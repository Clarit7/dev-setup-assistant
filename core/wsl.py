"""WSL (Windows Subsystem for Linux) 감지 및 관리"""
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

_CF = 0x08000000


@dataclass
class WSLDistro:
    name: str
    state: str       # Running | Stopped
    version: int     # 1 or 2
    is_default: bool = False


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_wsl_available() -> bool:
    return is_windows() and shutil.which("wsl") is not None


def _decode_wsl_output(raw: bytes) -> str:
    """WSL 출력(UTF-16 LE)을 문자열로 변환합니다."""
    for enc in ("utf-16-le", "utf-8", "mbcs"):
        try:
            return raw.decode(enc, errors="replace")
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def list_wsl_distros() -> List[WSLDistro]:
    if not is_wsl_available():
        return []
    try:
        r = subprocess.run(
            ["wsl", "--list", "--verbose"],
            capture_output=True, timeout=10, creationflags=_CF,
        )
        raw = _decode_wsl_output(r.stdout)
        distros = []
        for line in raw.splitlines():
            line = line.replace("\x00", "").strip()
            if not line or "NAME" in line.upper():
                continue
            is_default = line.startswith("*")
            line = line.lstrip("* ").strip()
            parts = line.split()
            if len(parts) >= 3:
                name  = parts[0]
                state = parts[1]
                try:
                    ver = int(parts[2])
                except ValueError:
                    ver = 1
                distros.append(WSLDistro(
                    name=name, state=state,
                    version=ver, is_default=is_default,
                ))
        return distros
    except Exception:
        return []


def get_available_distros_online() -> List[str]:
    """설치 가능한 배포판 목록 (wsl --list --online)."""
    defaults = ["Ubuntu", "Ubuntu-24.04", "Ubuntu-22.04", "Debian", "kali-linux", "openSUSE-Leap-15.6"]
    if not is_wsl_available():
        return defaults
    try:
        r = subprocess.run(
            ["wsl", "--list", "--online"],
            capture_output=True, timeout=15, creationflags=_CF,
        )
        raw = _decode_wsl_output(r.stdout)
        names = []
        in_list = False
        for line in raw.splitlines():
            line = line.replace("\x00", "").strip()
            if not line:
                continue
            upper = line.upper()
            if "NAME" in upper and ("FRIENDLY" in upper or "DISTRIBUTION" in upper):
                in_list = True
                continue
            if in_list:
                parts = line.split()
                if parts and not parts[0].startswith("-"):
                    names.append(parts[0])
        return names if names else defaults
    except Exception:
        return defaults


def install_wsl_distro(distro: str = "Ubuntu", on_output=None) -> bool:
    if not is_wsl_available():
        return False
    try:
        proc = subprocess.Popen(
            ["wsl", "--install", "-d", distro],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=_CF,
        )
        if on_output and proc.stdout:
            for raw_line in proc.stdout:
                try:
                    on_output(_decode_wsl_output(raw_line))
                except Exception:
                    pass
        proc.wait(timeout=300)
        return proc.returncode == 0
    except Exception:
        return False


def set_default_distro(name: str) -> bool:
    try:
        r = subprocess.run(
            ["wsl", "--set-default", name],
            capture_output=True, timeout=10, creationflags=_CF,
        )
        return r.returncode == 0
    except Exception:
        return False


def set_wsl_version(name: str, version: int) -> bool:
    """배포판의 WSL 버전을 1 또는 2로 변환합니다 (시간이 걸릴 수 있음)."""
    try:
        r = subprocess.run(
            ["wsl", "--set-version", name, str(version)],
            capture_output=True, timeout=120, creationflags=_CF,
        )
        return r.returncode == 0
    except Exception:
        return False


def run_in_wsl(command: str, distro: Optional[str] = None):
    """WSL 내부에서 셸 명령어를 실행합니다. (success: bool, output: str) 반환."""
    cmd = ["wsl"]
    if distro:
        cmd += ["-d", distro]
    cmd += ["--", "bash", "-c", command]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=30, creationflags=_CF)
        out = _decode_wsl_output(r.stdout).strip()
        return r.returncode == 0, out
    except Exception as e:
        return False, str(e)


def open_wsl_terminal(distro: Optional[str] = None) -> bool:
    """새 cmd 창에서 WSL을 엽니다."""
    try:
        cmd = ["wsl"]
        if distro:
            cmd += ["-d", distro]
        subprocess.Popen(
            ["cmd", "/c", "start"] + cmd,
            shell=False, creationflags=_CF,
        )
        return True
    except Exception:
        return False
