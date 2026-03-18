"""Tests for project initialization (init.py)."""

import json
import stat

from ember_code.init import BUILT_IN_HOOKS, initialize_project


class TestInitializeProject:
    def test_creates_marker_file(self, tmp_path):
        initialize_project(tmp_path)
        assert (tmp_path / ".ember" / ".initialized").exists()

    def test_returns_true_on_first_run(self, tmp_path):
        assert initialize_project(tmp_path) is True

    def test_returns_false_on_second_run(self, tmp_path):
        initialize_project(tmp_path)
        assert initialize_project(tmp_path) is False

    def test_never_runs_again_after_marker(self, tmp_path):
        initialize_project(tmp_path)
        # Delete everything except marker
        for child in (tmp_path / ".ember").iterdir():
            if child.name != ".initialized":
                if child.is_dir():
                    import shutil

                    shutil.rmtree(child)
                else:
                    child.unlink()

        # Second run should not recreate anything
        initialize_project(tmp_path)
        assert not (tmp_path / ".ember" / "hooks").exists()

    def test_creates_ember_directory(self, tmp_path):
        initialize_project(tmp_path)
        assert (tmp_path / ".ember").is_dir()

    def test_existing_ember_dir_not_destroyed(self, tmp_path):
        ember_dir = tmp_path / ".ember"
        ember_dir.mkdir()
        (ember_dir / "custom.txt").write_text("keep me")

        initialize_project(tmp_path)
        assert (ember_dir / "custom.txt").read_text() == "keep me"


class TestAgentCopy:
    def test_copies_builtin_agents(self, tmp_path):
        # Create fake built-in agents
        builtin = tmp_path / "builtin_agents"
        builtin.mkdir()
        (builtin / "editor.md").write_text("---\nname: editor\ndescription: edits\n---\nPrompt")
        (builtin / "explorer.md").write_text(
            "---\nname: explorer\ndescription: explores\n---\nPrompt"
        )

        # Patch PACKAGE_ROOT
        import ember_code.init as init_mod

        original = init_mod.PACKAGE_ROOT
        # Create expected structure: PACKAGE_ROOT / "agents"
        fake_root = tmp_path / "fake_root"
        fake_root.mkdir()
        agents_dir = fake_root / "agents"
        agents_dir.mkdir()
        (agents_dir / "editor.md").write_text("editor content")
        (agents_dir / "docs.md").write_text("docs content")

        init_mod.PACKAGE_ROOT = fake_root
        try:
            project = tmp_path / "project"
            project.mkdir()
            initialize_project(project)

            copied = project / ".ember" / "agents"
            assert (copied / "editor.md").exists()
            assert (copied / "docs.md").exists()
            assert (copied / "editor.md").read_text() == "editor content"
        finally:
            init_mod.PACKAGE_ROOT = original

    def test_does_not_overwrite_existing_agents(self, tmp_path):
        import ember_code.init as init_mod

        original = init_mod.PACKAGE_ROOT

        fake_root = tmp_path / "fake_root"
        (fake_root / "agents").mkdir(parents=True)
        (fake_root / "agents" / "editor.md").write_text("builtin version")
        (fake_root / "skills").mkdir()

        init_mod.PACKAGE_ROOT = fake_root
        try:
            project = tmp_path / "project"
            project.mkdir()
            agents_dir = project / ".ember" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "editor.md").write_text("user version")

            initialize_project(project)
            assert (agents_dir / "editor.md").read_text() == "user version"
        finally:
            init_mod.PACKAGE_ROOT = original


class TestSkillCopy:
    def test_copies_builtin_skills(self, tmp_path):
        import ember_code.init as init_mod

        original = init_mod.PACKAGE_ROOT

        fake_root = tmp_path / "fake_root"
        (fake_root / "agents").mkdir(parents=True)
        skills_dir = fake_root / "skills"
        (skills_dir / "commit").mkdir(parents=True)
        (skills_dir / "commit" / "SKILL.md").write_text("commit skill")
        (skills_dir / "simplify").mkdir(parents=True)
        (skills_dir / "simplify" / "SKILL.md").write_text("simplify skill")

        init_mod.PACKAGE_ROOT = fake_root
        try:
            project = tmp_path / "project"
            project.mkdir()
            initialize_project(project)

            copied = project / ".ember" / "skills"
            assert (copied / "commit" / "SKILL.md").exists()
            assert (copied / "simplify" / "SKILL.md").exists()
            assert (copied / "commit" / "SKILL.md").read_text() == "commit skill"
        finally:
            init_mod.PACKAGE_ROOT = original

    def test_ignores_non_skill_directories(self, tmp_path):
        import ember_code.init as init_mod

        original = init_mod.PACKAGE_ROOT

        fake_root = tmp_path / "fake_root"
        (fake_root / "agents").mkdir(parents=True)
        skills_dir = fake_root / "skills"
        # Dir without SKILL.md
        (skills_dir / "broken").mkdir(parents=True)
        (skills_dir / "broken" / "README.md").write_text("not a skill")

        init_mod.PACKAGE_ROOT = fake_root
        try:
            project = tmp_path / "project"
            project.mkdir()
            initialize_project(project)
            assert not (project / ".ember" / "skills" / "broken").exists()
        finally:
            init_mod.PACKAGE_ROOT = original


class TestHookProvisioning:
    def test_writes_hook_scripts(self, tmp_path):
        initialize_project(tmp_path)
        hooks_dir = tmp_path / ".ember" / "hooks"
        for hook in BUILT_IN_HOOKS:
            script = hooks_dir / hook["filename"]
            assert script.exists()
            assert script.stat().st_mode & stat.S_IXUSR  # executable

    def test_registers_hooks_in_settings(self, tmp_path):
        initialize_project(tmp_path)
        settings = json.loads((tmp_path / ".ember" / "settings.json").read_text())
        assert "hooks" in settings
        assert "Stop" in settings["hooks"]
        assert any(h["command"] == ".ember/hooks/docs-remind.sh" for h in settings["hooks"]["Stop"])

    def test_preserves_existing_settings(self, tmp_path):
        ember_dir = tmp_path / ".ember"
        ember_dir.mkdir()
        (ember_dir / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Read"]}}))

        initialize_project(tmp_path)
        settings = json.loads((ember_dir / "settings.json").read_text())
        assert settings["permissions"]["allow"] == ["Read"]
        assert "hooks" in settings


class TestEmberMd:
    def test_creates_ember_md(self, tmp_path):
        initialize_project(tmp_path)
        path = tmp_path / "ember.md"
        assert path.exists()
        assert "Project Context" in path.read_text()

    def test_does_not_overwrite_existing_ember_md(self, tmp_path):
        (tmp_path / "ember.md").write_text("my custom context")
        initialize_project(tmp_path)
        assert (tmp_path / "ember.md").read_text() == "my custom context"
