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

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    _DND_AVAILABLE = True
except ImportError:
    _DND_AVAILABLE = False

# customtkinter 5.2.2 + Windows 11 버그 패치
ctk.CTk._windows_set_titlebar_color = lambda self, color_mode: None

from core.admin import is_admin, relaunch_as_admin
from core.safety import (
    is_safe_command, is_in_blacklist, is_in_dynamic_whitelist,
    add_to_dynamic_whitelist, get_exe_name, ALLOWED_EXECUTABLES,
)
from core.runner import run_command
from core.actions import (
    Action, InstallAction, RunAction, LaunchAction, ContainerSetupAction, SetEnvAction,
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

# ── 스피너 애니메이션 프레임 ───────────────────────────────────────────────────
_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
_SPINNER_INTERVAL_MS = 120

# ── 인스톨러 초기화 ───────────────────────────────────────────────────────────
_INSTALLERS = {
    "windows": WingetInstaller(),
}

# winget 패키지 ID 허용 패턴 (Publisher.PackageName 형식)
_PACKAGE_ID_RE = re.compile(r"^[\w][\w.-]+\.[\w][\w.-]+$")

# LLM이 set_env 액션으로 설정할 수 있는 환경변수 화이트리스트
_ALLOWED_ENV_KEYS = {
    # AI 에이전트 API 키
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "GITHUB_TOKEN",
    # 데이터베이스 연결
    "DATABASE_URL",
    "POSTGRES_URL",
    "POSTGRES_PASSWORD",
    "MYSQL_URL",
    "MYSQL_ROOT_PASSWORD",
    "MYSQL_PASSWORD",
    "MONGODB_URL",
    "MONGO_INITDB_ROOT_PASSWORD",
    "REDIS_URL",
    "REDIS_PASSWORD",
}
# 환경변수명 형식: 대문자·숫자·밑줄, 3~60자
_ENV_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,59}$")
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


def _set_system_env(key: str, value: str) -> bool:
    """플랫폼별로 환경변수를 영속적으로 저장합니다.

    Windows : HKCU\\Environment 레지스트리에 저장
    macOS/Linux : ~/.zshrc 또는 ~/.bashrc 에 export 라인 추가
    현재 프로세스 환경에도 즉시 반영합니다.
    """
    import platform
    os.environ[key] = value  # 현재 프로세스 즉시 반영

    system = platform.system()
    if system == "Windows":
        try:
            import winreg
            reg = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(reg, key, 0, winreg.REG_SZ, value)
            winreg.CloseKey(reg)
            # 변경사항을 로그인 세션 전체에 브로드캐스트
            import ctypes
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "Environment")
            return True
        except Exception:
            return False
    else:  # macOS / Linux
        shell = os.environ.get("SHELL", "/bin/bash")
        profile = Path.home() / (".zshrc" if "zsh" in shell else ".bashrc")
        try:
            with open(profile, "a", encoding="utf-8") as f:
                f.write(f'\nexport {key}="{value}"\n')
            return True
        except Exception:
            return False


class _SecureInputDialog(ctk.CTkToplevel):
    """API 키 입력을 위한 마스킹 입력 다이얼로그 (show='*')"""

    def __init__(self, parent, title: str, text: str):
        super().__init__(parent)
        self.title(title)
        self.geometry("440x200")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self._value: str = ""

        ctk.CTkLabel(
            self, text=text, wraplength=400,
            font=("Malgun Gothic", 13), justify="left",
        ).pack(padx=20, pady=(20, 8), anchor="w")

        self._entry = ctk.CTkEntry(
            self, show="*", width=400, font=("Malgun Gothic", 13)
        )
        self._entry.pack(padx=20, pady=4)
        self._entry.bind("<Return>", lambda _: self._confirm())
        self._entry.focus()

        ctk.CTkButton(self, text="확인", command=self._confirm).pack(pady=12)

    def _confirm(self):
        self._value = self._entry.get()
        self.destroy()

    def get_input(self) -> str:
        self.wait_window()
        return self._value


class _CautionConfirmDialog(ctk.CTkToplevel):
    """LLM이 '주의' 판정한 명령어를 사용자가 허용할지 묻는 다이얼로그"""

    def __init__(self, parent, cmd_str: str, reason: str):
        super().__init__(parent)
        self.title("⚠️  주의 명령어 확인")
        self.geometry("500x260")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()
        self._allowed = False

        ctk.CTkLabel(
            self, text="⚠️  주의가 필요한 명령어입니다",
            font=("Malgun Gothic", 15, "bold"), text_color="orange",
        ).pack(padx=20, pady=(18, 6))

        ctk.CTkLabel(
            self, text=cmd_str,
            font=("Consolas", 13), text_color="gray90",
            wraplength=460, justify="left",
        ).pack(padx=20, pady=(0, 4))

        ctk.CTkLabel(
            self, text=reason,
            font=("Malgun Gothic", 12), text_color="gray60",
            wraplength=460, justify="left",
        ).pack(padx=20, pady=(0, 14))

        ctk.CTkLabel(
            self, text="이 명령어를 실행하시겠습니까?\n(허용하면 이번 세션 동안 화이트리스트에 추가됩니다)",
            font=("Malgun Gothic", 12),
            wraplength=460, justify="center",
        ).pack(padx=20, pady=(0, 14))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 18))

        ctk.CTkButton(
            btn_frame, text="허용", width=100, font=("Malgun Gothic", 13),
            command=self._on_allow,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_frame, text="차단", width=100, font=("Malgun Gothic", 13),
            fg_color="gray40", hover_color="gray30",
            command=self.destroy,
        ).pack(side="right")

    def _on_allow(self):
        self._allowed = True
        self.destroy()

    def get_result(self) -> bool:
        self.wait_window()
        return self._allowed


# ── GUI ──────────────────────────────────────────────────────────────────────
_AppBase = (
    type("_AppBase", (ctk.CTk, TkinterDnD.DnDWrapper), {})
    if _DND_AVAILABLE else ctk.CTk
)


class DevSetupApp(_AppBase):
    def __init__(self):
        super().__init__()
        if _DND_AVAILABLE:
            self.TkdndVersion = TkinterDnD._require(self)
        self.title("개발환경 세팅 도우미 [관리자]")
        self.geometry("720x640")
        self.minsize(520, 440)

        self.app_state = STATE_CHATTING
        self.installer = _get_installer()
        self.pending_actions: List[Action] = []

        # F: 설치 이력 관리자
        self.history_manager = HistoryManager()

        # B: 스트리밍 — 이번 응답에서 emit한 문자 수
        self._stream_chars_emitted = 0
        # E/주제 가드: 스트리밍 시작 직전 텍스트 위치 (topic_valid=False 시 해당 범위 삭제)
        self._ai_stream_start: Optional[str] = None
        # 스피너 텍스트가 실제로 textbox에 존재하는지 (삭제 이중 실행 방지)
        self._spinner_present = False

        # E: 현재 첨부 이미지
        self._current_image = None   # ImageAttachment | None

        self.llm: LLMClient | None = None

        self._build_ui()
        self._init_dnd()
        self._init_llm()

        # A: 앱 시작 직후 환경 감지 (백그라운드)
        threading.Thread(target=self._detect_environment, daemon=True).start()

    def _init_dnd(self):
        """드래그앤드롭 초기화 (tkinterdnd2 설치 시)."""
        if not _DND_AVAILABLE:
            return
        try:
            widgets = [self, self.input_container]
            # ctk 래퍼의 내부 tkinter 위젯도 등록 (실제 이벤트 수신 대상)
            for ctk_w, inner_attr in (
                (self.chat_box,    "_textbox"),
                (self.input_field, "_textbox"),
            ):
                widgets.append(ctk_w)
                inner = getattr(ctk_w, inner_attr, None)
                if inner:
                    widgets.append(inner)
            for w in widgets:
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._on_dnd_drop)
                except Exception:
                    pass
        except Exception as e:
            print(f"[DnD] 초기화 실패: {e}")

    def _on_dnd_drop(self, event):
        """파일 드롭 이벤트 — 이미지 파일이면 첨부합니다."""
        raw = event.data.strip()
        paths = []
        for m in re.finditer(r'\{([^}]+)\}|(\S+)', raw):
            paths.append(m.group(1) or m.group(2))
        for p in paths:
            if Path(p).suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'):
                try:
                    from ui.image_handler import load_image_from_file
                    img = load_image_from_file(p)
                    if img:
                        self._set_image_attachment(img)
                except Exception:
                    pass
                break

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ─ 탭 뷰 ─
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        for tab_name in ("채팅", "컨테이너", "Git 설정", "WSL"):
            self.tab_view.add(tab_name)
        self.tab_view.set("채팅")

        # ─ 채팅 탭 ─
        chat_tab = self.tab_view.tab("채팅")
        chat_tab.grid_columnconfigure(0, weight=1)
        chat_tab.grid_rowconfigure(0, weight=1)
        chat_tab.grid_rowconfigure(1, weight=0)
        chat_tab.grid_rowconfigure(2, weight=0)

        # ─ 채팅창 ─
        self.chat_box = ctk.CTkTextbox(
            chat_tab, state="disabled", wrap="word", font=("Malgun Gothic", 14)
        )
        self.chat_box.grid(row=0, column=0, padx=0, pady=(0, 4), sticky="nsew")

        # ─ E: 이미지 미리보기 프레임 (기본 숨김) ─
        self.image_preview_frame = ctk.CTkFrame(chat_tab, height=56, fg_color="gray20")
        self.image_preview_frame.grid(row=1, column=0, padx=0, pady=(0, 4), sticky="ew")
        self.image_preview_frame.grid_columnconfigure(1, weight=1)
        self.image_preview_frame.grid_remove()

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

        # ─ 입력 컨테이너 (입력창 + 버튼을 하나의 UI 블록으로 묶음) ─
        self.input_container = ctk.CTkFrame(
            chat_tab, fg_color="gray20", corner_radius=12,
            border_width=1, border_color="gray30",
        )
        self.input_container.grid(row=2, column=0, padx=0, pady=(6, 0), sticky="ew")
        self.input_container.grid_columnconfigure(0, weight=1)

        # ─ 입력 영역 (멀티라인, 자동 높이 조절) ─
        self.input_field = ctk.CTkTextbox(
            self.input_container,
            font=("Malgun Gothic", 14),
            height=36,
            wrap="word",
            activate_scrollbars=True,
            fg_color="transparent",
            border_width=0,
        )
        self.input_field.grid(row=0, column=0, padx=(10, 10), pady=(8, 2), sticky="ew")
        self.input_field.bind("<Return>",       self._on_input_return)
        self.input_field.bind("<Shift-Return>", self._on_input_shift_return)
        self.input_field.bind("<KeyRelease>",   self._on_input_resize)
        self.input_field.bind("<Control-v>",    self._on_paste_event)

        # ─ 구분선 (input_container 내부, 입력창과 버튼 사이) ─
        tk.Frame(self.input_container, height=1, bg="#3d3d3d").grid(
            row=1, column=0, padx=10, pady=(2, 4), sticky="ew"
        )

        # ─ 버튼 행 ─
        btn_row = ctk.CTkFrame(self.input_container, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="ew")
        btn_row.grid_columnconfigure(2, weight=1)  # 가운데 spacer

        # E: 이미지 첨부 버튼
        self.attach_button = ctk.CTkButton(
            btn_row, text="📎", width=36, height=30,
            font=("Malgun Gothic", 15), command=self._on_attach_image,
            fg_color="gray30", hover_color="gray20",
        )
        self.attach_button.grid(row=0, column=0, padx=(0, 4))

        # C: 설정 버튼
        self.settings_button = ctk.CTkButton(
            btn_row, text="⚙", width=36, height=30,
            font=("Malgun Gothic", 15), command=self._open_settings,
            fg_color="gray30", hover_color="gray20",
        )
        self.settings_button.grid(row=0, column=1, padx=(0, 4))

        # 전송 버튼
        self.send_button = ctk.CTkButton(
            btn_row, text="전송", width=80, height=30,
            font=("Malgun Gothic", 14), command=self._on_send,
        )
        self.send_button.grid(row=0, column=3)

        # 취소 버튼 (설치 중에만 표시)
        self.cancel_button = ctk.CTkButton(
            btn_row, text="취소", width=80, height=30,
            font=("Malgun Gothic", 14), command=self._on_cancel_install,
            fg_color="#8B1A1A", hover_color="#6B1212",
        )
        self.cancel_button.grid(row=0, column=3)
        self.cancel_button.grid_remove()

        # ─ 컨테이너 탭 ─
        from ui.container_dashboard import ContainerDashboard
        container_tab = self.tab_view.tab("컨테이너")
        container_tab.grid_columnconfigure(0, weight=1)
        container_tab.grid_rowconfigure(0, weight=1)
        self.container_dashboard = ContainerDashboard(container_tab)
        self.container_dashboard.grid(row=0, column=0, sticky="nsew")

        # ─ Git 설정 탭 ─
        from ui.git_tab import GitTab
        git_tab = self.tab_view.tab("Git 설정")
        git_tab.grid_columnconfigure(0, weight=1)
        git_tab.grid_rowconfigure(0, weight=1)
        self.git_tab_widget = GitTab(git_tab)
        self.git_tab_widget.grid(row=0, column=0, sticky="nsew")

        # ─ WSL 탭 ─
        from ui.wsl_tab import WSLTab
        wsl_tab = self.tab_view.tab("WSL")
        wsl_tab.grid_columnconfigure(0, weight=1)
        wsl_tab.grid_rowconfigure(0, weight=1)
        self.wsl_tab_widget = WSLTab(wsl_tab)
        self.wsl_tab_widget.grid(row=0, column=0, sticky="nsew")

    # ── LLM 초기화 ───────────────────────────────────────────────────────────

    def _init_llm(self):
        try:
            self.llm = LLMClient()
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
        """Ctrl+V — 클립보드에 이미지/이미지 파일이 있으면 첨부하고 텍스트 붙여넣기를 차단합니다."""
        try:
            from ui.image_handler import (
                is_available, _clipboard_has_format, _CF_HDROP, _CF_DIB, _CF_DIBV5,
            )
            has_non_text = (
                _clipboard_has_format(_CF_HDROP) or
                _clipboard_has_format(_CF_DIB) or
                _clipboard_has_format(_CF_DIBV5)
            )
            if has_non_text:
                if is_available():
                    # Tk가 <Control-v> 처리 중 클립보드를 점유하므로
                    # 즉시 "break"로 차단 후 다음 틱에서 클립보드 접근
                    self.after(10, self._load_clipboard_image)
                return "break"
        except Exception:
            pass
        self.after(10, self._on_input_resize)

    def _load_clipboard_image(self):
        """Ctrl+V 후 Tk의 클립보드 점유 해제를 기다렸다가 이미지를 로드합니다."""
        try:
            from ui.image_handler import grab_clipboard_image
            img = grab_clipboard_image()
            if img:
                self._set_image_attachment(img)
        except Exception:
            pass

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

        img = load_image_from_file(filepath)
        if img:
            self._set_image_attachment(img)
        else:
            self._append_message("시스템", "이미지 파일을 불러올 수 없습니다.")

    def _set_image_attachment(self, img):
        """이미지를 현재 첨부물로 설정하고 미리보기를 표시합니다."""
        # 이전 이미지 먼저 정리 (pyimage1 stale 참조 방지)
        try:
            self.image_thumb_label._label.configure(image="")
        except Exception:
            pass
        self._current_image = img

        # 썸네일 표시
        if img.thumbnail:
            try:
                self.image_thumb_label.configure(image=img.thumbnail, text="")
            except Exception:
                self.image_thumb_label.configure(image=None, text="🖼")
        else:
            self.image_thumb_label.configure(image=None, text="🖼")

        # 파일명 또는 기본 레이블
        if img.source_path:
            name = Path(img.source_path).name
        else:
            name = "클립보드 이미지"
        self.image_name_label.configure(text=name)

        # 미리보기 프레임 표시 후 DnD 등록 (프레임이 드롭 이벤트를 가로채지 않도록)
        self.image_preview_frame.grid()
        if _DND_AVAILABLE:
            for w in (self.image_preview_frame, self.image_thumb_label,
                      self.image_name_label, self.image_clear_button):
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._on_dnd_drop)
                except Exception:
                    pass

    def _clear_image_attachment(self):
        """첨부 이미지를 제거하고 미리보기를 숨깁니다."""
        # CTkLabel 내부 tk.Label에서 image를 먼저 직접 제거
        # (CTkImage GC 후에도 tk.Label이 pyimage1을 참조하고 있어 TclError 발생)
        try:
            self.image_thumb_label._label.configure(image="")
        except Exception:
            pass
        self._current_image = None   # CTkImage GC는 이 줄 이후에 발생
        try:
            self.image_thumb_label.configure(image=None, text="")
        except Exception:
            pass
        self.image_name_label.configure(text="")
        self.image_preview_frame.grid_remove()

    # ── 채팅창 헬퍼 ──────────────────────────────────────────────────────────

    def _append_message(self, sender: str, message: str):
        self.chat_box.configure(state="normal")
        tb = self.chat_box._textbox
        # 스피너가 활성화 중이면 스피너 줄 앞에 삽입
        # Tk 텍스트 위젯은 끝에 암묵적 \n을 유지하므로:
        #   end-1c = 암묵적 \n,  end-2c = 스피너 줄의 실제 마지막 \n
        #   end-2c linestart = 스피너 줄의 첫 글자
        pos = tb.index("end-2c linestart") if getattr(self, "_spinner_present", False) else "end"
        tb.insert(pos, f"[{sender}]\n{message}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _append_text(self, text: str):
        """발신자 없이 텍스트만 추가 (스트리밍 청크 / 설치 로그)"""
        self.chat_box.configure(state="normal")
        tb = self.chat_box._textbox
        spinner_on = getattr(self, "_spinner_present", False)
        ins = tb.index("end-2c linestart") if spinner_on else "end"

        if '\r' not in text:
            tb.insert(ins, text)
        else:
            # \r 처리: winget 등 프로그레스바가 같은 줄을 덮어쓰는 경우
            segments = text.split('\r')
            tb.insert(ins, segments[0])
            for seg in segments[1:]:
                if '\n' in seg:
                    ins = tb.index("end-2c linestart") if spinner_on else "end"
                    tb.insert(ins, seg)
                else:
                    if spinner_on:
                        # 스피너 직전 줄을 덮어쓴다
                        spinner_line = tb.index("end-2c linestart")
                        prev_end     = tb.index(f"{spinner_line} -1c")
                        prev_start   = tb.index(f"{prev_end} linestart")
                        if prev_start != prev_end:
                            tb.delete(prev_start, prev_end)
                        if seg:
                            tb.insert(prev_start, seg)
                    else:
                        end_idx    = tb.index("end-1c")
                        line_start = tb.index(f"{end_idx} linestart")
                        if line_start != end_idx:
                            tb.delete(line_start, "end-1c")
                        if seg:
                            tb.insert("end", seg)

        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _is_at_bottom(self) -> bool:
        """스크롤이 맨 아래에 있는지 확인합니다."""
        try:
            _, bottom = self.chat_box._textbox.yview()
            return bottom >= 0.99
        except Exception:
            return True

    def _get_operation_label(self, actions) -> str:
        """액션 목록을 보고 적절한 진행 레이블을 반환합니다."""
        _REMOVE_KEYWORDS = {"uninstall", "remove", "제거", "삭제", "delete"}
        for action in actions:
            if isinstance(action, RunAction):
                tokens = {t.lower() for t in action.command}
                name   = action.display_name.lower()
                if tokens & _REMOVE_KEYWORDS or any(k in name for k in _REMOVE_KEYWORDS):
                    return "제거 진행 중"
        return "설치 진행 중"

    # ── 스피너 애니메이션 ────────────────────────────────────────────────────

    def _start_spinner(self, label: str = "처리 중"):
        """채팅창 맨 아래에 애니메이션 스피너 줄을 삽입합니다."""
        self._spinner_active = True
        self._spinner_present = True
        self._spinner_frame_idx = 0
        self._spinner_label = label
        self.chat_box.configure(state="normal")
        self.chat_box._textbox.insert("end", f"{_SPINNER_FRAMES[0]} {label}...\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")
        self._spinner_after_id = self.after(_SPINNER_INTERVAL_MS, self._tick_spinner)

    def _tick_spinner(self):
        if not getattr(self, "_spinner_active", False):
            return
        self._spinner_frame_idx = (self._spinner_frame_idx + 1) % len(_SPINNER_FRAMES)
        frame = _SPINNER_FRAMES[self._spinner_frame_idx]
        self.chat_box.configure(state="normal")
        tb = self.chat_box._textbox
        try:
            # end-2c = 스피너 줄 마지막 \n (암묵적 trailing \n 제외)
            # end-2c linestart = 스피너 줄 첫 글자
            start = tb.index("end-2c linestart")
            end   = tb.index("end-2c")
            tb.delete(start, end)
            tb.insert(start, f"{frame} {self._spinner_label}...")
        except Exception:
            pass
        # 사용자가 스크롤 중일 때는 강제로 아래로 이동하지 않음
        if self._is_at_bottom():
            self.chat_box.see("end")
        self.chat_box.configure(state="disabled")
        self._spinner_after_id = self.after(_SPINNER_INTERVAL_MS, self._tick_spinner)

    def _stop_spinner(self):
        """스피너를 멈추고 해당 줄을 채팅창에서 제거합니다."""
        self._spinner_active = False
        after_id = getattr(self, "_spinner_after_id", None)
        if after_id:
            self.after_cancel(after_id)
            self._spinner_after_id = None
        if not self._spinner_present:
            return  # 이미 제거됨 — 두 번째 호출 시 스트리밍 내용 삭제 방지
        self._spinner_present = False
        self.chat_box.configure(state="normal")
        tb = self.chat_box._textbox
        try:
            # 스피너 줄 + 앞 \n 삭제 → 빈 줄 없이 깔끔하게 제거
            tb.delete("end-2c linestart -1c", "end-2c")
        except Exception:
            pass
        self.chat_box.configure(state="disabled")

    def _set_input_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.input_field.configure(state=state)
        self.send_button.configure(state=state)
        self.attach_button.configure(state=state)
        self.settings_button.configure(state=state)

    def _set_installing_mode(self, installing: bool):
        """설치 중일 때 취소 버튼을 표시하고 전송 버튼을 숨깁니다."""
        if installing:
            self.send_button.grid_remove()
            self.cancel_button.grid()
        else:
            self.cancel_button.grid_remove()
            self.send_button.grid()

    def _on_cancel_install(self):
        """설치 취소 요청 — stop_event를 설정해 실행 중인 명령어를 종료합니다."""
        if hasattr(self, "_install_stop_event"):
            self._install_stop_event.set()
        self._append_message("시스템", "⚠️  설치 취소 중...")

    # ── 입력창 이벤트 ────────────────────────────────────────────────────────

    def _on_input_return(self, event):
        """Enter → 전송 (줄바꿈 삽입 차단)"""
        self._on_send()
        return "break"

    def _on_input_shift_return(self, event):
        """Shift+Enter → 줄바꿈 삽입 후 현재 줄 수 +1 (word-wrap 상태 보존)."""
        self.input_field.insert("insert", "\n")
        prev = getattr(self, "_input_lines", 1)
        new_lines = min(5, prev + 1)
        if new_lines != prev:
            self._input_lines = new_lines
            self.input_field.configure(height=6 + new_lines * 26)
        return "break"

    def _on_input_resize(self, event=None):
        """디바운스: 한글 IME 연속 이벤트 방지 (40ms)."""
        if hasattr(self, "_resize_job") and self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(40, self._do_input_resize)

    def _do_input_resize(self, use_layout=True):
        """입력창 높이를 조절합니다 (최대 5줄).

        use_layout=False: \\n 카운트만 사용 (Shift+Enter 즉시 호출 시)
        use_layout=True : update_idletasks + displaylines로 word-wrap도 감지
        줄 수가 바뀔 때만 configure → IME 입력 중 불필요한 리드로우 방지.
        """
        self._resize_job = None
        content = self.input_field.get("1.0", "end-1c")
        explicit_lines = content.count("\n") + 1

        if use_layout:
            try:
                tb = self.input_field._textbox
                tb.update_idletasks()
                info_end = tb.dlineinfo("end-1c")
                line_h = info_end[3] if (info_end and info_end[3] > 0) else 19
                widget_h = tb.winfo_height()
                lines_visible = max(1, widget_h // line_h)
                yview = tb.yview()
                frac = yview[1] - yview[0]  # 픽셀 기반 비율

                if frac >= 0.99:
                    # 전체 내용이 뷰포트 안에 있음 → dlineinfo로 직접 계산
                    info_1_0 = tb.dlineinfo("1.0")
                    if info_1_0 and info_end:
                        display_lines = (info_end[1] - info_1_0[1]) // line_h + 1
                    else:
                        display_lines = lines_visible
                else:
                    # 일부가 스크롤됨 → yview 비율로 전체 줄 수 추정
                    # yview는 픽셀 기반 → display line 비율과 동일
                    display_lines = max(lines_visible, round(lines_visible / frac))

                display_lines = max(1, display_lines)
            except Exception:
                display_lines = explicit_lines
        else:
            display_lines = explicit_lines

        lines = max(explicit_lines, display_lines)
        lines = max(1, min(5, lines))
        prev = getattr(self, "_input_lines", 0)
        # 이전 줄 수와 동일하면 아무것도 하지 않음
        if lines == prev:
            return
        self._input_lines = lines
        new_h = 6 + lines * 26
        self.input_field.configure(height=new_h)
        # 5줄 도달 시 스크롤바 색으로 가시화 (지원 여부 불확실 → try/except)
        at_max = lines >= 5
        try:
            self.input_field.configure(
                scrollbar_button_color="gray40" if at_max else "gray17",
                scrollbar_button_hover_color="gray50" if at_max else "gray17",
            )
        except Exception:
            pass

    def _on_send(self):
        if not self.llm:
            return
        text = self.input_field.get("1.0", "end-1c").strip()
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

        self.input_field.delete("1.0", "end")
        self.after(0, self._do_input_resize)   # 전송 후 높이 1줄로 복귀
        self._clear_image_attachment()
        self._handle_state(text, image)

    def _handle_state(self, text: str, image=None):
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
        self._set_input_enabled(False)
        self._stream_chars_emitted = 0

        # [AI] 헤더를 삽입하고, 헤더 직후 위치를 저장해둔다.
        # topic_valid=False로 판명되면 이 위치 이후를 전부 삭제하고 고정 메시지로 교체한다.
        self._append_text("[AI]\n")
        self._ai_stream_start = self.chat_box._textbox.index("end-1c")
        self._start_spinner("AI 응답 생성 중")

        def _on_chunk(chunk: str):
            # 첫 청크 도착 시 스피너 제거
            if getattr(self, "_spinner_active", False):
                self._spinner_active = False          # 재진입 방지
                self.after(0, self._stop_spinner)
            self._stream_chars_emitted += len(chunk)
            self.after(0, self._append_text, chunk)

        def _worker():
            try:
                response = self.llm.send_stream(
                    user_message, on_chunk=_on_chunk, image=image
                )
                self.after(0, self._on_stream_done, response)
            except Exception as e:
                self.after(0, self._on_llm_error, str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_stream_done(self, response: LLMResponse):
        self._stop_spinner()   # 청크가 하나도 없었던 경우를 대비한 정리
        # ── 주제 가드 (방법 1+4) ────────────────────────────────────────────
        # LLM이 topic_valid=false를 반환하면, 이미 스트리밍된 내용을 삭제하고
        # 고정 메시지로 교체한다. LLM 응답 내용은 사용자에게 노출되지 않는다.
        if not response.topic_valid and self._stream_chars_emitted == 0:
            # 청크가 전혀 없었던 경우에만 삭제 + 고정 메시지 표시
            # (이미 스트리밍된 내용이 있으면 그냥 보여줌 — 오탐 방지)
            if self._ai_stream_start:
                self.chat_box.configure(state="normal")
                self.chat_box._textbox.delete(self._ai_stream_start, "end")
                self.chat_box.configure(state="disabled")
            self._append_text(
                "⛔ 이 도구는 개발환경 세팅 용도로만 사용할 수 있습니다.\n\n"
            )
            self._set_input_enabled(True)
            return
        # ────────────────────────────────────────────────────────────────────

        if self._stream_chars_emitted == 0:
            self._append_text(response.message)
        self._append_text("\n\n")
        self._set_input_enabled(True)

        if response.ready_to_install and response.actions:
            self._propose_actions(response.actions)

    def _on_llm_error(self, error_msg: str):
        self._stop_spinner()
        self._append_text(f"⚠️  오류: {error_msg}\n다시 시도해주세요.\n\n")
        self._set_input_enabled(True)

    # ── 액션 제안 및 안전 검증 ─────────────────────────────────────────────────

    def _propose_actions(self, actions: List[Action]):
        """
        액션을 분류합니다:
          safe    — 화이트리스트(정적+동적) 통과 + 블랙리스트 없음
          blocked — 블랙리스트 매칭 또는 형식 오류
          unknown — 화이트리스트에 없으나 블랙리스트도 아닌 run/launch 액션
                    → LLM 안전성 검사가 필요합니다.
          retry_items — 보안 규칙으로 차단된 항목 (사용자 거부 제외)
                        → safe_actions가 없을 때 LLM에게 대안 재요청
        """
        safe_actions: List[Action] = []
        blocked: list = []
        unknown: List[Action] = []
        retry_items: list = []  # (display_name, cmd_str, reason)

        for action in actions:
            if isinstance(action, (RunAction, LaunchAction)):
                # 1) 블랙리스트 먼저 확인 (항상 차단)
                in_bl, bl_reason = is_in_blacklist(action.command)
                if in_bl:
                    blocked.append((action.display_name, bl_reason))
                    retry_items.append((action.display_name, " ".join(action.command), bl_reason))
                    continue

                # 2) 화이트리스트 확인
                exe = get_exe_name(action.command)
                if exe in ALLOWED_EXECUTABLES or is_in_dynamic_whitelist(exe):
                    safe_actions.append(action)
                else:
                    unknown.append(action)

            elif isinstance(action, InstallAction):
                ok, reason = self._validate_install(action)
                (safe_actions if ok else blocked).append(
                    action if ok else (action.display_name, reason)
                )

            elif isinstance(action, ContainerSetupAction):
                ok, reason = self._validate_container(action)
                (safe_actions if ok else blocked).append(
                    action if ok else (action.display_name, reason)
                )

            elif isinstance(action, SetEnvAction):
                ok, reason = self._validate_set_env(action)
                (safe_actions if ok else blocked).append(
                    action if ok else (action.display_name, reason)
                )

        if unknown:
            if self.llm:
                # LLM 안전성 검사 — 백그라운드에서 실행
                self._set_input_enabled(False)
                self._append_message(
                    "시스템",
                    f"🔍 화이트리스트에 없는 명령어 {len(unknown)}개의 안전성을 검사 중..."
                )

                def _safety_worker():
                    from core.llm_safety import check_command_safety
                    results = [
                        (act, check_command_safety(act.command, self.llm))
                        for act in unknown
                    ]
                    self.after(0, self._on_safety_results, safe_actions, blocked, retry_items, results)

                threading.Thread(target=_safety_worker, daemon=True).start()
            else:
                # LLM 미연결 시 unknown은 모두 차단
                for action in unknown:
                    blocked.append((action.display_name, "화이트리스트에 없는 명령어 (LLM 미연결)"))
                self._finalize_propose(safe_actions, blocked, retry_items)
        else:
            self._finalize_propose(safe_actions, blocked, retry_items)

    def _on_safety_results(self, safe_actions: List[Action], blocked: list, retry_items: list, results: list):
        """LLM 안전성 검사 결과를 처리합니다 (메인 스레드에서 실행)."""
        from core.llm_safety import SafetyLevel

        auto_caution = os.environ.get("LLM_SAFETY_AUTO_CAUTION", "0") == "1"

        for action, result in results:
            if result.level == SafetyLevel.DANGEROUS:
                blocked.append((action.display_name, f"위험 명령어 차단: {result.reason}"))
                retry_items.append((action.display_name, " ".join(action.command), result.reason))

            elif result.level == SafetyLevel.SAFE:
                add_to_dynamic_whitelist(get_exe_name(action.command))
                safe_actions.append(action)

            else:  # CAUTION
                if auto_caution:
                    add_to_dynamic_whitelist(get_exe_name(action.command))
                    safe_actions.append(action)
                else:
                    cmd_str = " ".join(action.command)
                    dialog = _CautionConfirmDialog(self, cmd_str, result.reason)
                    if dialog.get_result():
                        add_to_dynamic_whitelist(get_exe_name(action.command))
                        safe_actions.append(action)
                    else:
                        blocked.append((action.display_name, f"사용자 거부 — 주의 명령어: {result.reason}"))
                        # 사용자가 직접 거부한 경우는 자동 재시도 대상에서 제외

        self._finalize_propose(safe_actions, blocked, retry_items)

    def _finalize_propose(self, safe_actions: List[Action], blocked: list, retry_items: list = None):
        """안전성 검사가 끝난 후 제안 메시지를 표시하고 상태를 전환합니다."""
        self._set_input_enabled(True)

        if blocked:
            blocked_msg = "\n".join(f"  ✗ {name}: {reason}" for name, reason in blocked)
            self._append_message("시스템", f"⚠️  보안 검사에서 차단됨:\n{blocked_msg}")

        if not safe_actions:
            if retry_items and self.llm:
                self._request_llm_alternative(retry_items)
            else:
                self._append_message("AI", "실행 가능한 액션이 없습니다. 다른 방법을 말씀해주세요.")
            return

        self.pending_actions = safe_actions
        action_list = format_actions_for_display(safe_actions)
        self._append_message(
            "AI",
            f"다음 작업을 진행할까요?\n\n{action_list}\n\n설치하려면 Y, 취소하려면 다른 키를 입력하세요."
        )
        self.app_state = STATE_AWAITING_CONFIRM

    def _request_llm_alternative(self, retry_items: list):
        """보안 규칙으로 차단된 명령어를 LLM에 알리고 대안을 자동으로 요청합니다."""
        lines = "\n".join(
            f"  - {name} (`{cmd}`): {reason}"
            for name, cmd, reason in retry_items
        )
        retry_msg = (
            "[앱 시스템] 제안한 명령어가 보안 규칙으로 차단되어 실행할 수 없습니다:\n"
            f"{lines}\n\n"
            "위 방법 대신, 동일한 목표를 달성할 수 있는 다른 방법을 제안해 주세요. "
            "가능하면 winget, 공식 패키지 관리자, 또는 허용된 CLI 도구를 사용해 주세요."
        )
        self._append_message("시스템", "🔄 LLM에게 대안을 요청합니다...")
        self._send_to_llm_async(retry_msg)

    @staticmethod
    def _validate_install(action: InstallAction) -> tuple:
        pid = action.package_id.strip()
        if not pid:
            return False, "패키지 ID가 비어 있습니다."
        if not _PACKAGE_ID_RE.match(pid):
            return False, f"잘못된 패키지 ID 형식: '{pid}'"
        return True, ""

    @staticmethod
    def _validate_set_env(action: SetEnvAction) -> tuple:
        key = action.key.strip()
        if not _ENV_KEY_RE.match(key):
            return False, f"잘못된 환경변수명 형식: '{key}'"
        if key not in _ALLOWED_ENV_KEYS:
            return False, f"허용되지 않은 환경변수: '{key}' (화이트리스트에 없음)"
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
        has_install_actions = any(
            isinstance(a, InstallAction) for a in self.pending_actions
        )
        if has_install_actions and not self.installer:
            self._append_message(
                "AI",
                "winget을 찾을 수 없습니다.\n"
                "Windows 10 1709 이상에서 winget이 설치되어 있는지 확인해주세요."
            )
            self.app_state = STATE_CHATTING
            return

        self.app_state = STATE_INSTALLING
        self._install_stop_event = threading.Event()
        self._set_input_enabled(False)
        self._set_installing_mode(True)
        spinner_label = self._get_operation_label(self.pending_actions)
        op_label = spinner_label.replace(' 진행 중', '')
        # 한국어 조사: 마지막 글자에 받침 없으면 '를', 있으면 '을'
        last = op_label[-1] if op_label else ""
        particle = "을" if last and (ord(last) - 0xAC00) % 28 != 0 else "를"
        self._append_message("AI", f"{op_label}{particle} 시작합니다. 잠시 기다려주세요...\n")
        self._start_spinner(spinner_label)
        threading.Thread(target=self._run_installation, daemon=True).start()

    def _run_installation(self):
        """백그라운드에서 액션들을 순서대로 실행합니다."""
        stop = self._install_stop_event
        install_actions   = [a for a in self.pending_actions if isinstance(a, InstallAction)]
        run_actions       = [a for a in self.pending_actions if isinstance(a, RunAction)]
        set_env_actions   = [a for a in self.pending_actions if isinstance(a, SetEnvAction)]
        container_actions = [a for a in self.pending_actions if isinstance(a, ContainerSetupAction)]
        launch_actions    = [a for a in self.pending_actions if isinstance(a, LaunchAction)]

        success = True
        recorded_packages: List[str] = []
        failure_logs: List[str] = []   # 실패한 액션의 (이름, 출력) 요약

        def _make_collectors(display_name: str):
            """액션별 출력 수집기를 반환합니다."""
            lines: List[str] = []
            def on_out(line: str):
                lines.append(line.rstrip())
                self.after(0, self._append_text, line)
            def on_err(msg: str):
                lines.append(f"[오류] {msg}")
                self.after(0, self._append_text, f"[오류] {msg}")
            def flush_on_fail():
                tail = "\n".join(lines[-30:])  # 마지막 30줄만
                failure_logs.append(f"[{display_name}]\n{tail}")
            return on_out, on_err, flush_on_fail

        # 1) 패키지 설치 (winget)
        for action in install_actions:
            if stop.is_set():
                break
            self.after(0, self._append_text, f"━━━ {action.display_name} ━━━\n")

            if action.check_command and shutil.which(action.check_command):
                self.after(0, self._append_text, "✓ 이미 설치되어 있습니다.\n\n")
                continue

            on_out, on_err, flush_fail = _make_collectors(action.display_name)
            cmd = self.installer.build_install_command(action.package_id)
            ok = run_command(cmd, on_output=on_out, on_error=on_err, stop_event=stop)
            self.after(0, self._append_text, "\n")
            recorded_packages.append(action.display_name)
            if not ok:
                success = False
                flush_fail()

        # 2) 추가 명령어 실행 (npm install 등)
        for action in run_actions:
            if stop.is_set():
                break
            self.after(0, self._append_text, f"━━━ {action.display_name} ━━━\n")
            on_out, on_err, flush_fail = _make_collectors(action.display_name)
            ok = run_command(action.command, on_output=on_out, on_error=on_err, stop_event=stop)
            self.after(0, self._append_text, "\n")
            if not ok:
                success = False
                flush_fail()

        # 3) API 키 등 환경변수 설정 (사용자 입력 필요 → 메인 스레드 다이얼로그)
        for action in set_env_actions:
            if stop.is_set():
                break
            done = threading.Event()
            self.after(0, self._prompt_env_key, action, done)
            done.wait(timeout=300)  # 최대 5분 대기

        # 4) D: 컨테이너 세팅
        for action in container_actions:
            if stop.is_set():
                break
            self._run_container_setup(action)
            recorded_packages.append(action.display_name)

        cancelled = stop.is_set()
        self.after(
            0, self._on_installation_done, success, launch_actions, recorded_packages,
            cancelled, failure_logs
        )

    def _prompt_env_key(self, action: SetEnvAction, done: threading.Event):
        """메인 스레드에서 API 키 입력 다이얼로그를 표시하고 시스템 환경변수를 설정합니다."""
        hint_text = f"힌트: {action.hint}" if action.hint else ""
        dialog = _SecureInputDialog(
            self,
            title=action.display_name,
            text=f"{action.display_name} ({action.key}) 를 입력하세요.\n{hint_text}",
        )
        value = dialog.get_input()
        if value and value.strip():
            ok = _set_system_env(action.key, value.strip())
            msg = (
                f"✓ {action.key} 설정 완료\n"
                if ok else
                f"⚠️  {action.key} 시스템 등록 실패 — 수동으로 환경변수를 설정해주세요.\n"
            )
        else:
            msg = f"⚠️  {action.display_name} 입력이 취소됐습니다.\n"
        self._append_text(msg)
        done.set()

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
        recorded_packages: List[str], cancelled: bool = False,
        failure_logs: List[str] = None,
    ):
        self.pending_actions.clear()
        self._stop_spinner()
        self._set_installing_mode(False)
        self._set_input_enabled(True)
        self.app_state = STATE_CHATTING

        if cancelled:
            self._append_message("시스템", "설치가 취소됐습니다.")
            self._send_to_llm_async("사용자가 설치를 취소했습니다. 다시 도와주세요.")
            return

        # F: 이력 기록 및 LLM 컨텍스트 갱신
        if recorded_packages:
            self.history_manager.record(recorded_packages, success)
            if self.llm:
                history_ctx = self.history_manager.format_for_llm()
                self.llm.set_context(self.llm._env_context, history_ctx)

        result_msg = "설치가 완료됐습니다! ✓" if success else (
            "일부 설치에 실패했습니다. 관리자 권한으로 재시도하거나 패키지 관리자 버전을 확인해주세요."
        )
        self._append_message("시스템", result_msg)

        if success:
            context_msg = (
                f"설치 성공.\n실행할 앱 목록: {[a.display_name for a in launch_actions]}"
                if launch_actions else
                "설치가 모두 성공했습니다. 다음 단계를 안내해주세요."
            )
        else:
            log_detail = (
                "\n\n다음은 실패한 항목의 출력 로그입니다:\n"
                + "\n---\n".join(failure_logs)
                if failure_logs else ""
            )
            context_msg = (
                f"[앱 시스템] 설치 중 일부 항목이 실패했습니다.{log_detail}\n\n"
                "위 오류 로그를 바탕으로 원인을 분석하고, "
                "해결 방법(재시도 방법, 대안 명령어, 권한 문제 해소 방법 등)을 구체적으로 안내해 주세요. "
                "사용자에게 오류 원인을 직접 묻지 마세요."
            )
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
    # 관리자 권한이 없으면 UAC 프롬프트를 띄우고 현재 프로세스 종료
    if not is_admin():
        relaunch_as_admin()
        raise SystemExit(0)
    app = DevSetupApp()
    app.mainloop()
