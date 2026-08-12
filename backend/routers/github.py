from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.db import get_db
from backend.models.user import User
from backend.services import github as github_service
from backend.services.ownership import owned_session, owned_workspace
from backend.auth.jwt import create_oauth_state, decode_oauth_state
from backend.auth.oauth import exchange_github_code
from backend.config import settings
from urllib.parse import urlencode

router = APIRouter(prefix="/github", tags=["github"])


class ImportRequest(BaseModel):
    session_id: str
    owner: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    branch: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")


class BranchRequest(BaseModel):
    workspace_id: str
    owner: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    source_branch: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    name: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._/-]+$")


class CommitRequest(BaseModel):
    workspace_id: str
    owner: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    branch: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    message: str = Field(min_length=1, max_length=500)
    paths: list[str] = Field(min_length=1, max_length=200)


class PullRequestBody(BaseModel):
    workspace_id: str
    owner: str
    repo: str
    title: str
    body: str = ""
    head: str
    base: str
    draft: bool = False


class PatConnectionRequest(BaseModel):
    token: str = Field(min_length=20, max_length=255)


class OAuthExchangeRequest(BaseModel):
    code: str
    state: str


@router.get("/status")
def connection_status(current_user: User = Depends(get_current_user)):
    return github_service.connection_status(current_user)


@router.get("/oauth/url")
def oauth_url(
    intent: str = "connect_github",
    return_to: str = "/chat",
    current_user: User = Depends(get_current_user),
):
    del current_user
    if not settings.github_client_id:
        raise HTTPException(status_code=400, detail="GitHub OAuth is not configured")
    state = create_oauth_state("github", intent=intent, return_to=return_to)
    url = "https://github.com/login/oauth/authorize?" + urlencode({
        "client_id": settings.github_client_id,
        "scope": "read:user user:email repo",
        "state": state,
    })
    return {"url": url}


@router.post("/oauth/exchange")
async def oauth_exchange(
    body: OAuthExchangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    state = decode_oauth_state(body.state, "github")
    if state.get("intent") != "connect_github":
        raise HTTPException(status_code=400, detail="OAuth intent does not match repository connection")
    info = await exchange_github_code(body.code)
    return github_service.connect_oauth_token(
        db,
        current_user,
        info["_access_token"],
        str(info["id"]),
        info.get("login") or info.get("name") or "GitHub",
        info.get("avatar_url"),
        info.get("_scopes", ""),
    )


@router.post("/connections/pat")
def connect_pat(
    body: PatConnectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return github_service.connect_pat(db, current_user, body.token)


@router.post("/connection/validate")
def validate_connection(current_user: User = Depends(get_current_user)):
    return github_service.connection_status(current_user, validate=True)


@router.delete("/connection", status_code=204)
def disconnect_connection(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    github_service.disconnect(db, current_user)


@router.get("/repositories")
def repositories(
    cursor: str | None = None,
    owner: str | None = None,
    query: str | None = None,
    current_user: User = Depends(get_current_user),
):
    return github_service.list_repositories(current_user, cursor, owner, query)


@router.get("/repositories/{owner}/{repo}/branches")
def branches(owner: str, repo: str, current_user: User = Depends(get_current_user)):
    return github_service.list_branches(current_user, owner, repo)


@router.post("/import")
def import_repo(body: ImportRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_session(db, body.session_id, current_user.id)
    return github_service.import_repository(db, current_user, body.session_id, body.owner, body.repo, body.branch)


@router.post("/branches")
@router.post("/publish/branch")
def create_branch(
    body: BranchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_workspace(db, body.workspace_id, current_user.id)
    return github_service.create_branch(
        db,
        current_user,
        body.workspace_id,
        body.owner,
        body.repo,
        body.source_branch,
        body.name,
    )


@router.post("/commit")
@router.post("/publish/commit")
def commit(body: CommitRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owned_workspace(db, body.workspace_id, current_user.id)
    return github_service.commit_workspace(
        db, current_user, body.workspace_id, body.owner, body.repo, body.branch, body.message, body.paths
    )


@router.post("/pull-requests")
@router.post("/publish/pull-request")
def pull_request(
    body: PullRequestBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_workspace(db, body.workspace_id, current_user.id)
    return github_service.open_pull_request(
        db,
        current_user,
        body.workspace_id,
        body.owner,
        body.repo,
        body.title,
        body.body,
        body.head,
        body.base,
        body.draft,
    )
