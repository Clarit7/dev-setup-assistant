"""
WSL 관리 탭
"""
import threading
import tkinter as tk
import customtkinter as ctk


class WSLTab(ctk.CTkFrame):
    """WSL 배포판 관리 탭 프레임"""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self.refresh()

    def _build(self):
        # ── 헤더 ──
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr, text="🐧 WSL 관리",
            font=("Malgun Gothic", 15, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self._wsl_ver_label = ctk.CTkLabel(
            hdr, text="", font=("Malgun Gothic", 12), text_color="gray60",
        )
        self._wsl_ver_label.grid(row=0, column=1, padx=8)

        ctk.CTkButton(
            hdr, text="⟳ 새로고침", width=90, height=28,
            font=("Malgun Gothic", 12), command=self.refresh,
        ).grid(row=0, column=2)

        # ── 배포판 리스트 ──
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
        )
        self._list_frame.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

        # ── 새 배포판 설치 섹션 ──
        install_frame = ctk.CTkFrame(self, fg_color="gray17", corner_radius=8)
        install_frame.grid(row=2, column=0, padx=8, pady=(4, 8), sticky="ew")
        install_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            install_frame, text="새 배포판 설치",
            font=("Malgun Gothic", 13, "bold"),
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 6), sticky="w")

        ctk.CTkLabel(
            install_frame, text="배포판:",
            font=("Malgun Gothic", 12),
        ).grid(row=1, column=0, padx=(12, 8), pady=(0, 10))

        self._distro_var = tk.StringVar(value="Ubuntu")
        self._distro_combo = ctk.CTkOptionMenu(
            install_frame,
            variable=self._distro_var,
            values=["Ubuntu", "Ubuntu-24.04", "Ubuntu-22.04", "Debian", "kali-linux", "openSUSE-Leap-15.6"],
            font=("Malgun Gothic", 12),
            width=200,
        )
        self._distro_combo.grid(row=1, column=1, padx=(0, 8), pady=(0, 10), sticky="ew")

        self._install_btn = ctk.CTkButton(
            install_frame, text="설치", width=80, height=30,
            font=("Malgun Gothic", 12),
            command=self._install_distro,
        )
        self._install_btn.grid(row=1, column=2, padx=(0, 12), pady=(0, 10))

        self._install_status = ctk.CTkLabel(
            install_frame, text="", font=("Malgun Gothic", 12),
        )
        self._install_status.grid(row=2, column=0, columnspan=3,
                                  padx=12, pady=(0, 10), sticky="w")

    def refresh(self):
        self._wsl_ver_label.configure(text="조회 중...")
        threading.Thread(target=self._fetch, daemon=True).start()
        # 온라인 배포판 목록도 백그라운드에서 가져오기
        threading.Thread(target=self._fetch_online_distros, daemon=True).start()

    def _fetch(self):
        from core.wsl import list_wsl_distros, is_wsl_available
        if not is_wsl_available():
            self.after(0, self._show_unavailable)
            return
        distros = list_wsl_distros()
        self.after(0, self._update_ui, distros)

    def _fetch_online_distros(self):
        from core.wsl import get_available_distros_online
        names = get_available_distros_online()
        self.after(0, self._distro_combo.configure, {"values": names})
        if names:
            self.after(0, self._distro_var.set, names[0])

    def _show_unavailable(self):
        self._wsl_ver_label.configure(text="WSL 미설치", text_color="#e74c3c")
        for w in self._list_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._list_frame,
            text=(
                "WSL이 설치되어 있지 않습니다.\n\n"
                "관리자 권한 PowerShell에서:\n"
                "  wsl --install\n\n"
                "또는 채팅에서 'WSL Ubuntu 설치해줘'라고 입력하세요."
            ),
            font=("Malgun Gothic", 13), text_color="gray50",
            justify="left",
        ).grid(row=0, column=0, pady=40, padx=20, sticky="w")

    def _update_ui(self, distros):
        self._wsl_ver_label.configure(
            text=f"● WSL 설치됨 ({len(distros)}개 배포판)",
            text_color="#2ecc71" if distros else "gray60",
        )

        for w in self._list_frame.winfo_children():
            w.destroy()

        if not distros:
            ctk.CTkLabel(
                self._list_frame,
                text="설치된 배포판이 없습니다. 아래에서 설치하세요.",
                font=("Malgun Gothic", 13), text_color="gray50",
            ).grid(row=0, column=0, pady=40)
            return

        # 열 헤더
        hdr = ctk.CTkFrame(self._list_frame, fg_color="gray20", corner_radius=6)
        hdr.grid(row=0, column=0, padx=2, pady=(0, 4), sticky="ew")
        for col, (text, w) in enumerate([
            ("", 40), ("배포판", 200), ("WSL", 60), ("상태", 80), ("", 200),
        ]):
            ctk.CTkLabel(
                hdr, text=text, width=w,
                font=("Malgun Gothic", 11), text_color="gray60",
            ).grid(row=0, column=col, padx=4, pady=4, sticky="w")

        for i, d in enumerate(distros):
            self._build_distro_row(i + 1, d)

    def _build_distro_row(self, row_idx: int, d):
        bg = "gray17" if row_idx % 2 == 0 else "gray15"
        row = ctk.CTkFrame(self._list_frame, fg_color=bg, corner_radius=6)
        row.grid(row=row_idx, column=0, padx=2, pady=2, sticky="ew")

        is_running = d.state.lower() == "running"
        state_color = "#2ecc71" if is_running else "gray50"

        # 기본값 표시
        ctk.CTkLabel(
            row, text="★" if d.is_default else "",
            width=40, font=("Malgun Gothic", 13), text_color="#f39c12",
        ).grid(row=0, column=0, padx=4, pady=6)

        ctk.CTkLabel(
            row, text=d.name, width=200,
            font=("Malgun Gothic", 12, "bold"), anchor="w",
        ).grid(row=0, column=1, padx=4, pady=6, sticky="w")

        ctk.CTkLabel(
            row, text=f"WSL{d.version}", width=60,
            font=("Consolas", 11), text_color="gray60",
        ).grid(row=0, column=2, padx=4, pady=6)

        ctk.CTkLabel(
            row, text=d.state, width=80,
            font=("Malgun Gothic", 11), text_color=state_color,
        ).grid(row=0, column=3, padx=4, pady=6)

        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.grid(row=0, column=4, padx=(4, 8), pady=4, sticky="e")

        name = d.name

        ctk.CTkButton(
            btn_frame, text="🖥 열기", width=70, height=26,
            font=("Malgun Gothic", 11),
            fg_color="gray35", hover_color="gray25",
            command=lambda n=name: self._open_terminal(n),
        ).pack(side="left", padx=2)

        if not d.is_default:
            ctk.CTkButton(
                btn_frame, text="기본값 설정", width=90, height=26,
                font=("Malgun Gothic", 11),
                fg_color="gray35", hover_color="gray25",
                command=lambda n=name: self._set_default(n),
            ).pack(side="left", padx=2)

        target_ver = 1 if d.version == 2 else 2
        ctk.CTkButton(
            btn_frame, text=f"WSL{target_ver}으로 변환", width=110, height=26,
            font=("Malgun Gothic", 11),
            fg_color="gray30", hover_color="gray20",
            command=lambda n=name, v=target_ver: self._convert_version(n, v),
        ).pack(side="left", padx=2)

    def _open_terminal(self, name: str):
        from core.wsl import open_wsl_terminal
        open_wsl_terminal(name)

    def _set_default(self, name: str):
        def _worker():
            from core.wsl import set_default_distro
            ok = set_default_distro(name)
            self.after(0, self.refresh)
        threading.Thread(target=_worker, daemon=True).start()

    def _convert_version(self, name: str, version: int):
        self._wsl_ver_label.configure(
            text=f"WSL{version} 변환 중... (시간이 걸릴 수 있습니다)",
            text_color="#f39c12",
        )
        def _worker():
            from core.wsl import set_wsl_version
            set_wsl_version(name, version)
            self.after(0, self.refresh)
        threading.Thread(target=_worker, daemon=True).start()

    def _install_distro(self):
        distro = self._distro_var.get()
        self._install_btn.configure(state="disabled")
        self._install_status.configure(
            text=f"⏳ {distro} 설치 중... (시간이 걸릴 수 있습니다)",
            text_color="#f39c12",
        )

        def _worker():
            from core.wsl import install_wsl_distro
            ok = install_wsl_distro(distro)
            msg = f"✓ {distro} 설치 완료 (재부팅이 필요할 수 있습니다)" if ok else f"✗ {distro} 설치 실패"
            color = "#2ecc71" if ok else "#e74c3c"
            self.after(0, self._install_status.configure,
                       {"text": msg, "text_color": color})
            self.after(0, self._install_btn.configure, {"state": "normal"})
            if ok:
                self.after(500, self.refresh)
        threading.Thread(target=_worker, daemon=True).start()
