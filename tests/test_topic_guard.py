"""
주제 가드(topic_valid) 테스트

LLM 응답의 topic_valid 필드가 LLMResponse에 올바르게 파싱되는지,
그리고 기본값/경계값이 올바르게 처리되는지 검증합니다.
(실제 LLM API 호출 없이 _parse_response 단위 테스트)
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from core.llm import LLMResponse, LLMClient


# ── _parse_response 단위 테스트 ──────────────────────────────────────────────

class TestTopicValidParsing:
    """LLMClient._parse_response 가 topic_valid를 올바르게 읽는지 검증합니다."""

    def _make_client(self):
        """API 키 없이 LLMClient 인스턴스를 만듭니다."""
        with patch.object(LLMClient, "_init_provider"):
            client = LLMClient.__new__(LLMClient)
            client.provider = "anthropic"
            client.history = []
            client._env_context = ""
            client._history_context = ""
            client._pending_image = None
        return client

    def _raw(self, **kwargs) -> str:
        base = {
            "topic_valid": True,
            "message": "테스트 메시지",
            "ready_to_install": False,
            "actions": [],
        }
        base.update(kwargs)
        return json.dumps(base)

    # ── topic_valid 파싱 ──────────────────────────────────────────────────

    def test_topic_valid_true_parsed(self):
        client = self._make_client()
        resp = client._parse_response(self._raw(topic_valid=True))
        assert resp.topic_valid is True

    def test_topic_valid_false_parsed(self):
        client = self._make_client()
        resp = client._parse_response(self._raw(topic_valid=False))
        assert resp.topic_valid is False

    def test_topic_valid_defaults_to_true_when_absent(self):
        """LLM이 topic_valid를 생략한 경우 True로 간주해야 합니다."""
        client = self._make_client()
        raw = json.dumps({"message": "안녕", "ready_to_install": False, "actions": []})
        resp = client._parse_response(raw)
        assert resp.topic_valid is True

    def test_topic_valid_false_does_not_block_message_parsing(self):
        """topic_valid=False여도 message 필드는 파싱해야 합니다 (앱에서 사용 안 하지만)."""
        client = self._make_client()
        resp = client._parse_response(
            self._raw(topic_valid=False, message="거부 메시지")
        )
        assert resp.message == "거부 메시지"

    def test_topic_valid_false_forces_ready_to_install_irrelevant(self):
        """topic_valid=False일 때 ready_to_install이 True여도 앱이 무시해야 합니다.
        파싱 자체는 그대로 하고, 앱 레이어에서 topic_valid를 먼저 확인합니다."""
        client = self._make_client()
        resp = client._parse_response(
            self._raw(topic_valid=False, ready_to_install=True)
        )
        assert resp.topic_valid is False
        assert resp.ready_to_install is True  # 파싱은 그대로, 앱에서 필터링

    def test_non_json_response_defaults_topic_valid_true(self):
        """JSON 파싱 실패 시 topic_valid는 True(통과)로 기본값을 가져야 합니다."""
        client = self._make_client()
        resp = client._parse_response("일반 텍스트 응답")
        assert resp.topic_valid is True

    def test_malformed_json_defaults_topic_valid_true(self):
        client = self._make_client()
        resp = client._parse_response("{topic_valid: false, broken json")
        assert resp.topic_valid is True

    # ── LLMResponse 기본값 ────────────────────────────────────────────────

    def test_llmresponse_default_topic_valid_is_true(self):
        resp = LLMResponse(message="test")
        assert resp.topic_valid is True

    def test_llmresponse_topic_valid_can_be_set_false(self):
        resp = LLMResponse(message="test", topic_valid=False)
        assert resp.topic_valid is False

    # ── actions가 비어 있어야 함 ──────────────────────────────────────────

    def test_topic_invalid_response_has_no_actions(self):
        """LLM이 지시를 따랐다면 topic_valid=False일 때 actions는 비어 있어야 합니다."""
        client = self._make_client()
        resp = client._parse_response(
            self._raw(topic_valid=False, actions=[])
        )
        assert resp.actions == []


# ── 시스템 프롬프트에 TOPIC GUARD 섹션 포함 여부 ──────────────────────────────

class TestSystemPromptContainsTopicGuard:
    """_BASE_SYSTEM_PROMPT에 주제 가드 관련 지시가 포함되어 있는지 확인합니다."""

    def test_prompt_contains_topic_valid_field(self):
        from core.llm import _BASE_SYSTEM_PROMPT
        assert "topic_valid" in _BASE_SYSTEM_PROMPT

    def test_prompt_instructs_false_for_off_topic(self):
        from core.llm import _BASE_SYSTEM_PROMPT
        assert "topic_valid=false" in _BASE_SYSTEM_PROMPT or \
               "topic_valid: false" in _BASE_SYSTEM_PROMPT.lower()

    def test_prompt_defines_allowed_topics(self):
        from core.llm import _BASE_SYSTEM_PROMPT
        # 허용 주제 키워드가 명시되어 있어야 함
        assert "development tools" in _BASE_SYSTEM_PROMPT.lower() or \
               "dev environment" in _BASE_SYSTEM_PROMPT.lower() or \
               "TOPIC GUARD" in _BASE_SYSTEM_PROMPT

    def test_prompt_mentions_refusal_behavior(self):
        from core.llm import _BASE_SYSTEM_PROMPT
        # 거부 동작이 지시되어 있어야 함
        assert "refusal" in _BASE_SYSTEM_PROMPT.lower() or \
               "do NOT answer" in _BASE_SYSTEM_PROMPT or \
               "MUST" in _BASE_SYSTEM_PROMPT
