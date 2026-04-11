"""
Windows Winget 인스톨러

Windows 10 1709+ 에 기본 포함된 winget 패키지 관리자를 사용합니다.
새 OS를 지원하려면 이 파일을 참고해 동일 인터페이스로 구현하세요.
"""
import shutil
from typing import List

from .base import BaseInstaller


class WingetInstaller(BaseInstaller):
    installer_type = "winget"

    def build_install_command(self, package_id: str) -> List[str]:
        return [
            "winget", "install",
            "--id", package_id, "-e",
            "--accept-package-agreements",
            "--accept-source-agreements",
            "--silent",
        ]

    def is_available(self) -> bool:
        return shutil.which("winget") is not None
