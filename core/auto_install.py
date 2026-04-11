"""
패키지 자동 설치 유틸리티

ImportError 발생 시 pip으로 자동 설치합니다.
"""
from __future__ import annotations

import importlib
import subprocess
import sys


def ensure(pip_name: str, import_path: str | None = None) -> None:
    """
    패키지가 설치되지 않았으면 pip으로 자동 설치합니다.

    Args:
        pip_name:    pip install 에 사용할 패키지 이름 (예: "google-genai")
        import_path: 임포트 경로 (pip 이름과 다를 경우 명시, 예: "google.genai")
    """
    path = import_path or pip_name.replace("-", "_")
    try:
        importlib.import_module(path)
        return  # 이미 설치됨
    except ImportError:
        pass

    print(f"[자동 설치] {pip_name} 패키지를 설치합니다...", flush=True)
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", pip_name, "-q"],
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{pip_name} 자동 설치에 실패했습니다: {e}") from e

    importlib.invalidate_caches()
