"""
AI 코드 에이전트 지원 테스트

- core/safety.py  : claude, codex, gemini, aider, gh 화이트리스트
- core/actions.py : SetEnvAction 파싱 / 포맷
- app.py          : SetEnvAction 환경변수명 검증
- scenarios/ai_agents.py : AIAgentsScenario 매칭·내용
"""
import json
import re
import pytest
from unittest.mock import patch, MagicMock


# ── 1. safety — AI 에이전트 실행 파일 허용 여부 ──────────────────────────────

class TestAIAgentSafety:
    from core.safety import is_safe_command, ALLOWED_EXECUTABLES

    def test_claude_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["claude", "--version"])
        assert ok

    def test_codex_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["codex", "--help"])
        assert ok

    def test_gemini_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["gemini", "--version"])
        assert ok

    def test_aider_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["aider", "--model", "claude-3-5-sonnet"])
        assert ok

    def test_gh_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["gh", "extension", "install", "github/gh-copilot"])
        assert ok

    def test_cursor_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["cursor", "."])
        assert ok

    def test_npm_install_claude_code_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["npm", "install", "-g", "@anthropic-ai/claude-code"])
        assert ok

    def test_npm_install_codex_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["npm", "install", "-g", "@openai/codex"])
        assert ok

    def test_npm_install_gemini_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["npm", "install", "-g", "@google/gemini-cli"])
        assert ok

    def test_pip_install_aider_allowed(self):
        from core.safety import is_safe_command
        ok, _ = is_safe_command(["pip", "install", "aider-chat"])
        assert ok

    def test_unknown_agent_blocked(self):
        from core.safety import is_safe_command
        ok, reason = is_safe_command(["some-unknown-agent", "--run"])
        assert not ok
        assert "허용되지 않은" in reason


# ── 2. actions — SetEnvAction 파싱 ───────────────────────────────────────────

class TestSetEnvActionParsing:

    def _parse(self, raw: list):
        from core.actions import parse_actions
        return parse_actions(raw)

    def test_set_env_parsed(self):
        from core.actions import SetEnvAction
        actions = self._parse([{
            "type": "set_env",
            "key": "ANTHROPIC_API_KEY",
            "display_name": "Anthropic API 키",
            "hint": "sk-ant-...",
        }])
        assert len(actions) == 1
        assert isinstance(actions[0], SetEnvAction)
        assert actions[0].key == "ANTHROPIC_API_KEY"
        assert actions[0].hint == "sk-ant-..."

    def test_set_env_default_hint_empty(self):
        from core.actions import SetEnvAction
        actions = self._parse([{
            "type": "set_env",
            "key": "OPENAI_API_KEY",
            "display_name": "OpenAI API 키",
        }])
        assert actions[0].hint == ""

    def test_set_env_and_run_together(self):
        from core.actions import SetEnvAction, RunAction
        actions = self._parse([
            {"type": "run", "command": ["npm", "install", "-g", "@anthropic-ai/claude-code"],
             "display_name": "Claude Code 설치"},
            {"type": "set_env", "key": "ANTHROPIC_API_KEY",
             "display_name": "API 키", "hint": "sk-ant-..."},
        ])
        assert len(actions) == 2
        assert isinstance(actions[0], RunAction)
        assert isinstance(actions[1], SetEnvAction)


# ── 3. actions — SetEnvAction 포맷 ───────────────────────────────────────────

class TestSetEnvActionFormat:

    def test_format_set_env(self):
        from core.actions import SetEnvAction, format_actions_for_display
        action = SetEnvAction(
            key="ANTHROPIC_API_KEY",
            display_name="Anthropic API 키",
            hint="sk-ant-...",
        )
        result = format_actions_for_display([action])
        assert "🔑" in result
        assert "ANTHROPIC_API_KEY" in result
        assert "Anthropic API 키" in result


# ── 4. app — SetEnvAction 환경변수명 검증 ────────────────────────────────────

_ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,59}$")
_ALLOWED_ENV_KEYS = {
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
    "OPENROUTER_API_KEY", "GITHUB_TOKEN",
}


def _validate_set_env_key(key: str):
    """app._validate_set_env 로직을 독립적으로 재현"""
    from core.actions import SetEnvAction
    action = SetEnvAction(key=key, display_name="test")
    k = action.key.strip()
    if not _ENV_KEY_RE.match(k):
        return False, f"잘못된 환경변수명 형식: '{k}'"
    if k not in _ALLOWED_ENV_KEYS:
        return False, f"허용되지 않은 환경변수: '{k}'"
    return True, ""


class TestSetEnvValidation:

    def test_anthropic_key_valid(self):
        ok, _ = _validate_set_env_key("ANTHROPIC_API_KEY")
        assert ok

    def test_openai_key_valid(self):
        ok, _ = _validate_set_env_key("OPENAI_API_KEY")
        assert ok

    def test_gemini_key_valid(self):
        ok, _ = _validate_set_env_key("GEMINI_API_KEY")
        assert ok

    def test_openrouter_key_valid(self):
        ok, _ = _validate_set_env_key("OPENROUTER_API_KEY")
        assert ok

    def test_github_token_valid(self):
        ok, _ = _validate_set_env_key("GITHUB_TOKEN")
        assert ok

    def test_unknown_key_blocked(self):
        ok, reason = _validate_set_env_key("SOME_RANDOM_KEY")
        assert not ok
        assert "허용되지 않은" in reason

    def test_lowercase_key_blocked(self):
        ok, reason = _validate_set_env_key("anthropic_api_key")
        assert not ok

    def test_shell_injection_key_blocked(self):
        ok, reason = _validate_set_env_key("A; rm -rf /")
        assert not ok

    def test_empty_key_blocked(self):
        ok, reason = _validate_set_env_key("")
        assert not ok


# ── 5. scenarios — AIAgentsScenario ─────────────────────────────────────────

class TestAIAgentsScenario:

    def _make(self):
        from scenarios.ai_agents import AIAgentsScenario
        return AIAgentsScenario()

    def test_supported_all_platforms(self):
        s = self._make()
        assert "windows" in s.supported_os
        assert "macos" in s.supported_os
        assert "linux" in s.supported_os

    def test_matches_claude_code(self):
        s = self._make()
        assert s.matches("Claude Code 설치해줘")

    def test_matches_aider(self):
        s = self._make()
        assert s.matches("aider 써보고 싶어")

    def test_matches_ai_agent_korean(self):
        s = self._make()
        assert s.matches("AI 코드 에이전트 설치")

    def test_not_matches_unrelated(self):
        s = self._make()
        assert not s.matches("파이썬 설치해줘")

    def test_all_agents_have_install_cmd(self):
        from scenarios.ai_agents import AIAgentsScenario
        for idx, info in AIAgentsScenario.all_agents().items():
            assert "install_cmd" in info, f"에이전트 {idx} install_cmd 없음"
            assert len(info["install_cmd"]) >= 2

    def test_all_agents_have_check_cmd(self):
        from scenarios.ai_agents import AIAgentsScenario
        for idx, info in AIAgentsScenario.all_agents().items():
            assert "check" in info, f"에이전트 {idx} check 없음"

    def test_set_agent_valid(self):
        s = self._make()
        s.set_agent(1)
        assert s._agent == 1

    def test_set_agent_invalid_ignored(self):
        s = self._make()
        s.set_agent(99)
        assert s._agent is None

    def test_choice_message_contains_all_names(self):
        s = self._make()
        msg = s.get_choice_message()
        for info in s.all_agents().values():
            assert info["name"] in msg

    def test_proposal_message_with_agent(self):
        s = self._make()
        s.set_agent(1)  # Claude Code
        msg = s.get_proposal_message()
        assert "Claude Code" in msg
        assert "ANTHROPIC_API_KEY" in msg

    def test_github_copilot_no_env_key(self):
        from scenarios.ai_agents import AIAgentsScenario
        agents = AIAgentsScenario.all_agents()
        copilot = agents[5]
        assert copilot["env_key"] is None  # gh auth login 방식


# ── 6. scenarios/registry — AIAgentsScenario 등록 확인 ───────────────────────

class TestRegistryAIAgents:

    def test_ai_agents_in_registry(self):
        from scenarios.registry import _ALL_SCENARIOS
        from scenarios.ai_agents import AIAgentsScenario
        assert any(isinstance(s, AIAgentsScenario) for s in _ALL_SCENARIOS)

    def test_ai_agents_listed_for_windows(self):
        from scenarios.registry import list_supported_scenarios
        from scenarios.ai_agents import AIAgentsScenario
        with patch("scenarios.registry.get_current_os", return_value="windows"):
            scenarios = list_supported_scenarios()
        assert any(isinstance(s, AIAgentsScenario) for s in scenarios)

    def test_ai_agents_listed_for_macos(self):
        from scenarios.registry import list_supported_scenarios
        from scenarios.ai_agents import AIAgentsScenario
        with patch("scenarios.registry.get_current_os", return_value="macos"):
            scenarios = list_supported_scenarios()
        assert any(isinstance(s, AIAgentsScenario) for s in scenarios)

    def test_ai_agents_listed_for_linux(self):
        from scenarios.registry import list_supported_scenarios
        from scenarios.ai_agents import AIAgentsScenario
        with patch("scenarios.registry.get_current_os", return_value="linux"):
            scenarios = list_supported_scenarios()
        assert any(isinstance(s, AIAgentsScenario) for s in scenarios)
