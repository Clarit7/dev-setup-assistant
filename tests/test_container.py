"""
컨테이너 기능 테스트

Docker 데몬 없이 실행 가능한 범위만 다룹니다:
  - ContainerSetupAction 파싱 / 표시
  - devcontainer.json 파일 생성
  - 진입 스크립트 파일 생성
  - Windows Terminal 프로파일 등록
  - format_for_llm 출력 형식
  - safety.py docker 허용 여부
  - ide_connector 안내 메시지 형식
  - image_handler 가용성 확인
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from core.actions import (
    ContainerSetupAction,
    parse_actions,
    format_actions_for_display,
    InstallAction,
)
from core.container import (
    DockerStatus,
    ContainerInfo,
    create_devcontainer_config,
    create_entry_scripts,
    register_windows_terminal_profile,
    format_for_llm,
)
from core.ide_connector import detect_ides, get_devcontainer_guidance
from core.safety import is_safe_command


# ── ContainerSetupAction 파싱 ────────────────────────────────────────────────

class TestContainerActionParsing:
    def _make_raw(self, **kwargs):
        base = {
            "type": "container_setup",
            "image": "node:18-bullseye",
            "container_name": "my-dev",
            "workspace_path": "",
            "ports": ["3000:3000"],
            "display_name": "Node.js 컨테이너",
        }
        base.update(kwargs)
        return base

    def test_parses_container_setup_type(self):
        actions = parse_actions([self._make_raw()])
        assert len(actions) == 1
        assert isinstance(actions[0], ContainerSetupAction)

    def test_image_field(self):
        actions = parse_actions([self._make_raw(image="python:3.11-slim")])
        assert actions[0].image == "python:3.11-slim"

    def test_container_name_field(self):
        actions = parse_actions([self._make_raw(container_name="my-python")])
        assert actions[0].container_name == "my-python"

    def test_ports_list(self):
        actions = parse_actions([self._make_raw(ports=["8000:8000", "5432:5432"])])
        assert actions[0].ports == ["8000:8000", "5432:5432"]

    def test_ports_comma_string_converted_to_list(self):
        actions = parse_actions([self._make_raw(ports="3000:3000, 8080:8080")])
        assert actions[0].ports == ["3000:3000", "8080:8080"]

    def test_empty_workspace_path_allowed(self):
        actions = parse_actions([self._make_raw(workspace_path="")])
        assert actions[0].workspace_path == ""

    def test_display_name_field(self):
        actions = parse_actions([self._make_raw(display_name="테스트 컨테이너")])
        assert actions[0].display_name == "테스트 컨테이너"

    def test_mixed_actions_parsed_correctly(self):
        raw = [
            {"type": "install", "package_id": "Docker.DockerDesktop",
             "display_name": "Docker", "check_command": "docker"},
            self._make_raw(),
        ]
        actions = parse_actions(raw)
        assert len(actions) == 2
        assert isinstance(actions[0], InstallAction)
        assert isinstance(actions[1], ContainerSetupAction)


# ── ContainerSetupAction 표시 ────────────────────────────────────────────────

class TestContainerActionDisplay:
    def _action(self, **kwargs):
        defaults = dict(
            image="node:18",
            container_name="dev",
            workspace_path="",
            ports=["3000:3000"],
            display_name="Node.js 컨테이너",
        )
        defaults.update(kwargs)
        return ContainerSetupAction(**defaults)

    def test_display_contains_image(self):
        text = format_actions_for_display([self._action()])
        assert "node:18" in text

    def test_display_contains_display_name(self):
        text = format_actions_for_display([self._action()])
        assert "Node.js 컨테이너" in text

    def test_display_shows_ports(self):
        text = format_actions_for_display([self._action(ports=["5000:5000"])])
        assert "5000:5000" in text

    def test_display_shows_no_ports_when_empty(self):
        text = format_actions_for_display([self._action(ports=[])])
        assert "없음" in text

    def test_display_contains_container_emoji(self):
        text = format_actions_for_display([self._action()])
        assert "🐳" in text


# ── devcontainer.json 파일 생성 ──────────────────────────────────────────────

class TestCreateDevcontainerConfig:
    def test_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(tmp, "mydev", "node:18", ["3000:3000"])
            assert path.exists()

    def test_file_path_in_devcontainer_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(tmp, "mydev", "node:18", [])
            assert path.parent.name == ".devcontainer"
            assert path.name == "devcontainer.json"

    def test_json_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(tmp, "mydev", "node:18", [])
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict)

    def test_name_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(tmp, "mydev", "node:18", [])
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["name"] == "mydev"

    def test_image_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(tmp, "mydev", "python:3.11", [])
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["image"] == "python:3.11"

    def test_forward_ports_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(
                tmp, "mydev", "node:18", ["3000:3000", "8080:8080"]
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            assert 3000 in data["forwardPorts"]
            assert 8080 in data["forwardPorts"]

    def test_invalid_port_string_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(
                tmp, "mydev", "node:18", ["invalid"]
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["forwardPorts"] == []

    def test_extensions_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_devcontainer_config(
                tmp, "mydev", "node:18", [],
                extensions=["ms-python.python"]
            )
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "ms-python.python" in (
                data["customizations"]["vscode"]["extensions"]
            )

    def test_overwrite_on_second_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            create_devcontainer_config(tmp, "first", "node:18", [])
            create_devcontainer_config(tmp, "second", "node:18", [])
            data = json.loads(
                (Path(tmp) / ".devcontainer" / "devcontainer.json")
                .read_text(encoding="utf-8")
            )
            assert data["name"] == "second"


# ── 진입 스크립트 생성 ────────────────────────────────────────────────────────

class TestCreateEntryScripts:
    def test_bat_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = create_entry_scripts("mydev", tmp)
            names = [s.name for s in scripts]
            assert "enter-dev.bat" in names

    def test_sh_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = create_entry_scripts("mydev", tmp)
            names = [s.name for s in scripts]
            assert "enter-dev.sh" in names

    def test_bat_contains_container_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = create_entry_scripts("mydev", tmp)
            bat = next(s for s in scripts if s.name == "enter-dev.bat")
            assert "mydev" in bat.read_text(encoding="utf-8")

    def test_sh_contains_container_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = create_entry_scripts("mydev", tmp)
            sh = next(s for s in scripts if s.name == "enter-dev.sh")
            assert "mydev" in sh.read_text(encoding="utf-8")

    def test_bat_contains_docker_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = create_entry_scripts("mydev", tmp)
            bat = next(s for s in scripts if s.name == "enter-dev.bat")
            assert "docker exec" in bat.read_text(encoding="utf-8")

    def test_sh_contains_docker_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts = create_entry_scripts("mydev", tmp)
            sh = next(s for s in scripts if s.name == "enter-dev.sh")
            assert "docker exec" in sh.read_text(encoding="utf-8")

    def test_creates_workspace_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "new_workspace")
            create_entry_scripts("mydev", target)
            assert os.path.isdir(target)


# ── Windows Terminal 프로파일 등록 ───────────────────────────────────────────

class TestRegisterWindowsTerminalProfile:
    def _make_settings_path(self, tmp: str) -> Path:
        """
        가짜 Windows Terminal settings.json을 올바른 경로에 생성합니다.
        glob 패턴: {LOCALAPPDATA}/Packages/Microsoft.WindowsTerminal_*/LocalState/settings.json
        여기서 tmp가 LOCALAPPDATA 역할을 합니다.
        """
        local_state = os.path.join(
            tmp, "Packages", "Microsoft.WindowsTerminal_fake", "LocalState"
        )
        os.makedirs(local_state, exist_ok=True)
        settings_path = Path(local_state) / "settings.json"
        settings_path.write_text(
            json.dumps({"profiles": {"list": []}}), encoding="utf-8"
        )
        return settings_path

    def test_returns_false_without_windows_terminal(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": "/nonexistent_path"}):
            result = register_windows_terminal_profile("mydev")
        assert result is False

    def test_returns_true_with_valid_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._make_settings_path(tmp)
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                result = register_windows_terminal_profile("mydev")
            assert result is True

    def test_profile_added_to_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = self._make_settings_path(tmp)
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                register_windows_terminal_profile("mydev")
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            profile_names = [p["name"] for p in data["profiles"]["list"]]
            assert any("mydev" in n for n in profile_names)

    def test_profile_contains_docker_exec(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = self._make_settings_path(tmp)
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                register_windows_terminal_profile("mydev")
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            profile = data["profiles"]["list"][0]
            assert "docker exec" in profile["commandline"]
            assert "mydev" in profile["commandline"]

    def test_duplicate_profile_is_updated_not_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = self._make_settings_path(tmp)
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
                register_windows_terminal_profile("mydev")
                register_windows_terminal_profile("mydev")
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            mydev_profiles = [
                p for p in data["profiles"]["list"] if "mydev" in p.get("name", "")
            ]
            assert len(mydev_profiles) == 1


# ── format_for_llm 출력 형식 ─────────────────────────────────────────────────

class TestFormatForLlm:
    def test_docker_not_installed_message(self):
        status = DockerStatus(installed=False, running=False)
        text = format_for_llm(status, [])
        assert "미설치" in text

    def test_docker_installed_but_not_running(self):
        status = DockerStatus(installed=True, running=False, version="Docker 24.0.0")
        text = format_for_llm(status, [])
        assert "미실행" in text or "실행" in text

    def test_docker_running_shows_version(self):
        status = DockerStatus(installed=True, running=True, version="Docker 24.0.0")
        text = format_for_llm(status, [])
        assert "Docker 24.0.0" in text

    def test_running_containers_listed(self):
        status = DockerStatus(installed=True, running=True, version="Docker 24.0.0")
        containers = [ContainerInfo("mydev", "node:18", "Up 2 hours")]
        text = format_for_llm(status, containers)
        assert "mydev" in text
        assert "node:18" in text

    def test_no_containers_message(self):
        status = DockerStatus(installed=True, running=True, version="Docker 24.0.0")
        text = format_for_llm(status, [])
        assert "없음" in text


# ── safety.py Docker 허용 ────────────────────────────────────────────────────

class TestDockerSafety:
    def test_docker_pull_allowed(self):
        ok, _ = is_safe_command(["docker", "pull", "node:18"])
        assert ok is True

    def test_docker_run_allowed(self):
        ok, _ = is_safe_command(
            ["docker", "run", "-d", "--name", "mydev", "node:18"]
        )
        assert ok is True

    def test_docker_exec_allowed(self):
        ok, _ = is_safe_command(
            ["docker", "exec", "-it", "mydev", "/bin/bash"]
        )
        assert ok is True

    def test_docker_ps_allowed(self):
        ok, _ = is_safe_command(["docker", "ps"])
        assert ok is True

    def test_docker_compose_allowed(self):
        ok, _ = is_safe_command(["docker-compose", "up", "-d"])
        assert ok is True

    def test_wsl_allowed(self):
        ok, _ = is_safe_command(["wsl", "--list"])
        assert ok is True

    def test_docker_system32_blocked(self):
        ok, reason = is_safe_command(
            ["docker", "run", "-v", "C:/Windows/System32:/host", "node:18"]
        )
        assert ok is False
        assert "시스템" in reason

    def test_docker_with_shell_injection_blocked(self):
        ok, reason = is_safe_command(
            ["docker", "exec", "mydev", "bash", "-c", "rm -rf / | bash"]
        )
        assert ok is False


# ── ide_connector 안내 메시지 ────────────────────────────────────────────────

class TestDevcontainerGuidance:
    def test_vscode_guidance_mentions_reopen(self):
        msg = get_devcontainer_guidance("vscode", "mydev")
        assert "Reopen in Container" in msg

    def test_cursor_guidance_mentions_cursor(self):
        msg = get_devcontainer_guidance("cursor", "mydev")
        assert "Cursor" in msg

    def test_guidance_mentions_screenshot_paste(self):
        msg = get_devcontainer_guidance("vscode", "mydev")
        assert "Ctrl+V" in msg or "스크린샷" in msg

    def test_guidance_mentions_ctrl_shift_p(self):
        msg = get_devcontainer_guidance("vscode", "mydev")
        assert "Ctrl+Shift+P" in msg

    def test_unknown_ide_fallback(self):
        msg = get_devcontainer_guidance("unknown_ide", "mydev")
        assert "mydev" in msg

    def test_detect_ides_returns_list(self):
        result = detect_ides()
        assert isinstance(result, list)

    def test_detect_ides_only_known_names(self):
        result = detect_ides()
        for ide in result:
            assert ide in ("vscode", "cursor")


# ── image_handler 가용성 ──────────────────────────────────────────────────────

class TestImageHandlerAvailability:
    def test_is_available_returns_bool(self):
        from ui.image_handler import is_available
        result = is_available()
        assert isinstance(result, bool)

    def test_grab_clipboard_image_returns_none_or_attachment(self):
        """클립보드 이미지가 없을 때 None을 반환하는지 확인합니다."""
        from ui.image_handler import grab_clipboard_image, is_available
        if not is_available():
            pytest.skip("Pillow 미설치")
        # 테스트 환경에서 클립보드에 이미지가 없을 가능성이 높으므로
        # None 또는 ImageAttachment 둘 다 허용
        from ui.image_handler import ImageAttachment
        result = grab_clipboard_image()
        assert result is None or isinstance(result, ImageAttachment)

    def test_load_image_from_nonexistent_file_returns_none(self):
        from ui.image_handler import load_image_from_file, is_available
        if not is_available():
            pytest.skip("Pillow 미설치")
        result = load_image_from_file("/nonexistent/file.png")
        assert result is None

    def test_load_image_from_file_returns_attachment(self):
        """실제 PNG 파일에서 ImageAttachment가 생성되는지 확인합니다."""
        from ui.image_handler import load_image_from_file, is_available, ImageAttachment
        if not is_available():
            pytest.skip("Pillow 미설치")

        # 1x1 최소 PNG 파일 생성
        try:
            from PIL import Image
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp_path = f.name
            img = Image.new("RGB", (10, 10), color=(255, 0, 0))
            img.save(tmp_path)
            result = load_image_from_file(tmp_path)
            assert isinstance(result, ImageAttachment)
            assert result.base64_data
            assert result.media_type == "image/png"
            assert result.source_path == tmp_path
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
