"""
시나리오: Windows에서 JavaScript 타이머 앱 개발환경 구성

지원: Windows (winget)
설치: Node.js, Visual Studio Code
실행: Visual Studio Code
"""
from ..base import Scenario, PackageSpec, LaunchSpec


class JSTimerScenario(Scenario):
    name = "JS 타이머 앱 (Windows)"
    description = "윈도우에서 동작하는 JavaScript 타이머 앱 개발환경"
    supported_os = ["windows"]

    def get_packages(self):
        return [
            PackageSpec(
                display_name="Node.js",
                check_command="node",
                package_ids={
                    "winget": "OpenJS.NodeJS",
                    # "brew": "node",        # macOS 지원 시 추가
                    # "apt": "nodejs",       # Linux 지원 시 추가
                },
            ),
            PackageSpec(
                display_name="Visual Studio Code",
                check_command="code",
                package_ids={
                    "winget": "Microsoft.VisualStudioCode",
                    # "brew": "--cask visual-studio-code",
                    # "snap": "code --classic",
                },
            ),
        ]

    def get_launch(self):
        return LaunchSpec(
            display_name="Visual Studio Code",
            command=["code"],
        )

    def get_proposal_message(self):
        return (
            "윈도우에서 동작하는 타이머 앱을 만들려면 다음이 필요합니다:\n\n"
            "  1. Node.js  —  JavaScript 실행 환경\n"
            "  2. Visual Studio Code  —  코드 편집기\n\n"
            "지금 바로 설치할까요? (y/N)"
        )

    def matches(self, user_input: str) -> bool:
        keywords = ["타이머", "timer"]
        return any(kw in user_input.lower() for kw in keywords)
