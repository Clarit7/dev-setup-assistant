"""
시나리오 추상 클래스

새로운 개발환경 시나리오를 추가하려면 Scenario를 상속해 구현하세요.
각 시나리오는 지원 OS, 설치 패키지 목록, 실행 정보, 매칭 로직을 정의합니다.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PackageSpec:
    """
    설치할 패키지 명세

    Attributes:
        display_name:  사용자에게 보여줄 이름 (예: "Node.js")
        check_command: 이미 설치됐는지 확인할 CLI 명령어 (예: "node")
        package_ids:   인스톨러 타입별 패키지 ID 매핑
                       예: {"winget": "OpenJS.NodeJS", "brew": "node", "apt": "nodejs"}
    """
    display_name: str
    check_command: str
    package_ids: Dict[str, str] = field(default_factory=dict)


@dataclass
class LaunchSpec:
    """
    설치 완료 후 실행할 앱 명세

    Attributes:
        display_name: 사용자에게 보여줄 이름 (예: "Visual Studio Code")
        command:      실행 명령어 리스트 (예: ["code"])
    """
    display_name: str
    command: List[str]


class Scenario:
    """
    개발환경 시나리오 기본 클래스

    새 시나리오를 추가할 때는 이 클래스를 상속하고
    아래 속성/메서드를 모두 구현한 뒤 registry.py에 등록하세요.
    """
    name: str = ""
    description: str = ""
    supported_os: List[str] = []   # 예: ["windows", "macos", "linux"]

    def get_packages(self) -> List[PackageSpec]:
        """설치할 패키지 목록을 반환합니다."""
        return []

    def get_launch(self) -> Optional[LaunchSpec]:
        """설치 완료 후 실행할 앱 정보를 반환합니다. 없으면 None."""
        return None

    def get_proposal_message(self) -> str:
        """사용자에게 보여줄 설치 제안 메시지를 반환합니다."""
        return ""

    def matches(self, user_input: str) -> bool:
        """유저 입력이 이 시나리오에 해당하는지 판단합니다."""
        return False
