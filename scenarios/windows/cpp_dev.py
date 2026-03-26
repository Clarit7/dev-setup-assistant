"""
시나리오: C / C++ 개발환경 (Windows)

지원: Windows (winget)
컴파일러 선택:
  1. GCC / MinGW-w64 (MSYS2 via winget) + CMake + VSCode  — 오픈소스 경량 구성
  2. Visual Studio Community 2022                          — MSVC + 통합 디버거 + CMake 내장
  3. Clang / LLVM + CMake + VSCode                        — 크로스 플랫폼 빌드 지향
"""
from ..base import Scenario, PackageSpec, LaunchSpec

_COMPILERS = {
    1: {
        "label":       "GCC / MinGW-w64  (MSYS2)",
        "packages": [
            PackageSpec("MSYS2",  "msys2", {"winget": "MSYS2.MSYS2"}),
            PackageSpec("CMake",  "cmake", {"winget": "Kitware.CMake"}),
            PackageSpec("Visual Studio Code", "code",
                        {"winget": "Microsoft.VisualStudioCode"}),
        ],
        "launch": LaunchSpec("Visual Studio Code", ["code"]),
        "note": "설치 후 MSYS2 터미널에서 `pacman -S mingw-w64-ucrt-x86_64-gcc` 를 실행하세요.",
    },
    2: {
        "label":       "Visual Studio Community 2022",
        "packages": [
            PackageSpec("Visual Studio Community 2022", "",
                        {"winget": "Microsoft.VisualStudio.2022.Community"}),
        ],
        "launch": None,
        "note": "설치 후 Visual Studio Installer에서 'C++를 사용한 데스크톱 개발' 워크로드를 선택하세요.",
    },
    3: {
        "label":       "Clang / LLVM + CMake + VSCode",
        "packages": [
            PackageSpec("LLVM / Clang", "clang", {"winget": "LLVM.LLVM"}),
            PackageSpec("CMake",        "cmake", {"winget": "Kitware.CMake"}),
            PackageSpec("Visual Studio Code", "code",
                        {"winget": "Microsoft.VisualStudioCode"}),
        ],
        "launch": LaunchSpec("Visual Studio Code", ["code"]),
        "note": "VSCode에서 'C/C++' 및 'CMake Tools' 확장을 설치하세요.",
    },
}

_MATCH_KEYWORDS = [
    "c++", "cpp", "c 언어", "c언어", "c 개발", "c개발",
    "gcc", "clang", "cmake", "visual studio",
    "c/c++", "c 프로그래밍", "c++ 프로그래밍",
]


class CppDevScenario(Scenario):
    name = "C/C++ 개발환경 (Windows)"
    description = "GCC·MSVC·Clang 중 선택하는 C/C++ 개발환경"
    supported_os = ["windows"]

    def __init__(self):
        self._compiler: int | None = None

    def set_compiler(self, choice: int) -> None:
        if choice in _COMPILERS:
            self._compiler = choice

    def get_compiler_choice_message(self) -> str:
        lines = ["C/C++ 개발환경을 구성할게요.\n컴파일러를 선택해주세요:\n"]
        for idx, info in _COMPILERS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~3)")
        return "\n".join(lines)

    def get_packages(self):
        return _COMPILERS[self._compiler]["packages"]

    def get_launch(self):
        return _COMPILERS[self._compiler]["launch"]

    def get_proposal_message(self) -> str:
        info = _COMPILERS[self._compiler]
        pkg_lines = "\n".join(
            f"  • {p.display_name}" for p in info["packages"]
        )
        return (
            f"{info['label']} 환경을 설치합니다:\n\n"
            f"{pkg_lines}\n\n"
            f"  ℹ️  {info['note']}\n\n"
            "설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in _MATCH_KEYWORDS)
