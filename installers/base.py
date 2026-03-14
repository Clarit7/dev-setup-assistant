"""
인스톨러 추상 클래스

새로운 OS/패키지 관리자를 지원하려면 이 클래스를 상속해 구현합니다.
예: AptInstaller, BrewInstaller, ChocoInstaller 등
"""
from abc import ABC, abstractmethod
from typing import List


class BaseInstaller(ABC):
    installer_type: str = ""   # 고유 식별자 (예: "winget", "brew", "apt")

    @abstractmethod
    def build_install_command(self, package_id: str) -> List[str]:
        """패키지 설치 명령어 리스트를 반환합니다."""

    @abstractmethod
    def is_available(self) -> bool:
        """현재 시스템에서 이 인스톨러를 사용할 수 있는지 확인합니다."""
