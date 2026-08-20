"""Skill files must remain scoped to their owner and execution target."""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from agent.runtime.events import StreamEvent, StreamEventType
from agent.skills.loader import SkillScope, discover_skills
from agent.skills.registry import skill_registry, skill_scope
from agent.tools.create_skill_tool import create_skill
from agent.ui.tui import _stream_runtime_turn
from backend.routers import skills


def _skill_file(path: Path, name: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{name}.md").write_text(
        f"---\nname: {name}\ndescription: Test skill\n---\n\nUse the test skill.\n",
        encoding="utf-8",
    )


class SkillIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name) / "skills"
        self.user_a = SimpleNamespace(id="user-a")
        self.user_b = SimpleNamespace(id="user-b")

    def tearDown(self) -> None:
        self.temp_directory.cleanup()

    def test_web_user_cannot_list_another_users_skill(self) -> None:
        """Removing the user scope from web discovery would expose ``review``."""
        body = skills.SkillWrite(
            name="review", description="Review code", system_prompt="Review it."
        )

        with patch.object(skills, "configured_skill_root", return_value=self.root):
            skills.create_skill(body, current_user=self.user_a)
            visible_to_b = skills.list_skills(current_user=self.user_b)

        self.assertEqual([item.name for item in visible_to_b], [])
        self.assertTrue((self.root / "users" / "user-a" / "review.md").is_file())

    def test_invalid_skill_names_are_rejected_before_a_file_is_created(self) -> None:
        """Relaxing name validation would allow malformed or traversing paths."""
        for name in ("../../escape", "A B", "", "a" * 65):
            with self.subTest(name=name), self.assertRaises(HTTPException) as rejected:
                skills._safe_name(name)
            self.assertEqual(rejected.exception.status_code, 422)

        self.assertFalse(self.root.exists())

    def test_local_workspace_skill_is_not_visible_to_unrelated_web_users(self) -> None:
        """Adding workspace directories to web discovery would leak local skills."""
        workspace_skills = Path(self.temp_directory.name) / "workspace" / ".compass" / "skills"
        _skill_file(workspace_skills, "workspace-review")

        local_skills = discover_skills(
            SkillScope.local(global_dir=self.root, workspace_dir=workspace_skills)
        )
        web_skills = discover_skills(SkillScope.web(self.root, self.user_b.id))

        self.assertEqual([skill.name for skill in local_skills], ["workspace-review"])
        self.assertEqual(web_skills, [])

    def test_discovery_skips_a_skill_symlink_that_escapes_its_scope(self) -> None:
        """Resolving a symlink outside the scope must not leak its prompt."""
        outside = Path(self.temp_directory.name) / "outside.md"
        outside.write_text(
            "---\nname: escaped-skill\ndescription: Private\n---\n\nPrivate prompt.\n",
            encoding="utf-8",
        )
        scoped_dir = self.root / "users" / self.user_a.id
        scoped_dir.mkdir(parents=True)
        link = scoped_dir / "review.md"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symlink creation is unavailable: {exc}")

        self.assertEqual(discover_skills(SkillScope.web(self.root, self.user_a.id)), [])

    def test_run_scoped_registry_does_not_reuse_another_users_skills(self) -> None:
        """Reusing a process-wide registry would make ``review`` visible to user B."""
        _skill_file(self.root / "users" / self.user_a.id, "review")

        with skill_scope(SkillScope.web(self.root, self.user_a.id)):
            self.assertIsNotNone(skill_registry.get("review"))
        with skill_scope(SkillScope.web(self.root, self.user_b.id)):
            self.assertIsNone(skill_registry.get("review"))

    def test_skill_creation_never_returns_the_server_file_path(self) -> None:
        """Returning a path would disclose the server filesystem to a web user."""
        with skill_scope(SkillScope.web(self.root, self.user_a.id)):
            result = create_skill.invoke(
                {
                    "name": "review",
                    "description": "Review code",
                    "system_prompt": "Review it.",
                }
            )

        self.assertIn("user skills", result)
        self.assertNotIn(str(self.root), result)

    def test_tui_runtime_scopes_the_registry_freshly_for_each_run(self) -> None:
        """A TUI run must not retain another workspace's default registry."""
        workspace_a = Path(self.temp_directory.name) / "workspace-a"
        workspace_b = Path(self.temp_directory.name) / "workspace-b"
        _skill_file(workspace_a / ".compass" / "skills", "review")
        observed: list[bool] = []

        async def stream(_input_value, _config):
            observed.append(skill_registry.get("review") is not None)
            yield StreamEvent(type=StreamEventType.DONE, data={"status": "completed"})

        compass = MagicMock()
        compass.console = MagicMock()
        with patch("agent.runtime.runner.stream_agent_events", stream):
            asyncio.run(
                _stream_runtime_turn(
                    compass,
                    {"messages": []},
                    {"configurable": {"workspace_context": {"root": str(workspace_a)}}},
                    1,
                )
            )
            asyncio.run(
                _stream_runtime_turn(
                    compass,
                    {"messages": []},
                    {"configurable": {"workspace_context": {"root": str(workspace_b)}}},
                    2,
                )
            )

        self.assertEqual(observed, [True, False])


if __name__ == "__main__":
    unittest.main()
