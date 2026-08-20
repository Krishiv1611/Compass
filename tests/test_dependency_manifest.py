import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class DependencyManifestTests(unittest.TestCase):
    def test_runtime_requirements_are_exactly_locked(self):
        lines = (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
        unlocked = [
            line for line in lines
            if line.strip()
            and not line.lstrip().startswith(("#", "--hash="))
            and line.strip() != "\\"
            and "==" not in line
            and " @ " not in line
        ]
        self.assertEqual(unlocked, [])

    def test_docker_uses_frozen_lock(self):
        dockerfile = (ROOT / "backend.Dockerfile").read_text(encoding="utf-8")
        self.assertIn("requirements.lock", dockerfile)
        self.assertIn("--require-hashes", dockerfile)
        self.assertIn("ghcr.io/astral-sh/uv:0.9.1", dockerfile)
        self.assertIn("python:3.12.13-slim-bookworm", dockerfile)

    def test_pyproject_is_the_dependency_source(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertTrue(project["project"]["dependencies"])
        self.assertIn("dev", project["dependency-groups"])
        compatibility = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("-r requirements.lock", compatibility)

    def test_supported_python_is_pinned(self):
        self.assertEqual((ROOT / ".python-version").read_text().strip(), "3.12")

    def test_bootstrap_checks_native_process_failures(self):
        script = (ROOT / "tools" / "bootstrap.ps1").read_text(encoding="utf-8")
        self.assertIn("$LASTEXITCODE", script)
        self.assertIn("[version]$Matches[1]", script)


if __name__ == "__main__":
    unittest.main()
