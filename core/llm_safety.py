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
  Developer-grade tools with well-known, scoped behavior.
  Examples: compilers (gcc, rustc), build tools (cmake, make, gradle), version managers,
  common package managers (npm, pip, cargo), linters, formatters, code generators,
  database CLI clients (psql, mysql, sqlite3), standard dev utilities.

"caution":
  Commands that could have significant side effects beyond the current project directory,
  modify system-wide settings, install packages globally, run remote scripts,
  require elevated privileges, or have large disk/network impact.
  Examples: npm install -g <unknown>, pip install --user <unknown>,
  system configuration tools, network scanning utilities, script runners fetching from URLs.

"dangerous":
  Commands that could damage the system, access sensitive areas, exfiltrate data,
  modify security settings, encrypt files, create backdoors, or are clearly malicious.
  Examples: rm -rf /, format C:, reg delete HKLM, taskkill /f lsass,
  powershell -EncodedCommand, curl | bash (remote execution),
  access to System32/SysWOW64, shutdown/restart commands, any obfuscated command.

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
