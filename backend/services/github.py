"""Synchronous GitHub REST operations for isolated web workspaces."""

import base64
import io
import shutil
import zipfile
from contextvars import ContextVar
from functools import wraps
from pathlib import Path, PurePosixPath

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.auth.credentials import decrypt_credential, encrypt_credential
from backend.models.github_connection import GitHubConnection
from backend.models.user import User
from backend.services.workspace import create_workspace_record, get_workspace, update_workspace_stats

API_ROOT = "https://api.github.com"
MAX_REPOSITORY_BYTES = 50 * 1024 * 1024
MAX_EXPANDED_BYTES = 250 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20_000
MAX_IMPORTED_FILES = 2_000
MAX_WORKSPACE_BYTES = 100 * 1024 * 1024
_operation_client: ContextVar[httpx.Client | None] = ContextVar(
    "github_operation_client",
    default=None,
)


def github_operation(function):
    """Reuse one HTTP client for every request in a GitHub service operation."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        existing = _operation_client.get()
        if existing is not None:
            return function(*args, **kwargs)
        with httpx.Client(
            base_url=API_ROOT,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            token = _operation_client.set(client)
            try:
                return function(*args, **kwargs)
            finally:
                _operation_client.reset(token)

    return wrapped


def validate_repository_archive(bundle: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Reject dangerous or oversized archives before any extraction begins."""
    members = bundle.infolist()
    if len(members) > MAX_ARCHIVE_MEMBERS:
        raise HTTPException(status_code=413, detail="Repository archive has too many members")
    expanded_bytes = 0
    imported_files = 0
    validated = []
    for member in members:
        path = PurePosixPath(member.filename)
        mode = member.external_attr >> 16
        is_symlink = (mode & 0o170000) == 0o120000
        if path.is_absolute() or ".." in path.parts or is_symlink:
            raise HTTPException(status_code=400, detail="Repository archive contains an unsafe path")
        expanded_bytes += member.file_size
        if expanded_bytes > MAX_EXPANDED_BYTES:
            raise HTTPException(status_code=413, detail="Repository archive expands beyond 250 MB")
        if not member.is_dir():
            imported_files += 1
            if imported_files > MAX_IMPORTED_FILES:
                raise HTTPException(status_code=413, detail="Repository contains more than 2,000 files")
        validated.append(member)
    return validated


def _token_request(token: str, method: str, path: str, **kwargs) -> httpx.Response:
    client = _operation_client.get()
    request = client.request if client is not None else httpx.request
    target = path if client is not None else f"{API_ROOT}{path}"
    response = request(
        method,
        target,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        **({} if client is not None else {"timeout": 30, "follow_redirects": True}),
        **kwargs,
    )
    return response


def _token(user: User) -> str:
    connection = user.github_connection
    token = decrypt_credential(connection.token_encrypted) if connection else None
    if not connection or not token:
        raise HTTPException(status_code=409, detail="Connect GitHub before using repository actions")
    return token


def _request(user: User, method: str, path: str, **kwargs) -> httpx.Response:
    response = _token_request(_token(user), method, path, **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", "GitHub request failed")
        except ValueError:
            detail = "GitHub request failed"
        raise HTTPException(status_code=400, detail=detail)
    return response


def connection_status(user: User, validate: bool = False) -> dict:
    connection = user.github_connection
    token = decrypt_credential(connection.token_encrypted) if connection else None
    connected = bool(connection and token)
    profile = None
    scopes = {
        scope.strip()
        for scope in ((connection.scopes if connection else "") or "").split(",")
        if scope.strip()
    }
    if connected and validate and token:
        response = _token_request(token, "GET", "/user")
        if response.status_code >= 400:
            connected = False
        else:
            profile = response.json()
            response_scopes = response.headers.get("x-oauth-scopes", "")
            if response_scopes:
                scopes = {scope.strip() for scope in response_scopes.split(",") if scope.strip()}

    method = connection.method if connection else None
    write = bool({"repo", "public_repo"} & scopes) or method == "pat"
    return {
        "connected": connected,
        "method": method if connected else None,
        "login": (profile or {}).get("login") or (
            connection.login if connection else None
        ),
        "avatarUrl": (profile or {}).get("avatar_url") or (
            connection.avatar_url if connection else None
        ),
        "repositoryCount": (profile or {}).get("public_repos"),
        "lastValidatedAt": connection.updated_at.isoformat() if connection and connection.updated_at else None,
        "maskedCredential": "••••" + token[-4:] if connected and token else None,
        "capabilities": {
            "listRepositories": connected,
            "readContents": connected,
            "writeContents": connected and write,
            "createPullRequests": connected and write,
        },
    }


@github_operation
def connect_pat(db: Session, user: User, token: str) -> dict:
    response = _token_request(token, "GET", "/user")
    if response.status_code >= 400:
        raise HTTPException(status_code=400, detail="GitHub rejected this credential")
    profile = response.json()
    scopes = response.headers.get("x-oauth-scopes", "")
    connection = user.github_connection or GitHubConnection(user_id=user.id)
    connection.provider_user_id = str(profile["id"])
    connection.login = profile.get("login")
    connection.avatar_url = profile.get("avatar_url")
    connection.token_encrypted = encrypt_credential(token)
    connection.scopes = scopes
    connection.method = "pat"
    user.github_connection = connection
    db.add(connection)
    db.commit()
    db.refresh(user)
    return connection_status(user, validate=True)


@github_operation
def connect_oauth_token(
    db: Session,
    user: User,
    token: str,
    provider_id: str,
    login: str,
    avatar_url: str | None,
    scopes: str,
) -> dict:
    connection = user.github_connection or GitHubConnection(user_id=user.id)
    connection.provider_user_id = provider_id
    connection.login = login
    connection.avatar_url = avatar_url
    connection.token_encrypted = encrypt_credential(token)
    connection.scopes = scopes
    connection.method = "oauth"
    user.github_connection = connection
    db.add(connection)
    db.commit()
    db.refresh(user)
    return connection_status(user, validate=True)


def disconnect(db: Session, user: User) -> None:
    connection = user.github_connection
    if connection:
        db.delete(connection)
    db.commit()


def _assert_workspace_binding(workspace, owner: str, repo: str) -> None:
    expected = f"github.com/{owner.lower()}/{repo.lower()}"
    if workspace.source_type != "github" or workspace.project_id != expected:
        raise HTTPException(
            status_code=409,
            detail=(
                "This workspace is not bound to the requested GitHub repository. "
                "Re-import the repository before publishing changes."
            ),
        )


def _assert_remote_head(workspace, branch: str, remote_head: str) -> None:
    if workspace.git_branch != branch:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Workspace is bound to branch '{workspace.git_branch}', not '{branch}'. "
                "Create or select the branch from this workspace first."
            ),
        )
    if workspace.git_head and workspace.git_head != remote_head:
        raise HTTPException(
            status_code=409,
            detail=(
                "The remote branch changed since this workspace was imported. "
                "Refresh or re-import before committing."
            ),
        )


@github_operation
def list_repositories(
    user: User,
    cursor: str | None = None,
    owner: str | None = None,
    query: str | None = None,
) -> dict:
    try:
        page = max(int(cursor or "1"), 1)
    except ValueError:
        page = 1
    response = _request(
        user,
        "GET",
        "/user/repos",
        params={"sort": "updated", "per_page": 50, "page": max(page, 1)},
    )
    repositories = [
        {
            "id": item["id"],
            "full_name": item["full_name"],
            "private": item["private"],
            "default_branch": item["default_branch"],
            "updated_at": item["updated_at"],
            "archived": item.get("archived", False),
            "html_url": item.get("html_url"),
            "owner": {"login": item["owner"]["login"]},
            "permissions": item.get("permissions", {}),
        }
        for item in response.json()
        if (not owner or item["owner"]["login"].lower() == owner.lower())
        and (not query or query.lower() in item["full_name"].lower())
    ]
    owners = sorted({item["owner"]["login"] for item in response.json()})
    return {
        "repositories": repositories,
        "nextCursor": str(page + 1) if len(response.json()) == 50 else None,
        "owners": owners,
    }


@github_operation
def list_branches(user: User, owner: str, repo: str) -> list[dict]:
    response = _request(user, "GET", f"/repos/{owner}/{repo}/branches", params={"per_page": 100})
    return [{"name": item["name"], "sha": item["commit"]["sha"], "protected": item["protected"]} for item in response.json()]


@github_operation
def import_repository(
    db: Session,
    user: User,
    session_id: str,
    owner: str,
    repo: str,
    branch: str,
) -> object:
    archive = _request(user, "GET", f"/repos/{owner}/{repo}/zipball/{branch}").content
    if len(archive) > MAX_REPOSITORY_BYTES:
        raise HTTPException(status_code=413, detail="Repository archive exceeds the 50 MB import limit")

    ref = _request(user, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}").json()
    head = ref["object"]["sha"]
    workspace = create_workspace_record(db, user.id, session_id, repo)
    root = Path(workspace.storage_path)

    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = [
                member
                for member in validate_repository_archive(bundle)
                if not member.is_dir()
            ]
            prefixes = {PurePosixPath(member.filename).parts[0] for member in members if PurePosixPath(member.filename).parts}
            prefix = next(iter(prefixes)) if len(prefixes) == 1 else None
            for member in members:
                parts = list(PurePosixPath(member.filename).parts)
                if prefix and parts and parts[0] == prefix:
                    parts = parts[1:]
                if not parts or ".." in parts:
                    continue
                target = (root / Path(*parts)).resolve()
                try:
                    target.relative_to(root.resolve())
                except ValueError:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="GitHub returned an invalid repository archive") from exc

    update_workspace_stats(db, workspace)
    workspace.source_type = "github"
    workspace.project_id = f"github.com/{owner.lower()}/{repo.lower()}"
    workspace.git_remote = f"https://github.com/{owner}/{repo}.git"
    workspace.git_branch = branch
    workspace.git_head = head
    workspace.context_version = f"git:{head}"
    if workspace.session:
        workspace.session.project_id = workspace.project_id
        workspace.session.git_remote = workspace.git_remote
        workspace.session.git_branch = branch
        workspace.session.git_head = head
        workspace.session.context_version = workspace.context_version
    db.commit()
    db.refresh(workspace)
    return workspace


@github_operation
def create_branch(
    db: Session,
    user: User,
    workspace_id: str,
    owner: str,
    repo: str,
    source_branch: str,
    name: str,
) -> dict:
    workspace = get_workspace(db, workspace_id, user.id)
    _assert_workspace_binding(workspace, owner, repo)
    source = _request(user, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{source_branch}").json()
    _assert_remote_head(workspace, source_branch, source["object"]["sha"])
    response = _request(
        user,
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        json={"ref": f"refs/heads/{name}", "sha": source["object"]["sha"]},
    )
    head = response.json()["object"]["sha"]
    workspace.git_branch = name
    workspace.git_head = head
    if workspace.session:
        workspace.session.git_branch = name
        workspace.session.git_head = head
    db.commit()
    return {"name": name, "sha": head}


@github_operation
def commit_workspace(
    db: Session,
    user: User,
    workspace_id: str,
    owner: str,
    repo: str,
    branch: str,
    message: str,
    paths: list[str],
) -> dict:
    workspace = get_workspace(db, workspace_id, user.id)
    _assert_workspace_binding(workspace, owner, repo)
    root = Path(workspace.storage_path).resolve()
    ref = _request(user, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}").json()
    parent_sha = ref["object"]["sha"]
    _assert_remote_head(workspace, branch, parent_sha)
    parent = _request(user, "GET", f"/repos/{owner}/{repo}/git/commits/{parent_sha}").json()
    tree_items = []

    for relative in paths[:200]:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise HTTPException(status_code=400, detail=f"Invalid path: {relative}")
        target = (root / Path(*pure.parts)).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid path: {relative}") from exc
        if target.is_file():
            content = base64.b64encode(target.read_bytes()).decode("ascii")
            blob = _request(user, "POST", f"/repos/{owner}/{repo}/git/blobs", json={"content": content, "encoding": "base64"}).json()
            tree_items.append({"path": pure.as_posix(), "mode": "100644", "type": "blob", "sha": blob["sha"]})
        else:
            tree_items.append({"path": pure.as_posix(), "mode": "100644", "type": "blob", "sha": None})

    tree = _request(
        user,
        "POST",
        f"/repos/{owner}/{repo}/git/trees",
        json={"base_tree": parent["tree"]["sha"], "tree": tree_items},
    ).json()
    commit = _request(
        user,
        "POST",
        f"/repos/{owner}/{repo}/git/commits",
        json={"message": message, "tree": tree["sha"], "parents": [parent_sha]},
    ).json()
    _request(
        user,
        "PATCH",
        f"/repos/{owner}/{repo}/git/refs/heads/{branch}",
        json={"sha": commit["sha"], "force": False},
    )
    workspace.git_branch = branch
    workspace.git_head = commit["sha"]
    workspace.context_version = f"git:{commit['sha']}"
    if workspace.session:
        workspace.session.git_branch = branch
        workspace.session.git_head = commit["sha"]
        workspace.session.context_version = workspace.context_version
    db.commit()
    return {"sha": commit["sha"], "url": commit.get("html_url")}


@github_operation
def open_pull_request(
    db: Session,
    user: User,
    workspace_id: str,
    owner: str,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str,
    draft: bool = False,
) -> dict:
    workspace = get_workspace(db, workspace_id, user.id)
    _assert_workspace_binding(workspace, owner, repo)
    if workspace.git_branch != head:
        raise HTTPException(
            status_code=409,
            detail=f"Workspace is bound to branch '{workspace.git_branch}', not '{head}'.",
        )
    pull = _request(
        user,
        "POST",
        f"/repos/{owner}/{repo}/pulls",
        json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
    ).json()
    return {"number": pull["number"], "url": pull["html_url"], "state": pull["state"]}
