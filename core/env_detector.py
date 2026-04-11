"""
A. 시스템 환경 자동 감지

앱 시작 시 이미 설치된 개발 도구를 감지하여 LLM 컨텍스트로 제공합니다.
LLM이 "이미 Node.js가 설치되어 있으니 건너뛰겠습니다" 같은 스마트한 응답이 가능해집니다.
"""

import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DetectedTool:
    name: str
    command: str
    version: Optional[str]
    installed: bool


# (이름, which 명령어, 버전 확인 명령어 or None)
# None: GUI 앱이라 실행하면 창이 열릴 수 있으므로 which 확인만 함
_TOOLS = [
    ("Node.js",    "node",    ["node",   "--version"]),
    ("npm",        "npm",     ["npm",    "--version"]),
    ("Python",     "python",  ["python", "--version"]),
    ("Git",        "git",     ["git",    "--version"]),
    ("VS Code",    "code",    None),   # code --version 이 VS Code 창을 열 수 있음
    ("Cursor",     "cursor",  None),   # 동일
    ("Yarn",       "yarn",    ["yarn",   "--version"]),
    ("pnpm",       "pnpm",    ["pnpm",   "--version"]),
    ("Cargo/Rust", "cargo",   ["cargo",  "--version"]),
    ("Go",         "go",      ["go",     "version"]),
    ("Java",       "java",    ["java",   "-version"]),
    ("Docker",     "docker",  ["docker", "--version"]),
    ("Deno",       "deno",    ["deno",   "--version"]),
    ("Bun",        "bun",     ["bun",    "--version"]),
    ("WSL",        "wsl",     None),
]


def _get_version(cmd: List[str]) -> Optional[str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        output = (result.stdout or result.stderr or "").strip()
        first_line = output.split("\n")[0][:60]
        return first_line if first_line else None
    except Exception:
        return None


def detect_environment() -> List[DetectedTool]:
    """현재 PC에 설치된 개발 도구를 감지합니다."""
    results = []
    for name, cmd, version_cmd in _TOOLS:
        installed = shutil.which(cmd) is not None
        if not installed:
            version = None
        elif version_cmd is None:
            version = "설치됨"   # GUI 앱 — 실행 없이 존재만 확인
        else:
            version = _get_version(version_cmd)
        results.append(DetectedTool(name=name, command=cmd, version=version, installed=installed))
    return results


def format_for_llm(tools: List[DetectedTool], container_context: str = "") -> str:
    """감지 결과를 LLM 시스템 프롬프트용 텍스트로 변환합니다."""
    installed = [t for t in tools if t.installed]
    not_installed = [t for t in tools if not t.installed]

    lines = ["## 현재 PC 설치 환경 (앱 시작 시 자동 감지)"]
    if installed:
        lines.append("설치됨:")
        for t in installed:
            ver = f" ({t.version})" if t.version else ""
            lines.append(f"  ✓ {t.name}{ver}")
    if not_installed:
        lines.append("미설치:")
        lines.append(f"  ✗ {', '.join(t.name for t in not_installed)}")

    lines.append("이미 설치된 항목은 재설치하지 말고 건너뛰세요.")

    if container_context:
        lines.append("")
        lines.append(container_context)

    return "\n".join(lines)
