"""
안전한 명령어 실행기

모든 외부 명령어는 safety.py 검사를 통과해야만 실행됩니다.
stdout/stderr를 실시간으로 on_output 콜백에 전달합니다.
"""
import subprocess
import platform
import threading
from typing import Callable, List, Optional

from .safety import is_safe_command


def run_command(
    cmd: List[str],
    on_output: Callable[[str], None],
    on_error: Callable[[str], None],
    stop_event: Optional[threading.Event] = None,
) -> bool:
    """
    명령어를 안전하게 실행합니다.

    Args:
        cmd:        실행할 명령어 리스트
        on_output:  표준 출력 수신 콜백 (문자열)
        on_error:   오류 메시지 수신 콜백 (문자열)
        stop_event: 설정되면 프로세스를 강제 종료하고 False 반환

    Returns:
        True  — 성공 (returncode == 0)
        False — 실패, 차단, 또는 취소
    """
    safe, reason = is_safe_command(cmd)
    if not safe:
        on_error(f"[보안 차단] {reason}\n")
        return False

    kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        process = subprocess.Popen(cmd, **kwargs)
        for raw in process.stdout:
            if stop_event and stop_event.is_set():
                process.kill()
                process.wait()
                return False
            # winget은 UTF-16LE 또는 UTF-8 혼용 가능 — replace로 안전하게 처리
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                line = raw.decode("mbcs", errors="replace")
            on_output(line)
        process.wait()
        if stop_event and stop_event.is_set():
            return False
        return process.returncode == 0

    except FileNotFoundError:
        on_error(f"명령어를 찾을 수 없습니다: '{cmd[0]}'\n")
        return False
    except Exception as e:
        on_error(f"실행 오류: {e}\n")
        return False
