"""
시나리오: .NET / C# 개발환경 (Windows)

지원: Windows (winget)
SDK 선택:
  1. .NET 9 SDK (최신)
  2. .NET 8 SDK (LTS 추천)
에디터 선택:
  1. Visual Studio Community 2022  — 완전 통합 IDE (ASP.NET, WinForms, WPF 포함)
  2. Visual Studio Code + C# Dev Kit
  3. JetBrains Rider
"""
from ..base import Scenario, PackageSpec, LaunchSpec

_SDKS = {
    1: {"label": ".NET 9 SDK",   "check": "dotnet", "winget": "Microsoft.DotNet.SDK.9"},
    2: {"label": ".NET 8 SDK (LTS)", "check": "dotnet", "winget": "Microsoft.DotNet.SDK.8"},
}

_EDITORS = {
    1: {"label": "Visual Studio Community 2022", "check": "",
        "winget": "Microsoft.VisualStudio.2022.Community",
        "launch": [], "sdk_needed": False,
        "note": "Visual Studio 설치 시 '.NET 데스크톱 개발' 또는 'ASP.NET 및 웹 개발' 워크로드를 선택하세요."},
    2: {"label": "Visual Studio Code", "check": "code",
        "winget": "Microsoft.VisualStudioCode",
        "launch": ["code"], "sdk_needed": True,
        "note": "VSCode에서 'C# Dev Kit' 확장(ms-dotnettools.csdevkit)을 설치하세요."},
    3: {"label": "JetBrains Rider", "check": "",
        "winget": "JetBrains.Rider",
        "launch": [], "sdk_needed": True,
        "note": "Rider는 .NET SDK를 자동 감지합니다."},
}

_MATCH_KEYWORDS = [
    ".net", "dotnet", "c#", "csharp", "cs ", "asp.net", "aspnet",
    "닷넷", "씨샵", "wpf", "winforms", "blazor", "maui",
]


class DotNetDevScenario(Scenario):
    name = ".NET / C# 개발환경 (Windows)"
    description = ".NET SDK + Visual Studio / VSCode / Rider C# 개발환경"
    supported_os = ["windows"]

    def __init__(self):
        self._sdk: int | None = None
        self._editor: int | None = None

    def set_sdk(self, choice: int) -> None:
        if choice in _SDKS:
            self._sdk = choice

    def set_editor(self, choice: int) -> None:
        if choice in _EDITORS:
            self._editor = choice

    def get_sdk_choice_message(self) -> str:
        # Visual Studio는 .NET SDK를 자체 포함하므로 다른 경우만 SDK 선택 필요
        lines = [".NET / C# 개발환경을 구성할게요.\n.NET SDK 버전을 선택해주세요:\n"]
        for idx, info in _SDKS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~2)")
        return "\n".join(lines)

    def get_editor_choice_message(self) -> str:
        lines = ["에디터를 선택해주세요:\n"]
        for idx, info in _EDITORS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~3)")
        return "\n".join(lines)

    def get_packages(self):
        editor = _EDITORS[self._editor]
        pkgs = []
        # Visual Studio는 SDK 내장이므로 별도 SDK 불필요
        if editor["sdk_needed"] and self._sdk:
            sdk = _SDKS[self._sdk]
            pkgs.append(PackageSpec(sdk["label"], sdk["check"], {"winget": sdk["winget"]}))
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
        sdk_line = ""
        if editor["sdk_needed"] and self._sdk:
            sdk_line = f"  • {_SDKS[self._sdk]['label']}\n"
        return (
            f".NET / C# 개발환경을 설치합니다:\n\n"
            f"{sdk_line}"
            f"  • {editor['label']}\n\n"
            f"  ℹ️  {editor['note']}\n\n"
            "설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in _MATCH_KEYWORDS)
