"""
LLM이 반환하는 액션 정의

LLM은 JSON으로 액션 목록을 반환합니다.
각 액션은 실행 전 safety checker를 통과해야 합니다.
"""
from dataclasses import dataclass, field
from typing import List, Union


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


Action = Union[InstallAction, RunAction, LaunchAction]


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
    return "\n".join(lines)
