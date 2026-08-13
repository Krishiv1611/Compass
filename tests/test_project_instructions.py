import tempfile
import unittest
from pathlib import Path


from agent.instructions import (
    append_learned_instruction,
    initialize_compass_file,
    load_project_instructions,
    render_project_instructions,
)


class ProjectInstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "workspace"
        self.home = Path(self.temp.name) / "home"
        self.root.mkdir()
        (self.home / ".compass").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_workspace_compass_has_highest_precedence(self):
        rules = {
            "AGENTS.md": "style=agents",
            "CLAUDE.md": "style=claude",
            "GEMINI.md": "style=gemini",
            "COMPASS.md": "style=compass",
        }
        for name, content in rules.items():
            (self.root / name).write_text(content, encoding="utf-8")

        sources = load_project_instructions(self.root, home=self.home)

        self.assertEqual(
            [source.path.name for source in sources],
            ["AGENTS.md", "CLAUDE.md", "GEMINI.md", "COMPASS.md"],
        )
        self.assertTrue(
            render_project_instructions(sources).rstrip().endswith("style=compass")
        )

    def test_global_rules_are_lowest_precedence_and_newlines_are_normalized(self):
        (self.home / ".compass" / "COMPASS.md").write_bytes(b"global\r\nrules\r")
        (self.root / "AGENTS.md").write_text("workspace", encoding="utf-8")

        sources = load_project_instructions(self.root, home=self.home)

        self.assertEqual([source.precedence for source in sources], [0, 1])
        self.assertEqual(sources[0].content, "global\nrules\n")

    def test_render_limit_retains_higher_precedence_first(self):
        (self.root / "AGENTS.md").write_text("low-" * 20, encoding="utf-8")
        (self.root / "COMPASS.md").write_text("highest-rule", encoding="utf-8")

        rendered = render_project_instructions(
            load_project_instructions(self.root, home=self.home),
            max_chars=80,
        )

        self.assertIn("highest-rule", rendered)
        self.assertLessEqual(len(rendered), 80)

    def test_invalid_utf8_rule_is_ignored(self):
        (self.root / "AGENTS.md").write_bytes(b"\xff\xfe")
        self.assertEqual(load_project_instructions(self.root, home=self.home), [])

    def test_init_never_overwrites_without_force(self):
        target = self.root / "COMPASS.md"
        target.write_text("keep me", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            initialize_compass_file(self.root, force=False)

        self.assertEqual(target.read_text(encoding="utf-8"), "keep me")

    def test_init_force_requires_approval(self):
        target = self.root / "COMPASS.md"
        target.write_text("old", encoding="utf-8")

        with self.assertRaises(PermissionError):
            initialize_compass_file(self.root, force=True, approved=False)
        initialize_compass_file(self.root, force=True, approved=True)

        self.assertIn("# Compass project instructions", target.read_text(encoding="utf-8"))

    def test_learn_requires_approval_and_appends_one_bullet(self):
        initialize_compass_file(self.root)

        with self.assertRaises(PermissionError):
            append_learned_instruction(self.root, "Prefer small functions", approved=False)
        addition = append_learned_instruction(
            self.root, "Prefer small functions", approved=True
        )

        content = (self.root / "COMPASS.md").read_text(encoding="utf-8")
        self.assertEqual(addition, "- Prefer small functions")
        self.assertEqual(content.count("- Prefer small functions"), 1)

    def test_learn_rejects_empty_or_multiline_input(self):
        initialize_compass_file(self.root)
        for value in ("", "  ", "first\nsecond"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                append_learned_instruction(self.root, value, approved=True)


if __name__ == "__main__":
    unittest.main()
