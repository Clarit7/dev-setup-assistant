"""
시나리오: Go 개발환경 (Windows)

지원: Windows (winget)
설치: Go + VSCode (with Go extension)
"""
from ..base import Scenario, PackageSpec, LaunchSpec

_MATCH_KEYWORDS = [
    "go ", "golang", "고랭", "고 언어", "go 언어",
    "go 개발", "go개발",
]

_EDITORS = {
    1: {"label": "Visual Studio Code", "check": "code",
        "winget": "Microsoft.VisualStudioCode", "launch": ["code"]},
    2: {"label": "GoLand (JetBrains)", "check": "",
        "winget": "JetBrains.GoLand", "launch": []},
}


class GoDevScenario(Scenario):
    name = "Go 개발환경 (Windows)"
    description = "Go 런타임 + VSCode / GoLand Go 개발환경"
    supported_os = ["windows"]

    def __init__(self):
        self._editor: int | None = None

    def set_editor(self, choice: int) -> None:
        if choice in _EDITORS:
            self._editor = choice

    def get_editor_choice_message(self) -> str:
        lines = ["Go 개발환경을 구성할게요.\n에디터를 선택해주세요:\n"]
        for idx, info in _EDITORS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~2)")
        return "\n".join(lines)

    def get_packages(self):
        editor = _EDITORS[self._editor]
        pkgs = [
            PackageSpec("Go", "go", {"winget": "GoLang.Go"}),
        ]
        if editor["winget"]:
            pkgs.append(
                PackageSpec(editor["label"], editor["check"], {"winget": editor["winget"]})
            )
        return pkgs

    def get_launch(self):
        editor = _EDITORS[self._editor]
        if editor["launch"]:
            return LaunchSpec(editor["label"], editor["launch"])
        return None

    def get_proposal_message(self) -> str:
        editor = _EDITORS[self._editor]
        return (
            f"Go 개발환경을 설치합니다:\n\n"
            f"  • Go  (공식 런타임)\n"
            f"  • {editor['label']}\n\n"
            "  ℹ️  VSCode 사용 시 'Go' 확장(golang.go)을 설치하세요.\n\n"
            "설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in _MATCH_KEYWORDS)
