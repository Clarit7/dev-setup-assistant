"""
개발환경 세팅 도우미 — LLM 연동 버전

흐름:
  CHATTING → (LLM이 ready_to_install=true 반환) → AWAITING_CONFIRM
           → (Y) → INSTALLING → CHATTING (계속 대화 가능)
           → (N) → CHATTING

기능:
  A. 시스템 환경 자동 감지  — 시작 시 설치된 도구 목록 + Docker 상태를 LLM 컨텍스트로 전달
  B. 스트리밍 응답          — LLM 응답을 글자 단위로 실시간 표시
  C. LLM 설정 UI           — ⚙ 버튼으로 프로바이더/API키 변경
  D. 컨테이너 연동          — Docker 컨테이너 생성, devcontainer.json, 진입 스크립트 자동 생성
  E. 이미지 첨부            — 스크린샷 붙여넣기(Ctrl+V) 또는 파일 선택 → LLM 비전 Q&A
  F. 설치 이력 저장         — 설치 후 history.json에 기록, LLM에 컨텍스트 제공

안전 장치:
  - 모든 run/launch 명령어는 core.safety.is_safe_command() 통과 필수
  - LLM이 제안한 install 액션의 package_id 형식 검증
  - ContainerSetupAction의 이미지/컨테이너 이름 형식 검증
  - 블랙리스트 패턴 매칭으로 위험 명령 차단
"""

import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import List, Optional

import customtkinter as ctk
from tkinter import filedialog

# customtkinter 5.2.2 + Windows 11 버그 패치
ctk.CTk._windows_set_titlebar_color = lambda self, color_mode: None

from core.safety import is_safe_command
from core.runner import run_command
from core.actions import (
    Action, InstallAction, RunAction, LaunchAction, ContainerSetupAction,
    format_actions_for_display,
)
from core.llm import LLMClient, LLMResponse
from core.history import HistoryManager                              # F
from core.env_detector import detect_environment, format_for_llm    # A
from core.container import (                                         # D
    detect_docker, list_containers, create_devcontainer_config,
    create_entry_scripts, register_windows_terminal_profile,
    format_for_llm as format_container_for_llm,
)
from core.ide_connector import (                                     # D
    detect_ides, open_workspace_in_ide, get_devcontainer_guidance,
)
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
# Docker 이미지 이름 허용 패턴 (예: node:18, python:3.11-slim, ghcr.io/org/img:tag)
_DOCKER_IMAGE_RE = re.compile(
    r"^[a-z0-9][a-z0-9._/-]*(:[\w][\w.-]*)?$"
)
# 컨테이너 이름 허용 패턴
_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")

# 기본 워크스페이스 루트 디렉토리
_DEFAULT_WORKSPACE_ROOT = Path(os.path.expanduser("~")) / "dev"


def _get_installer():
    inst = _INSTALLERS.get(get_current_os())
    return inst if inst and inst.is_available() else None


def _default_workspace(container_name: str) -> str:
    """컨테이너 이름 기반 기본 워크스페이스 경로"""
    return str(_DEFAULT_WORKSPACE_ROOT / container_name)


# ── GUI ──────────────────────────────────────────────────────────────────────
class DevSetupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("개발환경 세팅 도우미")
        self.geometry("720x640")
        self.minsize(520, 440)

        self.app_state = STATE_CHATTING
        self.installer = _get_installer()
        self.pending_actions: List[Action] = []

        # F: 설치 이력 관리자
        self.history_manager = HistoryManager()

        # B: 스트리밍 — 이번 응답에서 emit한 문자 수
        self._stream_chars_emitted = 0

        # E: 현재 첨부 이미지
        self._current_image = None   # ImageAttachment | None

        self.llm: LLMClient | None = None

        self._build_ui()
        self._init_llm()

        # A: 앱 시작 직후 환경 감지 (백그라운드)
        threading.Thread(target=self._detect_environment, daemon=True).start()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ─ 채팅창 ─
        self.chat_box = ctk.CTkTextbox(
            self, state="disabled", wrap="word", font=("Malgun Gothic", 14)
        )
        self.chat_box.grid(row=0, column=0, columnspan=4,
                           padx=16, pady=(16, 4), sticky="nsew")

        # ─ E: 이미지 미리보기 프레임 (기본 숨김) ─
        self.image_preview_frame = ctk.CTkFrame(self, height=56, fg_color="gray20")
        self.image_preview_frame.grid(row=1, column=0, columnspan=4,
                                      padx=16, pady=(0, 4), sticky="ew")
        self.image_preview_frame.grid_columnconfigure(1, weight=1)
        self.image_preview_frame.grid_remove()  # 초기 숨김

        self.image_thumb_label = ctk.CTkLabel(
            self.image_preview_frame, text="", width=80
        )
        self.image_thumb_label.grid(row=0, column=0, padx=(8, 4), pady=4)

        self.image_name_label = ctk.CTkLabel(
            self.image_preview_frame, text="",
            font=("Malgun Gothic", 12), anchor="w"
        )
        self.image_name_label.grid(row=0, column=1, padx=4, pady=4, sticky="ew")

        self.image_clear_button = ctk.CTkButton(
            self.image_preview_frame, text="✕", width=32, height=28,
            font=("Malgun Gothic", 13),
            fg_color="gray40", hover_color="gray30",
            command=self._clear_image_attachment,
        )
        self.image_clear_button.grid(row=0, column=2, padx=(4, 8), pady=4)

        # ─ 입력 영역 ─
        self.input_field = ctk.CTkEntry(
            self, placeholder_text="메시지를 입력하거나 스크린샷을 Ctrl+V로 붙여넣으세요...",
            font=("Malgun Gothic", 14),
        )
        self.input_field.grid(row=2, column=0, padx=(16, 4),
                              pady=(0, 16), sticky="ew")
        self.input_field.bind("<Return>", lambda e: self._on_send())
        self.input_field.bind("<Control-v>", self._on_paste_event)

        # ─ E: 이미지 첨부 버튼 ─
        self.attach_button = ctk.CTkButton(
            self, text="📎", width=44,
            font=("Malgun Gothic", 15), command=self._on_attach_image,
            fg_color="gray30", hover_color="gray20",
        )
        self.attach_button.grid(row=2, column=1, padx=(0, 4), pady=(0, 16))

        # ─ 전송 버튼 ─
        self.send_button = ctk.CTkButton(
            self, text="전송", width=80,
            font=("Malgun Gothic", 14), command=self._on_send,
        )
        self.send_button.grid(row=2, column=2, padx=(0, 4), pady=(0, 16))

        # ─ C: 설정 버튼 ─
        self.settings_button = ctk.CTkButton(
            self, text="⚙", width=44,
            font=("Malgun Gothic", 15), command=self._open_settings,
            fg_color="gray30", hover_color="gray20",
        )
        self.settings_button.grid(row=2, column=3, padx=(0, 16), pady=(0, 16))

        self.grid_rowconfigure(2, minsize=50)

    # ── LLM 초기화 ───────────────────────────────────────────────────────────

    def _init_llm(self):
        print(f"[DEBUG] _init_llm 시작. LLM_PROVIDER={__import__('os').getenv('LLM_PROVIDER')}")
        try:
            self.llm = LLMClient()
            print(f"[DEBUG] LLM 초기화 성공: {self.llm.provider_label}")
            self._append_message(
                "시스템",
                f"LLM 연결됨: {self.llm.provider_label}\n"
                "무엇을 설치해드릴까요? 원하는 개발 환경을 자유롭게 말씀해주세요.\n"
                "스크린샷이 있으면 Ctrl+V 또는 📎 버튼으로 첨부할 수 있습니다."
            )
        except (ValueError, ImportError, Exception) as e:
            self.llm = None
            self._append_message(
                "시스템",
                f"⚠️  LLM을 초기화하지 못했습니다.\n{e}\n\n"
                ".env 파일에 API 키가 올바르게 설정됐는지 확인하거나\n"
                "⚙ 버튼을 눌러 설정해주세요."
            )

    # ── A. 시스템 환경 자동 감지 (Docker 포함) ───────────────────────────────

    def _detect_environment(self):
        """백그라운드에서 설치된 도구 + Docker 상태를 감지하고 LLM 컨텍스트를 업데이트합니다."""
        tools = detect_environment()

        # D: Docker 상태 감지
        docker_status = detect_docker()
        containers = list_containers() if docker_status.running else []
        container_ctx = format_container_for_llm(docker_status, containers)

        env_ctx = format_for_llm(tools, container_ctx)
        history_ctx = self.history_manager.format_for_llm()

        if self.llm:
            self.llm.set_context(env_ctx, history_ctx)

        installed_names = [t.name for t in tools if t.installed]
        summary = ", ".join(installed_names) if installed_names else "없음"

        docker_info = ""
        if docker_status.installed:
            docker_info = (
                f" | Docker: {'실행 중' if docker_status.running else '설치됨(미실행)'}"
            )

        self.after(0, self._append_message, "시스템",
                   f"🔍 환경 감지 완료 — 설치된 도구: {summary}{docker_info}")

    # ── C. 설정 창 ────────────────────────────────────────────────────────────

    def _open_settings(self):
        from ui.settings_dialog import SettingsDialog
        SettingsDialog(self, on_apply=self._reinit_llm)

    def _reinit_llm(self):
        old_env_ctx = self.llm._env_context if self.llm else ""
        old_hist_ctx = self.llm._history_context if self.llm else ""
        try:
            self.llm = LLMClient()
            self.llm.set_context(old_env_ctx, old_hist_ctx)
            self._append_message("시스템", f"✓ LLM 변경됨: {self.llm.provider_label}")
        except Exception as e:
            self._append_message("시스템", f"⚠️  LLM 초기화 실패: {e}")

    # ── E. 이미지 첨부 ────────────────────────────────────────────────────────

    def _on_paste_event(self, event):
        """Ctrl+V — 클립보드에 이미지가 있으면 첨부하고 텍스트 붙여넣기를 차단합니다."""
        try:
            from ui.image_handler import grab_clipboard_image, is_available
            if not is_available():
                return  # Pillow 없으면 기본 동작
            img = grab_clipboard_image()
            if img:
                self._set_image_attachment(img)
                return "break"   # 텍스트 붙여넣기 차단
        except Exception:
            pass
        # 이미지 아닌 경우 기본 텍스트 붙여넣기 허용

    def _on_attach_image(self):
        """📎 버튼 — 파일 선택 다이얼로그로 이미지를 첨부합니다."""
        try:
            from ui.image_handler import load_image_from_file, is_available
            if not is_available():
                self._append_message(
                    "시스템",
                    "이미지 첨부 기능을 사용하려면 Pillow가 필요합니다.\n"
                    "터미널에서 `pip install Pillow` 를 실행하세요."
                )
                return
        except Exception:
            return

        filepath = filedialog.askopenfilename(
            title="이미지 파일 선택",
            filetypes=[
                ("이미지 파일", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("모든 파일", "*.*"),
            ],
        )
        if not filepath:
            return

        from ui.image_handler import load_image_from_file
        img = load_image_from_file(filepath)
        if img:
            self._set_image_attachment(img)
        else:
            self._append_message("시스템", "이미지 파일을 불러올 수 없습니다.")

    def _set_image_attachment(self, img):
        """이미지를 현재 첨부물로 설정하고 미리보기를 표시합니다."""
        self._current_image = img

        # 썸네일 표시
        if img.thumbnail:
            self.image_thumb_label.configure(image=img.thumbnail, text="")
        else:
            self.image_thumb_label.configure(image=None, text="🖼")

        # 파일명 또는 기본 레이블
        if img.source_path:
            name = Path(img.source_path).name
        else:
            name = "클립보드 이미지"
        self.image_name_label.configure(text=name)

        # 미리보기 프레임 표시
        self.image_preview_frame.grid()

    def _clear_image_attachment(self):
        """첨부 이미지를 제거하고 미리보기를 숨깁니다."""
        self._current_image = None
        self.image_thumb_label.configure(image=None, text="")
        self.image_name_label.configure(text="")
        self.image_preview_frame.grid_remove()

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
        self.attach_button.configure(state=state)

    # ── 입력 처리 ────────────────────────────────────────────────────────────

    def _on_send(self):
        print(f"[DEBUG] _on_send 호출됨. llm={self.llm}, app_state={self.app_state}")
        if not self.llm:
            return
        text = self.input_field.get().strip()
        image = self._current_image

        # 이미지만 있고 텍스트가 없으면 기본 프롬프트 사용
        if not text and image:
            text = "이 스크린샷을 보고 문제를 분석하고 해결 방법을 알려주세요."
        elif not text:
            return

        # 채팅창에 메시지 표시
        if image:
            source = (
                Path(image.source_path).name if image.source_path
                else "클립보드 이미지"
            )
            self._append_message("나", f"{text}\n[이미지 첨부: {source}]")
        else:
            self._append_message("나", text)

        self.input_field.delete(0, "end")
        self._clear_image_attachment()
        self._handle_state(text, image)

    def _handle_state(self, text: str, image=None):
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
            self._send_to_llm_async(text, image=image)

    # ── B. 스트리밍 LLM 호출 ──────────────────────────────────────────────────

    def _send_to_llm_async(self, user_message: str, image=None):
        """B: 스트리밍으로 LLM을 호출합니다. image가 있으면 비전 모드로 호출합니다."""
        print(f"[DEBUG] _send_to_llm_async: '{user_message[:40]}'")
        self._set_input_enabled(False)
        self._stream_chars_emitted = 0
        self._append_text("[AI]\n")

        def _on_chunk(chunk: str):
            self._stream_chars_emitted += len(chunk)
            self.after(0, self._append_text, chunk)

        def _worker():
            try:
                print("[DEBUG] LLM 스트리밍 시작")
                response = self.llm.send_stream(
                    user_message, on_chunk=_on_chunk, image=image
                )
                print(f"[DEBUG] 스트리밍 완료. ready_to_install={response.ready_to_install}")
                self.after(0, self._on_stream_done, response)
            except Exception as e:
                print(f"[DEBUG] LLM 오류: {e}")
                self.after(0, self._on_llm_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_stream_done(self, response: LLMResponse):
        if self._stream_chars_emitted == 0:
            self._append_text(response.message)
        self._append_text("\n\n")
        self._set_input_enabled(True)

        if response.ready_to_install and response.actions:
            self._propose_actions(response.actions)

    def _on_llm_error(self, error_msg: str):
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

    def _validate_actions(self, actions: List[Action]) -> tuple:
        safe, blocked = [], []

        for action in actions:
            if isinstance(action, InstallAction):
                ok, reason = self._validate_install(action)
                (safe if ok else blocked).append(
                    action if ok else (action.display_name, reason)
                )

            elif isinstance(action, (RunAction, LaunchAction)):
                ok, reason = is_safe_command(action.command)
                (safe if ok else blocked).append(
                    action if ok else (action.display_name, reason)
                )

            elif isinstance(action, ContainerSetupAction):
                ok, reason = self._validate_container(action)
                (safe if ok else blocked).append(
                    action if ok else (action.display_name, reason)
                )

        return safe, blocked

    @staticmethod
    def _validate_install(action: InstallAction) -> tuple:
        pid = action.package_id.strip()
        if not pid:
            return False, "패키지 ID가 비어 있습니다."
        if not _PACKAGE_ID_RE.match(pid):
            return False, f"잘못된 패키지 ID 형식: '{pid}'"
        return True, ""

    @staticmethod
    def _validate_container(action: ContainerSetupAction) -> tuple:
        image = action.image.strip()
        if not image:
            return False, "Docker 이미지가 지정되지 않았습니다."
        if not _DOCKER_IMAGE_RE.match(image):
            return False, f"잘못된 Docker 이미지 형식: '{image}'"
        name = action.container_name.strip()
        if not name:
            return False, "컨테이너 이름이 비어 있습니다."
        if not _CONTAINER_NAME_RE.match(name):
            return False, f"잘못된 컨테이너 이름: '{name}' (영숫자, -, _ 만 허용)"
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
        install_actions  = [a for a in self.pending_actions if isinstance(a, InstallAction)]
        run_actions      = [a for a in self.pending_actions if isinstance(a, RunAction)]
        container_actions = [a for a in self.pending_actions if isinstance(a, ContainerSetupAction)]
        launch_actions   = [a for a in self.pending_actions if isinstance(a, LaunchAction)]

        success = True
        recorded_packages: List[str] = []

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

        # 3) D: 컨테이너 세팅
        for action in container_actions:
            self._run_container_setup(action)
            recorded_packages.append(action.display_name)

        self.after(
            0, self._on_installation_done, success, launch_actions, recorded_packages
        )

    def _run_container_setup(self, action: ContainerSetupAction):
        """D: ContainerSetupAction 실행 — Docker 컨테이너 생성 + 파일 생성 + 안내"""
        name = action.display_name
        self.after(0, self._append_text, f"━━━ {name} ━━━\n")

        # 워크스페이스 경로 결정
        workspace = action.workspace_path.strip() or _default_workspace(
            action.container_name
        )
        Path(workspace).mkdir(parents=True, exist_ok=True)
        self.after(0, self._append_text, f"📁 워크스페이스: {workspace}\n")

        # Docker 데몬 확인
        docker_status = detect_docker()
        if not docker_status.running:
            msg = (
                "⚠️  Docker 데몬이 실행되지 않고 있습니다.\n"
                "Docker Desktop을 시작한 후 다시 시도해주세요."
            )
            self.after(0, self._append_text, msg + "\n")
            return

        # 이미지 pull
        self.after(0, self._append_text,
                   f"🐳 이미지 [{action.image}]를 가져오는 중...\n")
        pull_ok = run_command(
            ["docker", "pull", action.image],
            on_output=lambda line: self.after(0, self._append_text, line),
            on_error=lambda msg: self.after(0, self._append_text, f"[오류] {msg}"),
        )
        if not pull_ok:
            self.after(0, self._append_text, "✗ 이미지 pull 실패\n")
            return
        self.after(0, self._append_text, "\n")

        # 컨테이너 생성
        port_args: List[str] = []
        for p in action.ports:
            port_args.extend(["-p", p])

        # 기존 컨테이너 정리 (이름 충돌 방지)
        subprocess.run(
            ["docker", "rm", "-f", action.container_name],
            capture_output=True, timeout=15,
            creationflags=0x08000000,
        )

        workspace_posix = workspace.replace("\\", "/")
        run_cmd = [
            "docker", "run", "-d",
            "--name", action.container_name,
            "-v", f"{workspace_posix}:/workspace",
            *port_args,
            action.image,
            "tail", "-f", "/dev/null",  # 컨테이너 유지
        ]
        run_ok = run_command(
            run_cmd,
            on_output=lambda line: self.after(0, self._append_text, line),
            on_error=lambda msg: self.after(0, self._append_text, f"[오류] {msg}"),
        )
        if not run_ok:
            self.after(0, self._append_text, "✗ 컨테이너 생성 실패\n")
            return
        self.after(0, self._append_text,
                   f"✓ 컨테이너 [{action.container_name}] 생성됨\n")

        # devcontainer.json 생성
        try:
            cfg_path = create_devcontainer_config(
                workspace, action.container_name, action.image, action.ports
            )
            self.after(0, self._append_text,
                       f"✓ {cfg_path.relative_to(Path(workspace).parent)} 생성됨\n")
        except Exception as e:
            self.after(0, self._append_text, f"⚠️  devcontainer.json 생성 실패: {e}\n")

        # 진입 스크립트 생성
        try:
            scripts = create_entry_scripts(action.container_name, workspace)
            for s in scripts:
                self.after(0, self._append_text, f"✓ {s.name} 생성됨\n")
        except Exception as e:
            self.after(0, self._append_text, f"⚠️  진입 스크립트 생성 실패: {e}\n")

        # Windows Terminal 프로파일 등록
        if register_windows_terminal_profile(action.container_name):
            self.after(0, self._append_text, "✓ Windows Terminal 프로파일 등록됨\n")

        # IDE 열기 + 안내 메시지
        ides = detect_ides()
        if ides:
            open_workspace_in_ide(workspace, ides[0])
            guidance = get_devcontainer_guidance(ides[0], action.container_name)
            self.after(0, self._append_message, "AI", guidance)
        else:
            self.after(0, self._append_message, "AI",
                       f"IDE가 감지되지 않았습니다.\n"
                       f"워크스페이스 `{workspace}`의 `enter-dev.bat`을 실행하거나\n"
                       f"VS Code/Cursor에서 폴더를 직접 여세요.")

    def _on_installation_done(
        self, success: bool, launch_actions: List[LaunchAction],
        recorded_packages: List[str]
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
