"""
LLM 기반 동적 명령어 안전성 검사

화이트리스트에 없는 명령어를 LLM에게 3단계로 평가합니다:
  SAFE      — 자동 허용
  CAUTION   — 사용자에게 묻고, 허가 시 세션 화이트리스트에 추가
  DANGEROUS — 무조건 차단 (블랙리스트 추가 없음)

블랙리스트에 포함된 명령어는 LLM 판정 결과와 무관하게 항상 차단됩니다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .llm import LLMClient

# ── 세션 캐시 (앱 종료 시 소멸) ──────────────────────────────────────────────
_SESSION_CACHE: dict = {}   # cmd_str → SafetyLevel

# ── LLM 안전성 평가 전용 시스템 프롬프트 ─────────────────────────────────────
_SAFETY_SYSTEM_PROMPT = """\
You are a command security evaluator for a Windows developer environment setup application.
Your job is to evaluate whether a shell command is safe to execute on a developer's machine.

RESPONSE FORMAT: Return ONLY valid JSON — no markdown fences, no extra text.
{"level": "safe" | "caution" | "dangerous", "reason": "brief Korean explanation (1~2 sentences)"}

EVALUATION CRITERIA:

"safe":
  Developer tools with well-known, clearly scoped behavior.
  - Compilers / build tools: gcc, clang, cmake, make, gradle, mvn, cargo build, go build
  - Package managers operating on a project: npm install, pip install, cargo add
  - Version managers: nvm use, volta install, pyenv install, rbenv install
  - Code quality tools: eslint, prettier, black, mypy, flake8, ruff
  - Database clients (read/write, not destructive admin): psql, mysql, sqlite3, mongosh
  - Standard dev CLI operations: git clone/pull/push, code --install-extension,
    docker build/run/pull, kubectl get/apply, helm install
  - Downloading a file with curl/wget to a local path (NOT piping to a shell)
  - Running a LOCALLY DOWNLOADED installer (.exe, .msi) with silent/quiet flags
    — this is standard practice for dev tools without a package manager entry

"caution":
  Commands with wider system impact that a developer might reasonably intend but
  should confirm. When in doubt between "safe" and "caution", choose "caution".
  - Global package installs: npm install -g, pip install --user, gem install --user
  - System-wide configuration changes (PATH, env vars via registry, etc.)
  - Running local shell scripts (.sh, .bat, .ps1) whose content is unknown
  - powershell -Command or pwsh -Command running an installer or system change
  - Large-scale operations: winget upgrade --all, docker system prune -a
  - Network-intensive operations: pulling large images, cloning huge repos

"dangerous":
  ONLY commands that could cause IRREVERSIBLE DAMAGE or security compromise.
  Be SPECIFIC — do not classify general installer or dev tool usage as dangerous.
  - Disk/filesystem destruction: rm -rf /, format C:, del /f /s /q C:\\
  - Piping remote content directly into a shell: curl ... | bash, iwr ... | iex
  - Obfuscated execution: powershell -EncodedCommand, -WindowStyle Hidden -EncodedCommand
  - Security setting changes: reg delete HKLM\\..., bcdedit, netsh advfirewall set allprofiles off
  - Killing critical system processes: taskkill /f /im lsass.exe, /im svchost.exe
  - Accessing sensitive system paths: System32, SysWOW64, %WINDIR%
  - Shutdown/restart: shutdown /s, shutdown /r
  - Clearly malicious patterns: data exfiltration, credential harvesting, backdoors

DEFAULT RULE: If a command looks like a standard developer environment setup step
(installing a tool, building code, configuring a dev environment), lean toward
"safe" or "caution" — NOT "dangerous". Reserve "dangerous" for genuinely destructive
or malicious commands.

Always write the "reason" field in Korean.
"""


class SafetyLevel(Enum):
    SAFE = "safe"
    CAUTION = "caution"
    DANGEROUS = "dangerous"


@dataclass
class SafetyResult:
    level: SafetyLevel
    reason: str
    cached: bool = False


def check_command_safety(
    cmd: List[str],
    llm_client: "LLMClient",
) -> SafetyResult:
    """
    명령어를 LLM으로 평가합니다.
    세션 캐시가 있으면 LLM 호출 없이 바로 반환합니다.

    주의: 블랙리스트 검사는 이 함수 밖(app.py)에서 먼저 수행해야 합니다.
    """
    if not cmd:
        return SafetyResult(SafetyLevel.DANGEROUS, "빈 명령어입니다.")

    cmd_str = " ".join(cmd)

    # 세션 캐시 확인
    if cmd_str in _SESSION_CACHE:
        return SafetyResult(_SESSION_CACHE[cmd_str], "캐시된 결과입니다.", cached=True)

    try:
        raw = llm_client.send_once(
            user_message=f"다음 명령어를 평가해주세요: {cmd_str}",
            system_override=_SAFETY_SYSTEM_PROMPT,
        )
        result = _parse_safety_response(raw)
    except Exception as e:
        # LLM 호출 실패 시 CAUTION으로 처리 (사용자에게 판단 위임)
        result = SafetyResult(
            SafetyLevel.CAUTION,
            f"안전성 검사 중 오류가 발생했습니다 — 주의로 처리합니다. ({e})",
        )

    # 세션 캐시 저장
    _SESSION_CACHE[cmd_str] = result.level
    return result


def _parse_safety_response(raw: str) -> SafetyResult:
    """LLM 응답에서 JSON을 추출하고 SafetyResult로 변환합니다."""
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        return SafetyResult(SafetyLevel.CAUTION, "응답 파싱 실패 — 주의로 처리합니다.")

    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return SafetyResult(SafetyLevel.CAUTION, "JSON 파싱 실패 — 주의로 처리합니다.")

    level_str = data.get("level", "caution").lower()
    reason = data.get("reason", "")

    try:
        level = SafetyLevel(level_str)
    except ValueError:
        level = SafetyLevel.CAUTION
        reason = f"알 수 없는 레벨 '{level_str}' — 주의로 처리합니다."

    return SafetyResult(level, reason)
