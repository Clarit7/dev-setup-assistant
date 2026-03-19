"""
개발환경 세팅 도우미 — LLM 연동 버전

흐름:
  CHATTING → (LLM이 ready_to_install=true 반환) → AWAITING_CONFIRM
           → (Y) → INSTALLING → CHATTING (계속 대화 가능)
           → (N) → CHATTING

신규 기능:
  A. 시스템 환경 자동 감지  — 시작 시 설치된 도구 목록을 LLM 컨텍스트로 전달
  B. 스트리밍 응답          — LLM 응답을 글자 단위로 실시간 표시
  C. LLM 설정 UI           — ⚙ 버튼으로 프로바이더/API키 변경
  F. 설치 이력 저장         — 설치 후 history.json에 기록, LLM에 컨텍스트 제공

안전 장치:
  - 모든 run/launch 명령어는 core.safety.is_safe_command() 통과 필수
  - LLM이 제안한 install 액션의 package_id 형식 검증
  - 블랙리스트 패턴 매칭으로 위험 명령 차단
"""

import re
import shutil
import subprocess
import threading
from typing import List

import customtkinter as ctk

# customtkinter 5.2.2 + Windows 11 버그 패치
ctk.CTk._windows_set_titlebar_color = lambda self, color_mode: None

from core.safety import is_safe_command
from core.runner import run_command
from core.actions import (
    Action, InstallAction, RunAction, LaunchAction,
    format_actions_for_display,
)
from core.llm import LLMClient, LLMResponse
from core.history import HistoryManager               # F
from core.env_detector import detect_environment, format_for_llm  # A
from installers.winget import WingetInstaller
from scenarios.registry import get_current_os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── 상태 상수 ────────────────────────────────────────────────────────────────
STATE_CHATTING         = "chatting"
STATE_AWAITING_CONFIRM = "awaiting_confirm"
STATE_INSTALLING       = "installing"

# ── 인스톨러 초기화 ───────────────────────────────────────────────────────────
_INSTALLERS = {
    "windows": WingetInstaller(),
}

# winget 패키지 ID 허용 패턴 (Publisher.PackageName 형식)
_PACKAGE_ID_RE = re.compile(r"^[\w][\w.-]+\.[\w][\w.-]+$")


def _get_installer():
    inst = _INSTALLERS.get(get_current_os())
    return inst if inst and inst.is_available() else None


# ── GUI ──────────────────────────────────────────────────────────────────────
class DevSetupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("개발환경 세팅 도우미")
        self.geometry("720x620")
        self.minsize(520, 420)

        self.app_state = STATE_CHATTING
        self.installer = _get_installer()
        self.pending_actions: List[Action] = []

        # F: 설치 이력 관리자
        self.history_manager = HistoryManager()

        # B: 스트리밍 — 이번 응답에서 emit한 문자 수
        self._stream_chars_emitted = 0

        self.llm: LLMClient | None = None

        self._build_ui()
        self._init_llm()

        # A: 앱 시작 직후 환경 감지 (백그라운드)
        threading.Thread(target=self._detect_environment, daemon=True).start()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.chat_box = ctk.CTkTextbox(
            self, state="disabled", wrap="word", font=("Malgun Gothic", 14)
        )
        self.chat_box.grid(row=0, column=0, columnspan=3,
                           padx=16, pady=(16, 8), sticky="nsew")

        self.input_field = ctk.CTkEntry(
            self, placeholder_text="메시지를 입력하세요...",
            font=("Malgun Gothic", 14),
        )
        self.input_field.grid(row=1, column=0, padx=(16, 8),
                              pady=(0, 16), sticky="ew")
        self.input_field.bind("<Return>", lambda e: self._on_send())

        self.send_button = ctk.CTkButton(
            self, text="전송", width=80,
            font=("Malgun Gothic", 14), command=self._on_send,
        )
        self.send_button.grid(row=1, column=1, padx=(0, 8), pady=(0, 16))

        # C: 설정 버튼
        self.settings_button = ctk.CTkButton(
            self, text="⚙", width=44,
            font=("Malgun Gothic", 15), command=self._open_settings,
            fg_color="gray30", hover_color="gray20",
        )
        self.settings_button.grid(row=1, column=2, padx=(0, 16), pady=(0, 16))

        self.grid_rowconfigure(1, minsize=50)

    # ── LLM 초기화 ───────────────────────────────────────────────────────────

    def _init_llm(self):
        print(f"[DEBUG] _init_llm 시작. LLM_PROVIDER={__import__('os').getenv('LLM_PROVIDER')}")
        try:
            self.llm = LLMClient()
            print(f"[DEBUG] LLM 초기화 성공: {self.llm.provider_label}")
            self._append_message(
                "시스템",
                f"LLM 연결됨: {self.llm.provider_label}\n"
                "무엇을 설치해드릴까요? 원하는 개발 환경을 자유롭게 말씀해주세요."
            )
        except (ValueError, ImportError, Exception) as e:
            self.llm = None
            self._append_message(
                "시스템",
                f"⚠️  LLM을 초기화하지 못했습니다.\n{e}\n\n"
                ".env 파일에 API 키가 올바르게 설정됐는지 확인하거나\n"
                "⚙ 버튼을 눌러 설정해주세요."
            )

    # ── A. 시스템 환경 자동 감지 ─────────────────────────────────────────────

    def _detect_environment(self):
        """백그라운드에서 설치된 도구를 감지하고 LLM 컨텍스트를 업데이트합니다."""
        tools = detect_environment()
        env_ctx = format_for_llm(tools)
        history_ctx = self.history_manager.format_for_llm()

        if self.llm:
            self.llm.set_context(env_ctx, history_ctx)

        installed_names = [t.name for t in tools if t.installed]
        summary = ", ".join(installed_names) if installed_names else "없음"
        self.after(0, self._append_message, "시스템",
                   f"🔍 환경 감지 완료 — 설치된 도구: {summary}")

    # ── C. 설정 창 ────────────────────────────────────────────────────────────

    def _open_settings(self):
        """⚙ 버튼 → 설정 다이얼로그 열기"""
        from ui.settings_dialog import SettingsDialog
        SettingsDialog(self, on_apply=self._reinit_llm)

    def _reinit_llm(self):
        """설정 저장 후 LLM 재초기화 (기존 컨텍스트 유지)"""
        # 변경된 .env를 os.environ에 이미 반영했으므로 바로 재생성
        old_env_ctx = self.llm._env_context if self.llm else ""
        old_hist_ctx = self.llm._history_context if self.llm else ""
        try:
            self.llm = LLMClient()
            self.llm.set_context(old_env_ctx, old_hist_ctx)
            self._append_message("시스템", f"✓ LLM 변경됨: {self.llm.provider_label}")
        except Exception as e:
            self._append_message("시스템", f"⚠️  LLM 초기화 실패: {e}")

    # ── 채팅창 헬퍼 ──────────────────────────────────────────────────────────

    def _append_message(self, sender: str, message: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"[{sender}]\n{message}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _append_text(self, text: str):
        """발신자 없이 텍스트만 추가 (스트리밍 청크 / 설치 로그)"""
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", text)
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _set_input_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.input_field.configure(state=state)
        self.send_button.configure(state=state)

    # ── 입력 처리 ────────────────────────────────────────────────────────────

    def _on_send(self):
        print(f"[DEBUG] _on_send 호출됨. llm={self.llm}, app_state={self.app_state}")
        if not self.llm:
            print("[DEBUG] llm이 None이라 리턴")
            return
        text = self.input_field.get().strip()
        print(f"[DEBUG] 입력 텍스트: '{text}'")
        if not text:
            print("[DEBUG] 텍스트 비어있어 리턴")
            return
        self._append_message("나", text)
        self.input_field.delete(0, "end")
        self._handle_state(text)

    def _handle_state(self, text: str):
        print(f"[DEBUG] _handle_state: app_state={self.app_state}")
        if self.app_state == STATE_INSTALLING:
            return

        if self.app_state == STATE_AWAITING_CONFIRM:
            if text.strip().upper() == "Y":
                self._start_installation()
            else:
                self._append_message("AI", "취소했습니다. 다른 요청이 있으시면 말씀해주세요.")
                self.pending_actions.clear()
                self.app_state = STATE_CHATTING
                self._send_to_llm_async("사용자가 설치를 취소했습니다. 다시 도와주세요.")

        elif self.app_state == STATE_CHATTING:
            self._send_to_llm_async(text)

    # ── B. 스트리밍 LLM 호출 ──────────────────────────────────────────────────

    def _send_to_llm_async(self, user_message: str):
        """B: 스트리밍으로 LLM을 호출합니다. 응답 글자가 실시간으로 표시됩니다."""
        print(f"[DEBUG] _send_to_llm_async: '{user_message[:40]}'")
        self._set_input_enabled(False)
        self._stream_chars_emitted = 0

        # AI 메시지 헤더를 미리 표시
        self._append_text("[AI]\n")

        def _on_chunk(chunk: str):
            self._stream_chars_emitted += len(chunk)
            self.after(0, self._append_text, chunk)

        def _worker():
            try:
                print("[DEBUG] LLM 스트리밍 시작")
                response = self.llm.send_stream(user_message, on_chunk=_on_chunk)
                print(f"[DEBUG] 스트리밍 완료. ready_to_install={response.ready_to_install}")
                self.after(0, self._on_stream_done, response)
            except Exception as e:
                print(f"[DEBUG] LLM 오류: {e}")
                self.after(0, self._on_llm_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_stream_done(self, response: LLMResponse):
        """B: 스트리밍 완료 — 미표시 메시지 fallback 처리 및 액션 제안"""
        if self._stream_chars_emitted == 0:
            # message 추출 실패(비-JSON 응답 등) → 전체 메시지 일괄 표시
            self._append_text(response.message)
        self._append_text("\n\n")
        self._set_input_enabled(True)

        if response.ready_to_install and response.actions:
            self._propose_actions(response.actions)

    def _on_llm_error(self, error_msg: str):
        """LLM 호출 실패 — [AI] 헤더 아래에 오류 메시지 추가"""
        self._append_text(f"⚠️  오류: {error_msg}\n다시 시도해주세요.\n\n")
        self._set_input_enabled(True)

    # ── 액션 제안 및 안전 검증 ─────────────────────────────────────────────────

    def _propose_actions(self, actions: List[Action]):
        safe_actions, blocked = self._validate_actions(actions)

        if blocked:
            blocked_msg = "\n".join(f"  ✗ {name}: {reason}" for name, reason in blocked)
            self._append_message("시스템", f"⚠️  보안 검사에서 차단됨:\n{blocked_msg}")

        if not safe_actions:
            self._append_message("AI", "실행 가능한 액션이 없습니다. 다른 방법을 말씀해주세요.")
            return

        self.pending_actions = safe_actions
        action_list = format_actions_for_display(safe_actions)
        self._append_message(
            "AI",
            f"다음 작업을 진행할까요?\n\n{action_list}\n\n설치하려면 Y, 취소하려면 다른 키를 입력하세요."
        )
        self.app_state = STATE_AWAITING_CONFIRM

    def _validate_actions(
        self, actions: List[Action]
    ) -> tuple:
        safe, blocked = [], []

        for action in actions:
            if isinstance(action, InstallAction):
                ok, reason = self._validate_install(action)
                (safe if ok else blocked).append(action if ok else (action.display_name, reason))

            elif isinstance(action, (RunAction, LaunchAction)):
                ok, reason = is_safe_command(action.command)
                (safe if ok else blocked).append(action if ok else (action.display_name, reason))

        return safe, blocked

    @staticmethod
    def _validate_install(action: InstallAction) -> tuple:
        pid = action.package_id.strip()
        if not pid:
            return False, "패키지 ID가 비어 있습니다."
        if not _PACKAGE_ID_RE.match(pid):
            return False, f"잘못된 패키지 ID 형식: '{pid}'"
        return True, ""

    # ── 설치 실행 ────────────────────────────────────────────────────────────

    def _start_installation(self):
        if not self.installer:
            self._append_message(
                "AI",
                "winget을 찾을 수 없습니다.\n"
                "Windows 10 1709 이상에서 winget이 설치되어 있는지 확인해주세요."
            )
            self.app_state = STATE_CHATTING
            return

        self.app_state = STATE_INSTALLING
        self._set_input_enabled(False)
        self._append_message("AI", "설치를 시작합니다. 잠시 기다려주세요...\n")
        threading.Thread(target=self._run_installation, daemon=True).start()

    def _run_installation(self):
        """백그라운드에서 액션들을 순서대로 실행합니다."""
        install_actions = [a for a in self.pending_actions if isinstance(a, InstallAction)]
        run_actions     = [a for a in self.pending_actions if isinstance(a, RunAction)]
        launch_actions  = [a for a in self.pending_actions if isinstance(a, LaunchAction)]

        success = True
        recorded_packages: List[str] = []  # F: 이력 기록용

        # 1) 패키지 설치 (winget)
        for action in install_actions:
            self.after(0, self._append_text, f"━━━ {action.display_name} ━━━\n")

            if action.check_command and shutil.which(action.check_command):
                self.after(0, self._append_text, "✓ 이미 설치되어 있습니다.\n\n")
                continue

            cmd = self.installer.build_install_command(action.package_id)
            ok = run_command(
                cmd,
                on_output=lambda line: self.after(0, self._append_text, line),
                on_error=lambda msg: self.after(0, self._append_text, f"[오류] {msg}"),
            )
            self.after(0, self._append_text, "\n")
            recorded_packages.append(action.display_name)
            if not ok:
                success = False

        # 2) 추가 명령어 실행 (npm install 등)
        for action in run_actions:
            self.after(0, self._append_text, f"━━━ {action.display_name} ━━━\n")
            ok = run_command(
                action.command,
                on_output=lambda line: self.after(0, self._append_text, line),
                on_error=lambda msg: self.after(0, self._append_text, f"[오류] {msg}"),
            )
            self.after(0, self._append_text, "\n")
            if not ok:
                success = False

        self.after(0, self._on_installation_done, success, launch_actions, recorded_packages)

    def _on_installation_done(
        self, success: bool, launch_actions: List[LaunchAction], recorded_packages: List[str]
    ):
        self.pending_actions.clear()
        self._set_input_enabled(True)
        self.app_state = STATE_CHATTING

        # F: 이력 기록 및 LLM 컨텍스트 갱신
        if recorded_packages:
            self.history_manager.record(recorded_packages, success)
            if self.llm:
                history_ctx = self.history_manager.format_for_llm()
                self.llm.set_context(self.llm._env_context, history_ctx)

        result_msg = "설치가 완료됐습니다! ✓" if success else (
            "일부 설치에 실패했습니다. 관리자 권한으로 재시도하거나 패키지 관리자 버전을 확인해주세요."
        )
        context_msg = (
            f"설치 {'성공' if success else '실패'}.\n"
            f"실행할 앱 목록: {[a.display_name for a in launch_actions]}"
            if launch_actions else
            f"설치 {'성공' if success else '실패'}. 다음 단계를 안내해주세요."
        )
        self._append_message("시스템", result_msg)
        self._send_to_llm_async(context_msg)

        # 3) 앱 실행 (launch actions)
        for action in launch_actions:
            self._launch_app(action)

    # ── 앱 실행 ──────────────────────────────────────────────────────────────

    def _launch_app(self, action: LaunchAction):
        safe, reason = is_safe_command(action.command)
        if not safe:
            self._append_message("시스템", f"[보안 차단] {action.display_name}: {reason}")
            return
        try:
            subprocess.Popen(action.command, shell=False)
        except Exception as e:
            self._append_message("시스템", f"{action.display_name} 실행 실패: {e}")


# ── 진입점 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = DevSetupApp()
    app.mainloop()
