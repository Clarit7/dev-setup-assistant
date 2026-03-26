"""
시나리오: Rust 개발환경 (Windows)

지원: Windows (winget)
설치: rustup (toolchain manager) + Visual Studio Build Tools (링커 필요) + VSCode
"""
from ..base import Scenario, PackageSpec, LaunchSpec

_MATCH_KEYWORDS = [
    "rust", "러스트", "cargo", "rustup", "웹어셈블리", "wasm",
    "시스템 프로그래밍", "시스템프로그래밍",
]

_EDITORS = {
    1: {"label": "Visual Studio Code", "check": "code",
        "winget": "Microsoft.VisualStudioCode", "launch": ["code"]},
    2: {"label": "RustRover (JetBrains)", "check": "",
        "winget": "JetBrains.RustRover", "launch": []},
}


class RustDevScenario(Scenario):
    name = "Rust 개발환경 (Windows)"
    description = "rustup + VS Build Tools + VSCode/RustRover Rust 개발환경"
    supported_os = ["windows"]

    def __init__(self):
        self._editor: int | None = None

    def set_editor(self, choice: int) -> None:
        if choice in _EDITORS:
            self._editor = choice

    def get_editor_choice_message(self) -> str:
        lines = ["Rust 개발환경을 구성할게요.\n에디터를 선택해주세요:\n"]
        for idx, info in _EDITORS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~2)")
        return "\n".join(lines)

    def get_packages(self):
        editor = _EDITORS[self._editor]
        pkgs = [
            PackageSpec("rustup", "rustup", {"winget": "Rustlang.Rustup"}),
            # Rust on Windows는 MSVC 링커 필요 (VS Build Tools)
            PackageSpec("VS Build Tools 2022", "",
                        {"winget": "Microsoft.VisualStudioBuildTools"}),
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
            f"Rust 개발환경을 설치합니다:\n\n"
            f"  • rustup  (Rust toolchain 관리자)\n"
            f"  • VS Build Tools 2022  (MSVC 링커, Windows Rust 필수)\n"
            f"  • {editor['label']}\n\n"
            "  ℹ️  설치 후 새 터미널에서 `rustup update stable` 을 실행하세요.\n\n"
            "설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in _MATCH_KEYWORDS)
