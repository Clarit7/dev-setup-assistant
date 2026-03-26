"""
컨테이너 관리 모듈

Docker 환경을 감지하고, VS Code devcontainer 설정 파일과
터미널 진입 스크립트를 자동으로 생성합니다.

자동화 가능한 것:
  - .devcontainer/devcontainer.json 생성 (VS Code/Cursor 자동 인식)
  - enter-dev.bat / enter-dev.sh 생성 (터미널 사용자)
  - Windows Terminal 프로파일 등록

수동 안내가 필요한 것:
  - VS Code의 'Reopen in Container' 버튼 클릭
  - Dev Containers 확장 설치 (미설치 시)
"""

import glob
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class DockerStatus:
    installed: bool
    running: bool
    version: Optional[str] = None


@dataclass
class ContainerInfo:
    name: str
    image: str
    status: str
    ports: str = ""


def detect_docker() -> DockerStatus:
    """Docker 설치 여부 및 데몬 실행 상태를 감지합니다."""
    if not shutil.which("docker"):
        return DockerStatus(installed=False, running=False)

    version = None
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0][:60]
    except Exception:
        pass

    running = False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,
        )
        running = result.returncode == 0
    except Exception:
        pass

    return DockerStatus(installed=True, running=running, version=version)


def list_containers() -> List[ContainerInfo]:
    """실행 중인 컨테이너 목록을 반환합니다."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--format",
             "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,
        )
        if result.returncode != 0:
            return []
        containers = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                containers.append(ContainerInfo(
                    name=parts[0],
                    image=parts[1],
                    status=parts[2],
                    ports=parts[3] if len(parts) > 3 else "",
                ))
        return containers
    except Exception:
        return []


def create_devcontainer_config(
    workspace_path: str,
    container_name: str,
    image: str,
    ports: List[str],
    extensions: Optional[List[str]] = None,
) -> Path:
    """
    .devcontainer/devcontainer.json 파일을 생성합니다.
    VS Code / Cursor의 Remote Containers 확장에서 자동 인식됩니다.
    """
    devcontainer_dir = Path(workspace_path) / ".devcontainer"
    devcontainer_dir.mkdir(parents=True, exist_ok=True)

    port_numbers: List[int] = []
    for p in ports:
        try:
            port_numbers.append(int(p.split(":")[0]))
        except (ValueError, IndexError):
            pass

    config = {
        "name": container_name,
        "image": image,
        "forwardPorts": port_numbers,
        "customizations": {
            "vscode": {
                "extensions": extensions or []
            }
        },
        "postCreateCommand": "echo '개발 컨테이너가 준비됐습니다!'",
        "remoteUser": "root",
    }

    config_path = devcontainer_dir / "devcontainer.json"
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return config_path


def create_entry_scripts(container_name: str, workspace_path: str) -> List[Path]:
    """
    컨테이너에 바로 진입하는 스크립트를 생성합니다.
      - enter-dev.bat : Windows 배치 파일 (더블클릭 실행)
      - enter-dev.sh  : Bash 스크립트 (WSL / Git Bash)
    """
    created: List[Path] = []
    base = Path(workspace_path)
    base.mkdir(parents=True, exist_ok=True)

    bat_path = base / "enter-dev.bat"
    bat_content = (
        "@echo off\n"
        f"echo 개발 컨테이너 [{container_name}]에 진입합니다...\n"
        f"docker start {container_name} 2>nul\n"
        f"docker exec -it {container_name} /bin/bash 2>nul "
        f"|| docker exec -it {container_name} /bin/sh\n"
        "if errorlevel 1 (\n"
        "  echo 컨테이너 진입에 실패했습니다. Docker Desktop이 실행 중인지 확인하세요.\n"
        "  pause\n"
        ")\n"
    )
    bat_path.write_text(bat_content, encoding="utf-8")
    created.append(bat_path)

    sh_path = base / "enter-dev.sh"
    sh_content = (
        "#!/bin/bash\n"
        f'echo "개발 컨테이너 [{container_name}]에 진입합니다..."\n'
        f"docker start {container_name} 2>/dev/null\n"
        f"docker exec -it {container_name} /bin/bash "
        f"|| docker exec -it {container_name} /bin/sh\n"
    )
    sh_path.write_text(sh_content, encoding="utf-8")
    created.append(sh_path)

    return created


def register_windows_terminal_profile(container_name: str) -> bool:
    """
    Windows Terminal 설정에 컨테이너 진입 프로파일을 등록합니다.
    성공하면 True, Windows Terminal이 없거나 실패하면 False를 반환합니다.
    """
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        return False

    pattern = os.path.join(
        local_app_data,
        "Packages", "Microsoft.WindowsTerminal_*",
        "LocalState", "settings.json",
    )
    matches = glob.glob(pattern)
    if not matches:
        return False

    settings_path = Path(matches[0])
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return False

    profiles = settings.setdefault("profiles", {})
    profile_list = profiles.setdefault("list", [])

    new_profile = {
        "name": f"\U0001f433 {container_name}",
        "commandline": (
            f"docker exec -it {container_name} /bin/bash 2>nul "
            f"|| docker exec -it {container_name} /bin/sh"
        ),
        "icon": "\U0001f433",
        "startingDirectory": "%USERPROFILE%",
        "hidden": False,
    }

    for i, p in enumerate(profile_list):
        if p.get("name") == new_profile["name"]:
            profile_list[i] = new_profile
            break
    else:
        profile_list.append(new_profile)

    try:
        settings_path.write_text(
            json.dumps(settings, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception:
        return False


def format_for_llm(docker_status: DockerStatus, containers: List[ContainerInfo]) -> str:
    """Docker 상태를 LLM 컨텍스트 문자열로 변환합니다."""
    lines = ["## Docker / 컨테이너 환경"]

    if not docker_status.installed:
        lines.append("Docker: 미설치 (winget install Docker.DockerDesktop 로 설치 가능)")
    elif not docker_status.running:
        lines.append(f"Docker: 설치됨 ({docker_status.version}) — 데몬 미실행")
        lines.append("사용자에게 Docker Desktop을 실행하도록 안내하세요.")
    else:
        lines.append(f"Docker: 실행 중 ({docker_status.version})")
        if containers:
            lines.append("현재 실행 중인 컨테이너:")
            for c in containers:
                lines.append(f"  • {c.name} ({c.image}) — {c.status}")
        else:
            lines.append("실행 중인 컨테이너: 없음")

    return "\n".join(lines)
