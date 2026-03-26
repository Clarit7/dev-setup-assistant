"""
시나리오: 게임 개발환경 (Windows)

지원: Windows (winget)
엔진 선택:
  1. Unity    — C# 기반, 2D/3D, 인디~AA급, 크로스 플랫폼 빌드
  2. Godot    — GDScript/C#, 오픈소스, 경량, 2D 강점
  3. Unreal Engine — C++/Blueprint, 고품질 3D, AAA 수준
  4. Pygame   — Python, 2D, 빠른 프로토타이핑·학습용
"""
from ..base import Scenario, PackageSpec, LaunchSpec

_ENGINES = {
    1: {
        "label":   "Unity",
        "desc":    "C# 기반 크로스 플랫폼 2D/3D 게임 엔진 (Unity Hub로 관리)",
        "packages": [
            PackageSpec("Unity Hub", "",
                        {"winget": "Unity.UnityHub"}),
            # Unity 에디터는 Unity Hub 안에서 설치
            PackageSpec("Visual Studio Community 2022", "",
                        {"winget": "Microsoft.VisualStudio.2022.Community"}),
        ],
        "launch": None,
        "note": (
            "Unity Hub 설치 후:\n"
            "  1. Unity Hub를 열고 로그인합니다.\n"
            "  2. 'Installs' 탭에서 원하는 Unity 버전을 설치합니다.\n"
            "  3. 'New Project'로 프로젝트를 생성합니다.\n"
            "Visual Studio 설치 시 '.NET 데스크톱 개발' 워크로드를 선택하세요."
        ),
    },
    2: {
        "label":   "Godot Engine",
        "desc":    "오픈소스 경량 2D/3D 게임 엔진 (자체 에디터 포함)",
        "packages": [
            PackageSpec("Godot Engine", "godot",
                        {"winget": "GodotEngine.GodotEngine"}),
        ],
        "launch": None,
        "note": (
            "Godot는 자체 에디터가 포함되어 있습니다.\n"
            "C# 스크립팅을 사용하려면 .NET SDK도 함께 설치하세요.\n"
            "GDScript는 별도 설치 없이 즉시 사용 가능합니다."
        ),
    },
    3: {
        "label":   "Unreal Engine",
        "desc":    "C++/Blueprint 기반 AAA 품질 3D 게임 엔진",
        "packages": [
            PackageSpec("Epic Games Launcher", "",
                        {"winget": "EpicGames.EpicGamesLauncher"}),
            PackageSpec("Visual Studio Community 2022", "",
                        {"winget": "Microsoft.VisualStudio.2022.Community"}),
        ],
        "launch": None,
        "note": (
            "Epic Games Launcher 설치 후:\n"
            "  1. Launcher를 열고 로그인합니다.\n"
            "  2. 'Unreal Engine' 탭에서 원하는 버전을 설치합니다.\n"
            "Visual Studio 설치 시 'C++를 사용한 게임 개발' 워크로드를 선택하세요.\n"
            "  (설치 용량이 크므로 충분한 디스크 공간을 확보하세요.)"
        ),
    },
    4: {
        "label":   "Pygame  (Python 2D)",
        "desc":    "Python 기반 2D 게임 라이브러리, 학습·프로토타이핑에 적합",
        "packages": [
            PackageSpec("Python 3", "python",
                        {"winget": "Python.Python.3"}),
            PackageSpec("Visual Studio Code", "code",
                        {"winget": "Microsoft.VisualStudioCode"}),
        ],
        "launch": LaunchSpec("Visual Studio Code", ["code"]),
        "post_run": ["pip", "install", "pygame"],
        "note": (
            "설치 후 터미널에서 `pip install pygame` 을 실행하세요.\n"
            "VSCode에서 'Python' 확장(ms-python.python)을 설치하면 편리합니다."
        ),
    },
}

_MATCH_KEYWORDS = [
    "게임", "game", "unity", "유니티", "godot", "고도",
    "unreal", "언리얼", "epic", "pygame",
    "게임 개발", "게임개발", "게임 엔진", "게임엔진",
    "2d 게임", "3d 게임", "인디 게임", "인디게임",
]


class GameDevScenario(Scenario):
    name = "게임 개발환경 (Windows)"
    description = "Unity / Godot / Unreal Engine / Pygame 게임 개발환경"
    supported_os = ["windows"]

    def __init__(self):
        self._engine: int | None = None

    def set_engine(self, choice: int) -> None:
        if choice in _ENGINES:
            self._engine = choice

    def get_engine_choice_message(self) -> str:
        lines = ["게임 개발환경을 구성할게요!\n어떤 엔진으로 시작할까요?\n"]
        for idx, info in _ENGINES.items():
            lines.append(f"  {idx}. {info['label']:<26} — {info['desc']}")
        lines.append("\n번호를 입력해주세요 (1~4)")
        return "\n".join(lines)

    def get_packages(self):
        return _ENGINES[self._engine]["packages"]

    def get_launch(self):
        return _ENGINES[self._engine]["launch"]

    def get_proposal_message(self) -> str:
        info = _ENGINES[self._engine]
        pkg_lines = "\n".join(f"  • {p.display_name}" for p in info["packages"])
        return (
            f"{info['label']} 게임 개발환경을 설치합니다:\n\n"
            f"{pkg_lines}\n\n"
            f"  ℹ️  {info['note']}\n\n"
            "설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in _MATCH_KEYWORDS)

    @staticmethod
    def all_engines() -> dict:
        return _ENGINES
