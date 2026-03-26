"""
시나리오: AI 코드 에이전트 설치

지원: Windows / macOS / Linux (npm·pip 공통)

지원 에이전트:
  1. Claude Code     — Anthropic 공식 CLI  (npm)
  2. OpenAI Codex CLI — OpenAI CLI  (npm)
  3. Gemini CLI      — Google 공식 CLI  (npm)
  4. Aider           — 오픈소스 AI 페어 프로그래머  (pip)
  5. GitHub Copilot CLI — gh extension  (gh CLI 필요)
"""
from .base import Scenario, PackageSpec, LaunchSpec

# ── 에이전트 정보 ────────────────────────────────────────────────────────────
_AGENTS: dict = {
    1: {
        "name":        "Claude Code",
        "vendor":      "Anthropic",
        "install_cmd": ["npm", "install", "-g", "@anthropic-ai/claude-code"],
        "check":       "claude",
        "env_key":     "ANTHROPIC_API_KEY",
        "env_hint":    "sk-ant-...",
        "note":        "`claude` 명령으로 실행합니다.",
    },
    2: {
        "name":        "OpenAI Codex CLI",
        "vendor":      "OpenAI",
        "install_cmd": ["npm", "install", "-g", "@openai/codex"],
        "check":       "codex",
        "env_key":     "OPENAI_API_KEY",
        "env_hint":    "sk-...",
        "note":        "`codex` 명령으로 실행합니다.",
    },
    3: {
        "name":        "Gemini CLI",
        "vendor":      "Google",
        "install_cmd": ["npm", "install", "-g", "@google/gemini-cli"],
        "check":       "gemini",
        "env_key":     "GEMINI_API_KEY",
        "env_hint":    "AIza...",
        "note":        "`gemini` 명령으로 실행합니다.",
    },
    4: {
        "name":        "Aider",
        "vendor":      "aider-chat",
        "install_cmd": ["pip", "install", "aider-chat"],
        "check":       "aider",
        "env_key":     "ANTHROPIC_API_KEY",   # 기본값 — 다른 프로바이더도 지원
        "env_hint":    "sk-ant-... (또는 OPENAI_API_KEY 등 다른 키)",
        "note":        "`aider` 명령으로 실행합니다.",
    },
    5: {
        "name":        "GitHub Copilot CLI",
        "vendor":      "GitHub",
        # gh CLI(GitHub.cli)가 먼저 설치돼 있어야 합니다.
        "install_cmd": ["gh", "extension", "install", "github/gh-copilot"],
        "check":       "gh",
        "env_key":     None,   # gh auth login 으로 인증 (브라우저 OAuth)
        "env_hint":    "",
        "note":        "설치 후 `gh auth login`으로 인증하세요.",
    },
}

_MATCH_KEYWORDS = [
    "ai 에이전트", "ai에이전트", "코드 에이전트", "코드에이전트",
    "claude code", "codex", "gemini cli", "aider", "copilot cli",
    "ai agent", "code agent",
]


class AIAgentsScenario(Scenario):
    """AI 코드 에이전트 설치 시나리오 (에이전트 선택 → 설치 → API 키 설정)"""

    name = "AI 코드 에이전트"
    description = "Claude Code / Codex CLI / Gemini CLI / Aider / GitHub Copilot CLI 설치"
    supported_os = ["windows", "macos", "linux"]

    def __init__(self):
        self._agent: int | None = None

    # ── 선택 ─────────────────────────────────────────────────────────────────

    def set_agent(self, choice: int) -> None:
        """1~5 중 에이전트 선택"""
        if choice in _AGENTS:
            self._agent = choice

    def get_choice_message(self) -> str:
        lines = ["어떤 AI 코드 에이전트를 설치할까요?\n"]
        for idx, info in _AGENTS.items():
            lines.append(f"  {idx}. {info['name']}  ({info['vendor']})")
        lines.append("\n번호를 입력해주세요 (1~5)")
        return "\n".join(lines)

    # ── Scenario 인터페이스 ───────────────────────────────────────────────────

    def get_packages(self) -> list:
        """npm/pip 설치는 RunAction으로 처리하므로 PackageSpec은 반환하지 않습니다."""
        return []

    def get_launch(self):
        return None

    def get_proposal_message(self) -> str:
        if self._agent is None:
            return self.get_choice_message()
        info = _AGENTS[self._agent]
        lines = [
            f"{info['name']} ({info['vendor']}) 을 설치합니다:\n",
            f"  설치 명령어: {' '.join(info['install_cmd'])}",
        ]
        if info["env_key"]:
            lines.append(f"  필요 환경변수: {info['env_key']}  (예: {info['env_hint']})")
        lines.append(f"\n  {info['note']}")
        lines.append("\n설치할까요? (y/N)")
        return "\n".join(lines)

    def matches(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(kw in lower for kw in _MATCH_KEYWORDS)

    # ── 헬퍼 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def all_agents() -> dict:
        """전체 에이전트 정보 반환 (테스트·LLM 컨텍스트 용)"""
        return _AGENTS
