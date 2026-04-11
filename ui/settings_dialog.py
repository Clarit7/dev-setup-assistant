"""
C. LLM 프로바이더 / API 키 설정 다이얼로그

앱 안에서 .env를 직접 편집하지 않고도 프로바이더와 API 키를 설정할 수 있습니다.
"""

import os
import threading
from pathlib import Path
from typing import Callable, List, Optional

import customtkinter as ctk

_ENV_FILE = Path(__file__).parent.parent / ".env"

_PROVIDERS = ["anthropic", "openai", "gemini", "groq", "ollama"]

_KEY_LABELS = {
    "anthropic": "Anthropic API 키  (sk-ant-...)",
    "openai":    "OpenAI API 키  (sk-...)",
    "gemini":    "Google Gemini API 키  (AIza...)",
    "groq":      "Groq API 키  (gsk_...)",
    "ollama":    "(API 키 불필요 — 로컬 서버)",
}

_KEY_ENVVARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai":    "OPENAI_API_KEY",
    "gemini":    "GEMINI_API_KEY",
    "groq":      "GROQ_API_KEY",
    "ollama":    "",
}

_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai":    "gpt-4o-mini",
    "gemini":    "gemini-2.5-flash-preview-04-17",
    "groq":      "llama-3.3-70b-versatile",
    "ollama":    "mistral",
}

_MODEL_ENVVARS = {
    "anthropic": "ANTHROPIC_MODEL",
    "openai":    "OPENAI_MODEL",
    "gemini":    "GEMINI_MODEL",
    "groq":      "GROQ_MODEL",
    "ollama":    "OLLAMA_MODEL",
}


# ── .env 파일 헬퍼 ─────────────────────────────────────────────────────────────

def _load_env() -> dict:
    env: dict = {}
    if not _ENV_FILE.exists():
        return env
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _save_env(new_values: dict):
    """기존 .env 파일 구조를 유지하면서 값만 업데이트합니다."""
    lines: list = []
    updated: set = set()

    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=")[0].strip()
                if key in new_values:
                    lines.append(f"{key}={new_values[key]}")
                    updated.add(key)
                # new_values에 없는 키는 파일에서 제거 (삭제된 키 처리)
            else:
                lines.append(line)  # 주석·빈 줄은 유지

    # 기존 파일에 없던 새 키 추가
    for key, val in new_values.items():
        if key not in updated:
            lines.append(f"{key}={val}")

    _ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # os.environ에도 즉시 반영
    for key, val in new_values.items():
        os.environ[key] = val


# ── 설정 다이얼로그 ────────────────────────────────────────────────────────────

class SettingsDialog(ctk.CTkToplevel):
    """LLM 프로바이더 및 API 키 설정 모달 창"""

    def __init__(self, parent: ctk.CTk, on_apply: Optional[Callable] = None):
        super().__init__(parent)
        self.title("LLM 설정")
        self.geometry("480x470")
        self.resizable(False, False)
        self.grab_set()   # 모달: 다른 창 클릭 차단
        self.lift()
        self.focus_force()

        self.on_apply = on_apply
        self._env = _load_env()
        self._show_key = False
        self._fetch_thread: Optional[threading.Thread] = None

        self._build_ui()
        self._load_current_values()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 24, "pady": 6}

        ctk.CTkLabel(
            self, text="LLM 프로바이더 설정",
            font=("Malgun Gothic", 16, "bold"),
        ).pack(padx=24, pady=(20, 8))

        # ── 프로바이더 선택 ──
        ctk.CTkLabel(self, text="프로바이더", font=("Malgun Gothic", 13),
                     anchor="w").pack(fill="x", padx=24)
        self._provider_var = ctk.StringVar(value="anthropic")
        ctk.CTkOptionMenu(
            self, values=_PROVIDERS, variable=self._provider_var,
            font=("Malgun Gothic", 13), command=self._on_provider_change,
        ).pack(fill="x", **pad)

        # ── API 키 ──
        self._key_label = ctk.CTkLabel(
            self, text="API 키", font=("Malgun Gothic", 13), anchor="w"
        )
        self._key_label.pack(fill="x", padx=24)

        key_frame = ctk.CTkFrame(self, fg_color="transparent")
        key_frame.pack(fill="x", **pad)
        key_frame.grid_columnconfigure(0, weight=1)

        self._key_entry = ctk.CTkEntry(
            key_frame, show="●", font=("Malgun Gothic", 13),
            placeholder_text="API 키를 입력하세요",
        )
        self._key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._toggle_btn = ctk.CTkButton(
            key_frame, text="보기", width=60, font=("Malgun Gothic", 12),
            command=self._toggle_key_visibility,
        )
        self._toggle_btn.grid(row=0, column=1)

        # ── 모델 선택 ──
        model_header = ctk.CTkFrame(self, fg_color="transparent")
        model_header.pack(fill="x", padx=24, pady=(6, 0))
        model_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            model_header, text="모델",
            font=("Malgun Gothic", 13), anchor="w",
        ).grid(row=0, column=0, sticky="w")
        self._refresh_btn = ctk.CTkButton(
            model_header, text="↻ 목록 새로고침", width=110, height=22,
            font=("Malgun Gothic", 11),
            fg_color="gray30", hover_color="gray20",
            command=self._on_refresh_models,
        )
        self._refresh_btn.grid(row=0, column=1)

        self._model_combo = ctk.CTkComboBox(
            self, values=[], font=("Malgun Gothic", 13),
            state="normal",
        )
        self._model_combo.pack(fill="x", padx=24, pady=(2, 6))
        self._model_combo.set("")

        # ── Ollama URL (프로바이더가 ollama일 때만 표시) ──
        self._url_label = ctk.CTkLabel(
            self, text="Ollama 서버 URL", font=("Malgun Gothic", 13), anchor="w"
        )
        self._url_entry = ctk.CTkEntry(
            self, font=("Malgun Gothic", 13),
            placeholder_text="http://localhost:11434",
        )

        # ── LLM 안전성 설정 ──
        ctk.CTkLabel(
            self, text="명령어 안전성 설정",
            font=("Malgun Gothic", 13, "bold"), anchor="w",
        ).pack(fill="x", padx=24, pady=(12, 2))

        self._auto_caution_var = ctk.BooleanVar(
            value=self._env.get("LLM_SAFETY_AUTO_CAUTION", "0") == "1"
        )
        ctk.CTkCheckBox(
            self,
            text="주의 명령어 자동 허용",
            font=("Malgun Gothic", 13),
            variable=self._auto_caution_var,
        ).pack(anchor="w", padx=28, pady=(2, 0))
        ctk.CTkLabel(
            self,
            text="화이트리스트에 없지만 LLM이 '주의'로 판정한 명령어를 확인 없이 허용합니다",
            font=("Malgun Gothic", 11), text_color="gray60",
            anchor="w", wraplength=420,
        ).pack(fill="x", padx=44, pady=(0, 6))

        # ── 버튼 ──
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=24, pady=(10, 20))

        ctk.CTkButton(
            btn_frame, text="저장 & 적용", font=("Malgun Gothic", 13),
            command=self._on_save,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="취소",
            font=("Malgun Gothic", 13),
            fg_color="gray40", hover_color="gray30",
            command=self.destroy,
        ).pack(side="right")

    # ── 현재 값 로드 ──────────────────────────────────────────────────────────

    def _load_current_values(self):
        provider = self._env.get("LLM_PROVIDER", "anthropic").lower()
        if provider in _PROVIDERS:
            self._provider_var.set(provider)
        self._on_provider_change(provider)  # loads provider-specific model

        url = self._env.get("OLLAMA_BASE_URL", "")
        if url:
            self._url_entry.insert(0, url)

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────────────

    def _on_provider_change(self, provider: str):
        self._key_label.configure(text=_KEY_LABELS.get(provider, "API 키"))

        self._key_entry.delete(0, "end")
        envvar = _KEY_ENVVARS.get(provider, "")
        if envvar:
            existing = self._env.get(envvar, "")
            if existing:
                self._key_entry.insert(0, existing)
            self._key_entry.configure(state="normal")
        else:
            self._key_entry.configure(state="disabled")

        # 모델: 프로바이더별 저장값 로드
        model_envvar = _MODEL_ENVVARS.get(provider, "")
        saved_model = self._env.get(model_envvar, "") if model_envvar else ""
        self._model_combo.configure(values=[])
        self._model_combo.set(saved_model)

        # API 키가 있으면 모델 목록 비동기 로드
        api_key = self._key_entry.get().strip()
        if api_key or provider == "ollama":
            base_url = self._url_entry.get().strip() if provider == "ollama" else ""
            self._fetch_models_async(provider, api_key, base_url)

        if provider == "ollama":
            self._url_label.pack(fill="x", padx=24)
            self._url_entry.pack(fill="x", padx=24, pady=6)
        else:
            self._url_label.pack_forget()
            self._url_entry.pack_forget()

    def _toggle_key_visibility(self):
        self._show_key = not self._show_key
        self._key_entry.configure(show="" if self._show_key else "●")
        self._toggle_btn.configure(text="숨기기" if self._show_key else "보기")

    def _on_refresh_models(self):
        provider = self._provider_var.get()
        envvar = _KEY_ENVVARS.get(provider, "")
        api_key = self._key_entry.get().strip() if envvar else ""
        base_url = self._url_entry.get().strip() if provider == "ollama" else ""
        self._fetch_models_async(provider, api_key, base_url)

    def _fetch_models_async(self, provider: str, api_key: str, base_url: str = ""):
        """백그라운드에서 모델 목록을 가져와 ComboBox를 업데이트합니다."""
        from core.model_list import fetch_models

        current_value = self._model_combo.get()
        self._model_combo.configure(values=[], state="disabled")
        self._model_combo.set("불러오는 중...")
        self._refresh_btn.configure(state="disabled")

        def _worker():
            models = fetch_models(provider, api_key, base_url)
            if self.winfo_exists():
                self.after(0, lambda: self._on_models_loaded(models, current_value))

        self._fetch_thread = threading.Thread(target=_worker, daemon=True)
        self._fetch_thread.start()

    def _on_models_loaded(self, models: List[str], previous_value: str):
        """모델 목록 로드 완료 시 UI를 업데이트합니다."""
        if not self.winfo_exists():
            return
        self._refresh_btn.configure(state="normal")
        self._model_combo.configure(state="normal")
        if models:
            self._model_combo.configure(values=models)
            # 이전 값이 목록에 있으면 유지, 아니면 저장된 모델 또는 첫 번째 항목 선택
            if previous_value and previous_value in models:
                self._model_combo.set(previous_value)
            else:
                provider = self._provider_var.get()
                default = _DEFAULT_MODELS.get(provider, "")
                if default in models:
                    self._model_combo.set(default)
                elif previous_value and previous_value not in ("불러오는 중...", ""):
                    self._model_combo.set(previous_value)
                else:
                    self._model_combo.set(models[0])
        else:
            self._model_combo.configure(values=[])
            self._model_combo.set(
                previous_value if previous_value not in ("불러오는 중...", "") else ""
            )

    def _on_save(self):
        provider = self._provider_var.get()
        new_env = dict(self._env)
        new_env["LLM_PROVIDER"] = provider

        envvar = _KEY_ENVVARS.get(provider, "")
        if envvar:
            key = self._key_entry.get().strip()
            if key:
                new_env[envvar] = key

        model = self._model_combo.get().strip()
        model_envvar = _MODEL_ENVVARS.get(provider, "")
        if model:
            if model_envvar:
                new_env[model_envvar] = model
            # LLM_MODEL은 현재 활성 프로바이더의 모델로 설정 (core/llm.py 호환)
            new_env["LLM_MODEL"] = model
        else:
            if model_envvar and model_envvar in new_env:
                del new_env[model_envvar]
            if "LLM_MODEL" in new_env:
                del new_env["LLM_MODEL"]

        if provider == "ollama":
            url = self._url_entry.get().strip()
            if url:
                new_env["OLLAMA_BASE_URL"] = url

        new_env["LLM_SAFETY_AUTO_CAUTION"] = "1" if self._auto_caution_var.get() else "0"

        _save_env(new_env)
        # 삭제된 키를 os.environ에서도 제거
        for key in set(self._env) - set(new_env):
            os.environ.pop(key, None)
        self.destroy()
        if self.on_apply:
            self.on_apply()
