"""
시나리오: 웹 개발환경 구성 (2단계 선택)

지원: Windows (winget)
1단계 — 스택 선택: 프론트엔드(React) / 백엔드(Python Flask)
2단계 — 에디터 선택: Visual Studio Code / Cursor
"""
from ..base import Scenario, PackageSpec, LaunchSpec

_STACKS = {
    1: {
        "label":         "프론트엔드 (React)",
        "package_name":  "Node.js",
        "check_command": "node",
        "winget_id":     "OpenJS.NodeJS",
    },
    2: {
        "label":         "백엔드 (Python Flask)",
        "package_name":  "Python",
        "check_command": "python",
        "winget_id":     "Python.Python.3",
    },
}

_EDITORS = {
    1: {
        "name":          "Visual Studio Code",
        "check_command": "code",
        "winget_id":     "Microsoft.VisualStudioCode",
        "launch_cmd":    ["code"],
    },
    2: {
        "name":          "Cursor",
        "check_command": "cursor",
        "winget_id":     "Anysphere.Cursor",
        "launch_cmd":    ["cursor"],
    },
}


class WebDevScenario(Scenario):
    name = "웹 개발환경 (Windows)"
    description = "웹 개발환경 구성 (프론트엔드/백엔드 × VSCode/Cursor)"
    supported_os = ["windows"]

    def __init__(self):
        self._stack: int | None = None
        self._editor: int | None = None

    # ── 선택 저장 ─────────────────────────────────────────────────────────────

    def set_stack(self, choice: int) -> None:
        """1 = React, 2 = Python Flask"""
        self._stack = choice

    def set_editor(self, choice: int) -> None:
        """1 = VSCode, 2 = Cursor"""
        self._editor = choice

    # ── 선택 안내 메시지 ──────────────────────────────────────────────────────

    def get_stack_choice_message(self) -> str:
        return (
            "웹 개발 환경을 구성할게요!\n"
            "어떤 방향으로 시작하실 건가요?\n\n"
            "  1. 프론트엔드  —  React (Node.js)\n"
            "  2. 백엔드      —  Python Flask\n\n"
            "번호를 입력해주세요 (1 / 2)"
        )

    def get_editor_choice_message(self) -> str:
        return (
            "에디터를 선택해주세요:\n\n"
            "  1. Visual Studio Code\n"
            "  2. Cursor  (AI 코드 에디터)\n\n"
            "번호를 입력해주세요 (1 / 2)"
        )

    # ── Scenario 인터페이스 ───────────────────────────────────────────────────

    def get_packages(self):
        stack = _STACKS[self._stack]
        editor = _EDITORS[self._editor]
        return [
            PackageSpec(
                display_name=stack["package_name"],
                check_command=stack["check_command"],
                package_ids={"winget": stack["winget_id"]},
            ),
            PackageSpec(
                display_name=editor["name"],
                check_command=editor["check_command"],
                package_ids={"winget": editor["winget_id"]},
            ),
        ]

    def get_launch(self):
        editor = _EDITORS[self._editor]
        return LaunchSpec(
            display_name=editor["name"],
            command=editor["launch_cmd"],
        )

    def get_proposal_message(self) -> str:
        stack = _STACKS[self._stack]
        editor = _EDITORS[self._editor]
        return (
            f"{stack['label']} + {editor['name']} 개발환경을 설치합니다:\n\n"
            f"  • {stack['package_name']}\n"
            f"  • {editor['name']}\n\n"
            "설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        keywords = ["웹", "web", "개발 환경", "개발환경"]
        return any(kw in user_input.lower() for kw in keywords)
