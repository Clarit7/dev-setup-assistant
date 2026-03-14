"""
시나리오 레지스트리

새로운 시나리오를 추가할 때는 _ALL_SCENARIOS 리스트에 인스턴스를 추가하세요.
매칭 우선순위는 리스트 순서를 따릅니다.
"""
import platform
from typing import Optional

from .base import Scenario
from .windows.js_timer import JSTimerScenario

# ── 등록된 시나리오 목록 ─────────────────────────────────────────────────────
_ALL_SCENARIOS: list = [
    JSTimerScenario(),
    # 추가 예시:
    # ReactAppScenario(),
    # PythonFlaskScenario(),
    # JavaSpringScenario(),
]


def get_current_os() -> str:
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "macos"
    return "linux"


def match_scenario(user_input: str) -> Optional[Scenario]:
    """유저 입력과 현재 OS에 맞는 시나리오를 반환합니다. 없으면 None."""
    current_os = get_current_os()
    for scenario in _ALL_SCENARIOS:
        if current_os in scenario.supported_os and scenario.matches(user_input):
            return scenario
    return None


def list_supported_scenarios() -> list:
    """현재 OS에서 지원 가능한 시나리오 목록을 반환합니다."""
    current_os = get_current_os()
    return [s for s in _ALL_SCENARIOS if current_os in s.supported_os]
