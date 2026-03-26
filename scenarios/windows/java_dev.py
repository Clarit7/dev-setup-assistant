"""
시나리오: Java / Spring 개발환경 (Windows)

지원: Windows (winget)
JDK 선택:
  1. Eclipse Temurin 21 LTS (OpenJDK)  — 범용 추천
  2. Eclipse Temurin 17 LTS (OpenJDK)  — 안정성 우선
  3. Microsoft OpenJDK 21              — Azure / Windows 최적화
빌드 도구 선택:
  1. Maven
  2. Gradle
에디터 선택:
  1. Visual Studio Code (+ Extension Pack for Java)
  2. IntelliJ IDEA Community Edition
"""
from ..base import Scenario, PackageSpec, LaunchSpec

_JDKS = {
    1: {"label": "Eclipse Temurin 21 LTS",    "check": "java",
        "winget": "EclipseAdoptium.Temurin.21.JDK"},
    2: {"label": "Eclipse Temurin 17 LTS",    "check": "java",
        "winget": "EclipseAdoptium.Temurin.17.JDK"},
    3: {"label": "Microsoft OpenJDK 21",      "check": "java",
        "winget": "Microsoft.OpenJDK.21"},
}

_BUILD_TOOLS = {
    1: {"label": "Maven",  "check": "mvn",     "winget": "Apache.Maven"},
    2: {"label": "Gradle", "check": "gradle",  "winget": "Gradle.Gradle"},
}

_EDITORS = {
    1: {"label": "Visual Studio Code",          "check": "code",
        "winget": "Microsoft.VisualStudioCode", "launch": ["code"]},
    2: {"label": "IntelliJ IDEA Community",     "check": "",
        "winget": "JetBrains.IntelliJIDEA.Community", "launch": []},
}

_MATCH_KEYWORDS = [
    "java", "spring", "springboot", "spring boot",
    "jdk", "maven", "gradle", "intellij",
    "자바", "스프링",
]


class JavaDevScenario(Scenario):
    name = "Java / Spring 개발환경 (Windows)"
    description = "JDK · Maven/Gradle · VSCode/IntelliJ 조합 Java 개발환경"
    supported_os = ["windows"]

    def __init__(self):
        self._jdk: int | None = None
        self._build: int | None = None
        self._editor: int | None = None

    def set_jdk(self, choice: int) -> None:
        if choice in _JDKS:
            self._jdk = choice

    def set_build(self, choice: int) -> None:
        if choice in _BUILD_TOOLS:
            self._build = choice

    def set_editor(self, choice: int) -> None:
        if choice in _EDITORS:
            self._editor = choice

    def get_jdk_choice_message(self) -> str:
        lines = ["Java 개발환경을 구성할게요.\nJDK를 선택해주세요:\n"]
        for idx, info in _JDKS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~3)")
        return "\n".join(lines)

    def get_build_choice_message(self) -> str:
        lines = ["빌드 도구를 선택해주세요:\n"]
        for idx, info in _BUILD_TOOLS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~2)")
        return "\n".join(lines)

    def get_editor_choice_message(self) -> str:
        lines = ["에디터를 선택해주세요:\n"]
        for idx, info in _EDITORS.items():
            lines.append(f"  {idx}. {info['label']}")
        lines.append("\n번호를 입력해주세요 (1~2)")
        return "\n".join(lines)

    def get_packages(self):
        jdk    = _JDKS[self._jdk]
        build  = _BUILD_TOOLS[self._build]
        editor = _EDITORS[self._editor]
        pkgs = [
            PackageSpec(jdk["label"],   jdk["check"],   {"winget": jdk["winget"]}),
            PackageSpec(build["label"], build["check"], {"winget": build["winget"]}),
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
        jdk    = _JDKS[self._jdk]
        build  = _BUILD_TOOLS[self._build]
        editor = _EDITORS[self._editor]
        return (
            f"{jdk['label']} + {build['label']} + {editor['label']} 환경을 설치합니다:\n\n"
            f"  • {jdk['label']}\n"
            f"  • {build['label']}\n"
            f"  • {editor['label']}\n\n"
            "설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in _MATCH_KEYWORDS)
