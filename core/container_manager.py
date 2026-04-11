"""Docker 컨테이너 제어 (시작/중지/삭제/로그/진입)"""
import subprocess
from typing import List, Optional

_CF = 0x08000000  # CREATE_NO_WINDOW (Windows)


def _docker(*args, timeout: int = 15):
    """docker 명령어 실행. (success: bool, output: str) 반환."""
    try:
        r = subprocess.run(
            ["docker"] + list(args),
            capture_output=True, text=True, timeout=timeout,
            creationflags=_CF,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def list_all_containers():
    """실행 중 + 중지된 모든 컨테이너 목록을 반환합니다."""
    from core.container import ContainerInfo
    ok, out = _docker(
        "ps", "-a", "--format",
        "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}",
    )
    if not ok or not out:
        return []
    containers = []
    for line in out.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            containers.append(ContainerInfo(
                name=parts[0], image=parts[1], status=parts[2],
                ports=parts[3] if len(parts) > 3 else "",
            ))
    return containers


def start_container(name: str):
    return _docker("start", name)


def stop_container(name: str):
    return _docker("stop", name, timeout=30)


def remove_container(name: str):
    return _docker("rm", "-f", name)


def get_container_logs(name: str, lines: int = 100) -> str:
    _, out = _docker("logs", "--tail", str(lines), name, timeout=10)
    return out


def exec_container_in_terminal(name: str) -> bool:
    """새 cmd 창에서 컨테이너 셸에 진입합니다."""
    import platform
    try:
        if platform.system() == "Windows":
            subprocess.Popen(
                ["cmd", "/c", "start", "cmd", "/k",
                 f"docker exec -it {name} /bin/bash 2>nul || docker exec -it {name} /bin/sh"],
                shell=False, creationflags=_CF,
            )
        else:
            subprocess.Popen(["bash", "-c", f"docker exec -it {name} /bin/bash"])
        return True
    except Exception:
        return False
