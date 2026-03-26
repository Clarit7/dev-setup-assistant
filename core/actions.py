"""
LLM이 반환하는 액션 정의

LLM은 JSON으로 액션 목록을 반환합니다.
각 액션은 실행 전 safety checker를 통과해야 합니다.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class InstallAction:
    """winget 등 패키지 관리자를 통한 패키지 설치"""
    package_id: str
    display_name: str
    check_command: str  # 이미 설치됐는지 확인할 CLI 명령어


@dataclass
class RunAction:
    """임의 명령어 실행 (safety checker 검사 필수)"""
    command: List[str]
    display_name: str


@dataclass
class LaunchAction:
    """설치 완료 후 앱 실행 (safety checker 검사 필수)"""
    command: List[str]
    display_name: str


@dataclass
class ContainerSetupAction:
    """Docker 컨테이너 개발 환경 구성

    앱이 직접 처리합니다 (LLM 생성 명령어 아님):
      - docker pull / docker run
      - .devcontainer/devcontainer.json 자동 생성
      - enter-dev.bat / enter-dev.sh 자동 생성
      - Windows Terminal 프로파일 자동 등록
      - VS Code / Cursor에서 워크스페이스 자동 열기
    """
    image: str            # Docker 이미지 (예: "node:18-bullseye")
    container_name: str   # 컨테이너 이름 (영숫자 + 하이픈)
    workspace_path: str   # 로컬 워크스페이스 경로 (빈 문자열이면 기본값 사용)
    ports: List[str]      # 포트 매핑 (예: ["3000:3000"])
    display_name: str


@dataclass
class SetEnvAction:
    """사용자로부터 API 키 등 환경변수 값을 입력받아 시스템에 영속 등록

    - Windows: HKCU\\Environment 레지스트리에 저장 (로그인 유지)
    - macOS / Linux: ~/.zshrc 또는 ~/.bashrc에 export 라인 추가
    LLM이 제안하는 key는 _ALLOWED_ENV_KEYS 화이트리스트로 검증합니다.
    """
    key: str           # 환경변수명  (예: "ANTHROPIC_API_KEY")
    display_name: str  # 사용자에게 보여줄 이름  (예: "Anthropic API 키")
    hint: str = ""     # 입력 힌트  (예: "sk-ant-...")


Action = Union[InstallAction, RunAction, LaunchAction, ContainerSetupAction, SetEnvAction]


def parse_actions(raw_actions: list) -> List[Action]:
    """LLM JSON 액션 목록 → Action 객체 리스트로 변환"""
    result: List[Action] = []
    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        action_type = item.get("type", "")

        if action_type == "install":
            result.append(InstallAction(
                package_id=item.get("package_id", ""),
                display_name=item.get("display_name", ""),
                check_command=item.get("check_command", ""),
            ))

        elif action_type == "run":
            cmd = item.get("command", [])
            if isinstance(cmd, str):
                cmd = cmd.split()
            result.append(RunAction(
                command=cmd,
                display_name=item.get("display_name", ""),
            ))

        elif action_type == "launch":
            cmd = item.get("command", [])
            if isinstance(cmd, str):
                cmd = cmd.split()
            result.append(LaunchAction(
                command=cmd,
                display_name=item.get("display_name", ""),
            ))

        elif action_type == "set_env":
            result.append(SetEnvAction(
                key=item.get("key", ""),
                display_name=item.get("display_name", ""),
                hint=item.get("hint", ""),
            ))

        elif action_type == "container_setup":
            ports = item.get("ports", [])
            if isinstance(ports, str):
                ports = [p.strip() for p in ports.split(",") if p.strip()]
            result.append(ContainerSetupAction(
                image=item.get("image", ""),
                container_name=item.get("container_name", ""),
                workspace_path=item.get("workspace_path", ""),
                ports=ports,
                display_name=item.get("display_name", ""),
            ))

    return result


def format_actions_for_display(actions: List[Action]) -> str:
    """액션 목록을 사용자에게 보여줄 문자열로 변환"""
    lines = []
    for action in actions:
        if isinstance(action, InstallAction):
            lines.append(f"  📦 설치: {action.display_name}")
        elif isinstance(action, RunAction):
            lines.append(f"  ▶  실행: {action.display_name}  ({' '.join(action.command)})")
        elif isinstance(action, LaunchAction):
            lines.append(f"  🚀 실행: {action.display_name}")
        elif isinstance(action, ContainerSetupAction):
            ports_str = ", ".join(action.ports) if action.ports else "없음"
            lines.append(f"  🐳 컨테이너: {action.display_name} ({action.image})")
            lines.append(f"      포트: {ports_str}")
        elif isinstance(action, SetEnvAction):
            lines.append(f"  🔑 환경변수: {action.display_name} ({action.key})")
    return "\n".join(lines)
