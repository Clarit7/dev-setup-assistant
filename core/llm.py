"""
LLM API 클라이언트

지원 프로바이더:
    anthropic  — Claude (Haiku 기본)
    openai     — GPT (gpt-4o-mini 기본)
    gemini     — Google Gemini (gemini-2.5-flash 기본, 무료 티어 있음)
    groq       — Groq (llama-3.3-70b-versatile 기본, 무료 티어 있음)
    ollama     — 로컬 모델 (API 키 불필요)

환경 변수 (.env 또는 시스템):
    LLM_PROVIDER        : anthropic | openai | gemini | groq | ollama  (기본: anthropic)
    ANTHROPIC_API_KEY   : Anthropic API 키
    OPENAI_API_KEY      : OpenAI API 키
    GEMINI_API_KEY      : Google Gemini API 키
    GROQ_API_KEY        : Groq API 키 (console.groq.com에서 발급)
    OLLAMA_BASE_URL     : Ollama 서버 URL (기본: http://localhost:11434)
    LLM_MODEL           : 모델 이름 오버라이드 (미설정 시 프로바이더 기본값 사용)
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterator, List, Optional

if TYPE_CHECKING:
    from ui.image_handler import ImageAttachment

# .env 파일 자동 로드 — 모듈 위치 기준 절대 경로 사용
try:
    from dotenv import load_dotenv
    from pathlib import Path as _Path
    load_dotenv(_Path(__file__).parent.parent / ".env", override=True)
except ImportError:
    pass

from .actions import Action, parse_actions

# ── 기본 시스템 프롬프트 ──────────────────────────────────────────────────────

_BASE_SYSTEM_PROMPT = """\
You are a developer environment setup assistant.
Your job: help users install and configure the right development tools,
including Docker-based container environments.

## RESPONSE FORMAT
Always respond with ONLY valid JSON — no markdown fences, no extra text.

{
    "topic_valid": true,
    "message": "Korean message shown to user (markdown OK)",
    "ready_to_install": false,
    "actions": []
}

Set ready_to_install to true ONLY when you have a complete plan and want
to propose it to the user. Keep it false while gathering information.

## TOPIC GUARD
This assistant answers questions related to:
- Installing or configuring development tools (Node.js, Python, Git, Docker, etc.)
- Setting up programming/dev environments on any OS
- Container/Docker-based dev environments
- IDE configuration and extensions
- Package managers and build tools
- Troubleshooting dev environment issues (including screenshot analysis)
- Wanting to develop / build any kind of software project (web, mobile, game, CLI, AI, etc.)
- Choosing a tech stack, language, or framework for a project
- Any developer question that can naturally lead to environment setup suggestions

When the user expresses interest in developing something (e.g. "I want to build a game",
"I'm thinking of starting a React project", "which language should I use for X"),
treat it as ON-TOPIC and proactively suggest the relevant environment setup.

If the user asks about ANYTHING clearly unrelated to software development or tech
(writing essays, translation, general knowledge, math homework, entertainment,
personal advice, cooking, etc.), you MUST:
1. Set topic_valid=false
2. Write a single polite refusal sentence in message — do NOT answer the question
3. Keep ready_to_install=false and actions=[]

When in doubt, lean toward topic_valid=true and steer the conversation toward
what dev environment the user might need.

When topic_valid=true (normal case), omit it or set it to true.

## ACTION TYPES (only when ready_to_install is true)

### Package install (winget)
{"type": "install", "package_id": "OpenJS.NodeJS",
 "display_name": "Node.js", "check_command": "node"}

### Run command
{"type": "run", "command": ["npm", "install", "-g", "typescript"],
 "display_name": "TypeScript 글로벌 설치"}

### Launch app
{"type": "launch", "command": ["code"],
 "display_name": "VS Code 실행"}

### Container setup (Docker dev environment)
{"type": "container_setup",
 "image": "node:18-bullseye",
 "container_name": "my-node-dev",
 "workspace_path": "",
 "ports": ["3000:3000"],
 "display_name": "Node.js 개발 컨테이너"}

container_setup notes:
- Leave workspace_path empty — the app will use a sensible default.
- The app auto-generates: .devcontainer/devcontainer.json, enter-dev.bat,
  Windows Terminal profile, and opens VS Code/Cursor with the workspace.
- Add a "launch" action for code/cursor AFTER container_setup so the IDE
  is opened automatically.
- Use container_setup when the user explicitly wants Docker/containers.
- Ask the user: which stack (Node, Python, Go …) and which ports are needed.

## ALLOWED EXECUTABLES — ONLY these in "run" and "launch" actions
winget, npm, npx, node, yarn, pnpm, pip, pip3, python, python3,
git, code, cursor, cargo, rustup, go, dotnet, deno, bun,
mvn, gradle, java, javac, choco,
docker, docker-compose, podman, wsl

## COMMON WINGET PACKAGE IDs
- OpenJS.NodeJS            Node.js LTS
- Python.Python.3          Python 3
- Microsoft.VisualStudioCode  VS Code
- Anysphere.Cursor         Cursor (AI editor)
- Git.Git                  Git
- GoLang.Go                Go
- Rustlang.Rustup          Rust
- Microsoft.DotNet.SDK.8   .NET 8 SDK
- EclipseAdoptium.Temurin.21.JDK  Java 21
- Docker.DockerDesktop     Docker Desktop
- Yarn.Yarn                Yarn
- PNPM.PNPM                pnpm

## SAFETY RULES — NEVER violate
- No access to System32, SysWOW64, %windir%
- No: format, diskpart, fdisk, dd
- No force-delete: rm -rf, del /f, del /s
- No: reg delete, bcdedit
- No PowerShell -EncodedCommand
- No shell pipe injection: | bash, | sh, | cmd, | powershell
- No: shutdown, restart
- No executables not in the ALLOWED list above

## WORKFLOW
1. Greet and ask what dev environment they need
2. Ask clarifying questions if needed (stack, editor preference, containers?)
3. When plan is clear: set ready_to_install=true with actions list
4. The app will ask user to confirm, then execute the actions
5. After installation succeeds, guide next steps
6. If user shares a screenshot showing an error, analyze it and provide
   specific step-by-step instructions to resolve the issue.

Always respond in Korean. Be friendly and concise.
"""

SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT  # 하위 호환성 유지


def build_system_prompt(env_context: str = "", history_context: str = "") -> str:
    """A/F 컨텍스트를 포함한 완전한 시스템 프롬프트를 생성합니다."""
    parts = [_BASE_SYSTEM_PROMPT]
    if env_context:
        parts.append(env_context)
    if history_context:
        parts.append(history_context)
    return "\n\n".join(parts)


# ── 응답 모델 ─────────────────────────────────────────────────────────────────

@dataclass
class LLMResponse:
    message: str
    ready_to_install: bool = False
    topic_valid: bool = True   # False = 개발환경 외 주제, 앱이 응답 교체
    actions: List[Action] = field(default_factory=list)
    raw: str = ""


# ── LLM 클라이언트 ────────────────────────────────────────────────────────────

class LLMClient:
    """멀티 프로바이더 LLM 클라이언트 (스트리밍 지원)"""

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
        self.history: List[dict] = []
        self._env_context: str = ""
        self._history_context: str = ""
        self._pending_image: Optional["ImageAttachment"] = None
        self._init_provider()

    # ── 컨텍스트 설정 (A/F) ──────────────────────────────────────────────────

    def set_context(self, env_context: str = "", history_context: str = ""):
        """시스템 환경 감지 결과 및 설치 이력을 LLM 컨텍스트로 설정합니다."""
        self._env_context = env_context
        self._history_context = history_context

    def _get_system_prompt(self) -> str:
        return build_system_prompt(self._env_context, self._history_context)

    # ── 프로바이더 초기화 ─────────────────────────────────────────────────────

    def _init_provider(self):
        if self.provider == "anthropic":
            self._init_anthropic()
        elif self.provider == "openai":
            self._init_openai()
        elif self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "groq":
            self._init_groq()
        elif self.provider == "ollama":
            self._init_ollama()
        else:
            raise ValueError(
                f"지원하지 않는 LLM 프로바이더: '{self.provider}'\n"
                "사용 가능: anthropic, openai, gemini, groq, ollama"
            )

    def _init_anthropic(self):
        try:
            import anthropic  # noqa: F401
        except ImportError:
            raise ImportError("pip install anthropic  을 실행하세요.")
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요."
            )
        import anthropic as _ant
        self._client = _ant.Anthropic(api_key=api_key)
        self.model = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")

    def _init_openai(self):
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError("pip install openai  을 실행하세요.")
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 OPENAI_API_KEY=sk-... 를 추가하세요."
            )
        import openai as _oai
        self._client = _oai.OpenAI(api_key=api_key)
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def _init_gemini(self):
        try:
            import google.generativeai  # noqa: F401
        except ImportError:
            raise ImportError("pip install google-generativeai  을 실행하세요.")
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 GEMINI_API_KEY=AIza... 를 추가하세요."
            )
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = os.getenv("LLM_MODEL", "gemini-2.5-flash-preview-04-17")
        self._client = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=_BASE_SYSTEM_PROMPT,
        )

    def _init_groq(self):
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ImportError("pip install openai  을 실행하세요.")
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY 환경 변수가 설정되지 않았습니다.\n"
                ".env 파일에 GROQ_API_KEY=gsk_... 를 추가하세요.\n"
                "API 키 발급: https://console.groq.com/keys"
            )
        import openai as _oai
        self._client = _oai.OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        self.model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    def _init_ollama(self):
        try:
            import requests  # noqa: F401
        except ImportError:
            raise ImportError("pip install requests  을 실행하세요.")
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = os.getenv("LLM_MODEL", "mistral")
        self._client = None

    # ── 일반 전송 ────────────────────────────────────────────────────────────

    def send(self, user_message: str) -> LLMResponse:
        """유저 메시지를 LLM에 전송하고 파싱된 응답을 반환합니다."""
        self.history.append({"role": "user", "content": user_message})
        system = self._get_system_prompt()

        if self.provider == "anthropic":
            raw = self._call_anthropic(system)
        elif self.provider in ("openai", "groq"):
            raw = self._call_openai(system)
        elif self.provider == "gemini":
            raw = self._call_gemini()
        else:
            raw = self._call_ollama(system)

        self.history.append({"role": "assistant", "content": raw})
        return self._parse_response(raw)

    def send_once(self, user_message: str, system_override: str) -> str:
        """
        히스토리를 건드리지 않는 단발성 LLM 호출입니다.
        안전성 검사 등 내부 용도에만 사용합니다.
        """
        if self.provider == "gemini":
            return self._call_gemini_once(system_override, user_message)

        saved_history = self.history
        self.history = [{"role": "user", "content": user_message}]
        try:
            if self.provider == "anthropic":
                return self._call_anthropic(system_override)
            elif self.provider in ("openai", "groq"):
                return self._call_openai(system_override)
            else:  # ollama
                return self._call_ollama(system_override)
        finally:
            self.history = saved_history

    # ── B. 스트리밍 전송 ──────────────────────────────────────────────────────

    def send_stream(
        self,
        user_message: str,
        on_chunk: Callable[[str], None],
        image: Optional["ImageAttachment"] = None,
    ) -> LLMResponse:
        """
        스트리밍 LLM 호출.

        JSON 응답의 'message' 필드 내용만 실시간으로 on_chunk 콜백에 전달합니다.
        image를 전달하면 비전 모드로 호출합니다 (히스토리에는 텍스트만 저장).
        완료 후 파싱된 LLMResponse를 반환합니다.
        """
        self.history.append({"role": "user", "content": user_message})
        system = self._get_system_prompt()
        self._pending_image = image

        try:
            raw = self._stream_with_callback(system, on_chunk)
        except Exception:
            self.history.pop()
            self._pending_image = None
            return self.send(user_message)
        finally:
            self._pending_image = None

        self.history.append({"role": "assistant", "content": raw})
        return self._parse_response(raw)

    def _stream_with_callback(self, system: str, on_chunk: Callable[[str], None]) -> str:
        """
        스트리밍 청크를 처리하고 전체 원시 텍스트를 반환합니다.

        JSON의 "message" 값만 실시간으로 on_chunk에 전달합니다.
        이스케이프 시퀀스(\\n, \\t, \\")를 실제 문자로 변환합니다.
        """
        accumulated = ""
        msg_start = -1    # "message": " 이후 시작 위치
        emitted = 0       # 이미 emit한 위치
        msg_done = False

        for chunk in self._iter_raw_chunks(system):
            accumulated += chunk

            if msg_done:
                continue

            # "message" 필드 시작 탐색
            if msg_start == -1:
                m = re.search(r'"message"\s*:\s*"', accumulated)
                if m:
                    msg_start = m.end()
                    emitted = msg_start

            if msg_start == -1:
                continue

            # 새로 추가된 범위에서 문자 emit
            buf = []
            i = emitted
            while i < len(accumulated):
                c = accumulated[i]
                if c == "\\":
                    if i + 1 < len(accumulated):
                        nxt = accumulated[i + 1]
                        escape_map = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "r": "\r"}
                        buf.append(escape_map.get(nxt, nxt))
                        i += 2
                    else:
                        # 청크 경계에서 \가 끊긴 경우 — 다음 청크를 기다림
                        break
                elif c == '"':
                    msg_done = True
                    i += 1
                    break
                else:
                    buf.append(c)
                    i += 1

            emitted = i
            if buf:
                on_chunk("".join(buf))

        return accumulated

    # ── 스트리밍 이터레이터 (프로바이더별) ───────────────────────────────────

    def _iter_raw_chunks(self, system: str) -> Iterator[str]:
        """각 프로바이더의 스트리밍 API를 통해 텍스트 청크를 yield합니다."""
        img = self._pending_image
        if self.provider == "anthropic":
            yield from self._iter_anthropic_stream(system, img)
        elif self.provider in ("openai", "groq"):
            yield from self._iter_openai_stream(system, img)
        elif self.provider == "gemini":
            yield from self._iter_gemini_stream(img)
        else:
            yield from self._iter_ollama_stream(system, img)

    def _iter_anthropic_stream(self, system: str, image=None) -> Iterator[str]:
        messages = list(self.history)
        if image:
            last = messages[-1]
            messages[-1] = {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image.media_type,
                            "data": image.base64_data,
                        },
                    },
                    {"type": "text", "text": last["content"]},
                ],
            }
        with self._client.messages.stream(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _iter_openai_stream(self, system: str, image=None) -> Iterator[str]:
        messages = [{"role": "system", "content": system}]
        for msg in self.history[:-1]:
            messages.append(msg)
        last = self.history[-1]
        if image:
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": last["content"]},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image.media_type};base64,{image.base64_data}"
                        },
                    },
                ],
            })
        else:
            messages.append(last)

        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=2048,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def _iter_gemini_stream(self, image=None) -> Iterator[str]:
        chat = self._client.start_chat(history=[])
        for msg in self.history[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            chat.history.append({"role": role, "parts": [msg["content"]]})
        last_msg = self.history[-1]["content"]
        if image:
            import base64 as _b64
            image_part = {
                "mime_type": image.media_type,
                "data": _b64.b64decode(image.base64_data),
            }
            send_parts = [last_msg, image_part]
        else:
            send_parts = last_msg
        response = chat.send_message(send_parts, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    def _iter_ollama_stream(self, system: str, image=None) -> Iterator[str]:
        import requests
        messages = [{"role": "system", "content": system}]
        for msg in self.history[:-1]:
            messages.append(msg)
        last = dict(self.history[-1])
        if image:
            last["images"] = [image.base64_data]
        messages.append(last)
        with requests.post(
            f"{self._base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": True},
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    # ── 비스트리밍 API 호출 (send() 폴백용) ──────────────────────────────────

    def _call_anthropic(self, system: str) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=self.history,
        )
        return response.content[0].text

    def _call_openai(self, system: str) -> str:
        messages = [{"role": "system", "content": system}] + self.history
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def _call_gemini(self) -> str:
        chat = self._client.start_chat(history=[])
        for msg in self.history[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            chat.history.append({"role": role, "parts": [msg["content"]]})
        last_msg = self.history[-1]["content"]
        response = chat.send_message(last_msg)
        return response.text

    def _call_gemini_once(self, system_override: str, user_message: str) -> str:
        """시스템 프롬프트 오버라이드로 단발성 Gemini 호출을 수행합니다."""
        import google.generativeai as genai
        temp_client = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_override,
        )
        chat = temp_client.start_chat(history=[])
        response = chat.send_message(user_message)
        return response.text

    def _call_ollama(self, system: str) -> str:
        import requests
        messages = [{"role": "system", "content": system}] + self.history
        resp = requests.post(
            f"{self._base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    # ── 응답 파싱 ────────────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> LLMResponse:
        json_str = self._extract_json(raw)
        if not json_str:
            return LLMResponse(message=raw, raw=raw)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return LLMResponse(message=raw, raw=raw)
        actions = parse_actions(data.get("actions") or [])
        return LLMResponse(
            message=data.get("message", raw),
            ready_to_install=bool(data.get("ready_to_install", False)),
            topic_valid=bool(data.get("topic_valid", True)),
            actions=actions,
            raw=raw,
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[str]:
        m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if m:
            return m.group(1)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start: end + 1]
        return None

    # ── 유틸 ─────────────────────────────────────────────────────────────────

    def reset(self):
        self.history.clear()

    @property
    def provider_label(self) -> str:
        labels = {
            "anthropic": f"Claude ({self.model})",
            "openai":    f"OpenAI ({self.model})",
            "gemini":    f"Gemini ({self.model})",
            "groq":      f"Groq ({self.model})",
            "ollama":    f"Ollama/{self.model} (로컬)",
        }
        return labels.get(self.provider, self.provider)
