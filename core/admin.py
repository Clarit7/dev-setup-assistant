"""
관리자 권한 유틸리티

Windows UAC 상승(elevation) 관련 기능을 제공합니다.
"""
import ctypes
import os
import sys


def is_admin() -> bool:
    """현재 프로세스가 관리자 권한으로 실행 중인지 확인합니다."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """
    현재 앱을 관리자 권한으로 재실행합니다 (UAC 프롬프트 표시).

    Returns:
        True  — ShellExecute 호출 성공 (UAC 프롬프트가 표시됨)
        False — 호출 실패 (예: 비-Windows 환경)
    """
    try:
        # python.exe → pythonw.exe: 콘솔 창 없이 재실행
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
            if os.path.exists(pythonw):
                exe = pythonw
        params = " ".join(f'"{a}"' for a in sys.argv)
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,    # hwnd
            "runas", # lpOperation — 관리자 권한 요청
            exe,     # lpFile
            params,  # lpParameters
            None,    # lpDirectory
            1,       # nShowCmd (SW_SHOWNORMAL)
        )
        # ShellExecuteW는 32 초과 시 성공
        return int(ret) > 32
    except Exception:
        return False
