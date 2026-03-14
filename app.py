"""
개발환경 세팅 도우미 — 메인 GUI

상태머신:
  INIT → (시나리오 매칭) → AWAITING_CONFIRM
       → (y) → INSTALLING → AWAITING_LAUNCH → DONE
               (N) → INIT
"""
import subprocess
import threading
import shutil

import customtkinter as ctk

from core.safety import is_safe_command
from core.runner import run_command
from installers.winget import WingetInstaller
from scenarios.registry import match_scenario, list_supported_scenarios, get_current_os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── 상태 상수 ────────────────────────────────────────────────────────────────
STATE_INIT             = "init"
STATE_AWAITING_CONFIRM = "awaiting_confirm"
STATE_INSTALLING       = "installing"
STATE_AWAITING_LAUNCH  = "awaiting_launch"
STATE_DONE             = "done"

# ── OS별 인스톨러 선택 ────────────────────────────────────────────────────────
_INSTALLERS = {
    "windows": WingetInstaller(),
    # "macos":  BrewInstaller(),   # macOS 지원 시 추가
    # "linux":  AptInstaller(),    # Linux 지원 시 추가
}


def get_installer():
    installer = _INSTALLERS.get(get_current_os())
    if installer and installer.is_available():
        return installer
    return None


# ── GUI ─────────────────────────────────────────────────────────────────────
class DevSetupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("개발환경 세팅 도우미")
        self.geometry("700x600")
        self.minsize(500, 400)

        self.state = STATE_INIT
        self.current_scenario = None
        self.installer = get_installer()

        self._build_ui()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.chat_box = ctk.CTkTextbox(
            self, state="disabled", wrap="word", font=("Malgun Gothic", 14)
        )
        self.chat_box.grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="nsew")

        self.input_field = ctk.CTkEntry(
            self, placeholder_text="메시지를 입력하세요...", font=("Malgun Gothic", 14)
        )
        self.input_field.grid(row=1, column=0, padx=(16, 8), pady=(0, 16), sticky="ew")
        self.input_field.bind("<Return>", lambda e: self._on_send())

        self.send_button = ctk.CTkButton(
            self, text="전송", width=80, font=("Malgun Gothic", 14), command=self._on_send
        )
        self.send_button.grid(row=1, column=1, padx=(0, 16), pady=(0, 16))
        self.grid_rowconfigure(1, minsize=50)

    # ── 채팅창 헬퍼 ──────────────────────────────────────────────────────────

    def _append_message(self, sender: str, message: str):
        """발신자 + 메시지 블록을 추가합니다."""
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{sender}\n{message}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _append_text(self, text: str):
        """발신자 없이 텍스트만 추가합니다 (설치 로그용)."""
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
        text = self.input_field.get().strip()
        if not text:
            return
        self._append_message("나:", text)
        self.input_field.delete(0, "end")
        self._handle_state(text)

    def _handle_state(self, text: str):
        if self.state == STATE_INIT:
            self._handle_init(text)

        elif self.state == STATE_AWAITING_CONFIRM:
            if text.upper() == "Y":
                self._start_installation()
            else:
                self._append_message("AI:", "설치를 취소했습니다. 다른 도움이 필요하시면 말씀해주세요.")
                self._reset()

        elif self.state == STATE_AWAITING_LAUNCH:
            if text.upper() == "Y":
                self._launch_app()
            else:
                self._append_message("AI:", "모든 설정이 완료됐습니다. 즐거운 개발 되세요!")
                self.state = STATE_DONE

    def _handle_init(self, text: str):
        scenario = match_scenario(text)
        if scenario:
            self.current_scenario = scenario
            self._append_message("AI:", scenario.get_proposal_message())
            self.state = STATE_AWAITING_CONFIRM
        else:
            supported = list_supported_scenarios()
            names = "\n".join(f"  • {s.description}" for s in supported)
            self._append_message(
                "AI:",
                f"죄송합니다. 아직 해당 요청을 지원하지 않습니다.\n\n현재 지원 시나리오:\n{names}"
            )

    def _reset(self):
        self.state = STATE_INIT
        self.current_scenario = None

    # ── 설치 ─────────────────────────────────────────────────────────────────

    def _start_installation(self):
        if not self.installer:
            self._append_message(
                "AI:",
                "현재 OS에서 지원하는 패키지 관리자를 찾을 수 없습니다.\n"
                "winget(Windows), brew(macOS), apt(Ubuntu) 등이 설치되어 있는지 확인해주세요."
            )
            self._reset()
            return

        self.state = STATE_INSTALLING
        self._set_input_enabled(False)
        self._append_message("AI:", "설치를 시작합니다. 잠시 기다려주세요...\n")
        threading.Thread(target=self._run_installation, daemon=True).start()

    def _run_installation(self):
        packages = self.current_scenario.get_packages()
        success = True

        for pkg in packages:
            self.after(0, self._append_text, f"━━━ {pkg.display_name} ━━━\n")

            if shutil.which(pkg.check_command):
                self.after(0, self._append_text, f"✓ 이미 설치되어 있습니다.\n\n")
                continue

            package_id = pkg.package_ids.get(self.installer.installer_type)
            if not package_id:
                self.after(
                    0, self._append_text,
                    f"✗ 현재 패키지 관리자({self.installer.installer_type})에서 "
                    f"{pkg.display_name} 지원 정보가 없습니다.\n\n"
                )
                success = False
                continue

            cmd = self.installer.build_install_command(package_id)
            ok = run_command(
                cmd,
                on_output=lambda line: self.after(0, self._append_text, line),
                on_error=lambda msg: self.after(0, self._append_text, f"[오류] {msg}"),
            )
            self.after(0, self._append_text, "\n")
            if not ok:
                success = False

        self.after(0, self._on_installation_done, success)

    def _on_installation_done(self, success: bool):
        self._set_input_enabled(True)
        launch = self.current_scenario.get_launch()

        if success and launch:
            self._append_message(
                "AI:",
                f"설치가 모두 완료됐습니다!\n\n{launch.display_name}를 지금 실행할까요? (y/N)"
            )
            self.state = STATE_AWAITING_LAUNCH
        elif success:
            self._append_message("AI:", "설치가 모두 완료됐습니다! 즐거운 개발 되세요!")
            self.state = STATE_DONE
        else:
            self._append_message(
                "AI:",
                "일부 설치에 실패했습니다.\n"
                "관리자 권한으로 다시 실행하거나, 패키지 관리자가 최신 버전인지 확인해주세요."
            )
            self._reset()

    # ── 앱 실행 ──────────────────────────────────────────────────────────────

    def _launch_app(self):
        launch = self.current_scenario.get_launch()
        if not launch:
            return

        safe, reason = is_safe_command(launch.command)
        if not safe:
            self._append_message("AI:", f"[보안 차단] 실행이 차단됐습니다: {reason}")
            self.state = STATE_DONE
            return

        try:
            subprocess.Popen(launch.command, shell=True)
            self._append_message("AI:", f"{launch.display_name}를 실행했습니다. 즐거운 개발 되세요!")
        except Exception as e:
            self._append_message("AI:", f"{launch.display_name} 실행에 실패했습니다: {e}")

        self.state = STATE_DONE


# ── 진입점 ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = DevSetupApp()
    app.mainloop()
