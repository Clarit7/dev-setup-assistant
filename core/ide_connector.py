"""
IDE 컨테이너 연동 모듈

설치된 IDE를 감지하고, devcontainer 환경과의 연결을
가능한 한 자동으로 처리합니다.

자동화 가능:
  - IDE 감지 (VS Code, Cursor)
  - 워크스페이스 폴더로 IDE 열기 → devcontainer.json 감지 토스트 자동 표시

사용자 조작 필요 (안내 제공):
  - 'Reopen in Container' 버튼 클릭
  - Dev Containers 확장 미설치 시 설치
"""

import shutil
import subprocess
from typing import List, Optional

_IDE_COMMANDS = {
    "vscode":  "code",
    "cursor":  "cursor",
}

_IDE_DISPLAY_NAMES = {
    "vscode": "VS Code",
    "cursor": "Cursor",
}


def detect_ides() -> List[str]:
    """설치된 IDE 목록을 반환합니다 (예: ["vscode", "cursor"])."""
    return [name for name, cmd in _IDE_COMMANDS.items() if shutil.which(cmd)]


def open_workspace_in_ide(workspace_path: str, ide: Optional[str] = None) -> bool:
    """
    워크스페이스를 IDE에서 엽니다.
    .devcontainer/devcontainer.json 이 있으면 VS Code/Cursor가
    자동으로 'Reopen in Container' 토스트를 우하단에 표시합니다.
    """
    installed = detect_ides()
    if not installed:
        return False

    target = ide if ide in installed else installed[0]
    cmd = _IDE_COMMANDS[target]

    try:
        subprocess.Popen([cmd, workspace_path], shell=False)
        return True
    except Exception:
        return False


def get_devcontainer_guidance(ide: str, container_name: str) -> str:
    """
    devcontainer 연결에 필요한 사용자 조작을 안내하는 메시지를 반환합니다.
    스크린샷으로 질의응답이 필요한 경우도 안내합니다.
    """
    editor = _IDE_DISPLAY_NAMES.get(ide, ide)

    if ide in ("vscode", "cursor"):
        return (
            f"**{editor}에서 컨테이너를 연결하는 방법:**\n\n"
            f"**방법 1 — 자동 토스트 (권장)**\n"
            f"{editor}가 열리면 **우측 하단에 파란 알림**이 나타납니다.\n"
            f"→ **'Reopen in Container'** 버튼을 클릭하세요.\n\n"
            f"**방법 2 — 명령 팔레트**\n"
            f"토스트가 보이지 않으면:\n"
            f"`Ctrl+Shift+P` → **Dev Containers: Reopen in Container** 입력 → Enter\n\n"
            f"**Dev Containers 확장이 없는 경우:**\n"
            f"`Ctrl+Shift+X` → **Dev Containers** 검색 → 설치 → 재시도\n\n"
            f"문제가 해결되지 않으면 **스크린샷을 찍어 채팅창에 `Ctrl+V`로 붙여넣으세요.**\n"
            f"이미지를 보고 직접 안내해드리겠습니다."
        )

    return (
        f"터미널에서 아래 명령어로 컨테이너에 진입하거나,\n"
        f"워크스페이스의 `enter-dev.bat` 파일을 실행하세요.\n\n"
        f"```\ndocker exec -it {container_name} /bin/bash\n```"
    )
