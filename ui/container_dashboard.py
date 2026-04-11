"""
컨테이너 관리 대시보드 — CTkFrame 위젯
"""
import threading
import tkinter as tk
import customtkinter as ctk


_STATUS_COLOR = {
    "running": "#2ecc71",
    "up":      "#2ecc71",
    "exited":  "#e74c3c",
    "stopped": "#e74c3c",
    "created": "#f39c12",
    "paused":  "#f39c12",
}


def _status_color(status: str) -> str:
    s = status.lower()
    for key, color in _STATUS_COLOR.items():
        if key in s:
            return color
    return "#95a5a6"


def _is_running(status: str) -> bool:
    s = status.lower()
    return "up" in s or "running" in s


class _LogWindow(ctk.CTkToplevel):
    """컨테이너 로그를 표시하는 팝업 창"""

    def __init__(self, parent, container_name: str):
        super().__init__(parent)
        self.title(f"로그 — {container_name}")
        self.geometry("760x480")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._name = container_name

        # 헤더
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hdr, text=f"🐳 {container_name} — 최근 로그",
            font=("Malgun Gothic", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            hdr, text="새로고침", width=80, height=28,
            command=self._load,
        ).grid(row=0, column=1, padx=(8, 0))

        # 로그 텍스트박스
        self._box = ctk.CTkTextbox(
            self, font=("Consolas", 12), state="disabled",
        )
        self._box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self._load()

    def _load(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        from core.container_manager import get_container_logs
        text = get_container_logs(self._name, lines=200)
        self.after(0, self._set_text, text or "(로그 없음)")

    def _set_text(self, text: str):
        self._box.configure(state="normal")
        self._box.delete("1.0", "end")
        self._box.insert("end", text)
        self._box.see("end")
        self._box.configure(state="disabled")


class ContainerDashboard(ctk.CTkFrame):
    """전체 컨테이너 목록을 표시하고 제어하는 대시보드 프레임"""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._log_windows: dict = {}
        self._build()
        self.refresh()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── 헤더 ──
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        self._title_label = ctk.CTkLabel(
            hdr, text="🐳 컨테이너 관리",
            font=("Malgun Gothic", 15, "bold"),
        )
        self._title_label.grid(row=0, column=0, sticky="w")

        self._docker_status_label = ctk.CTkLabel(
            hdr, text="", font=("Malgun Gothic", 12), text_color="gray60",
        )
        self._docker_status_label.grid(row=0, column=1, padx=(8, 0))

        ctk.CTkButton(
            hdr, text="⟳ 새로고침", width=90, height=28,
            font=("Malgun Gothic", 12),
            command=self.refresh,
        ).grid(row=0, column=2, padx=(8, 0))

        # ── 컨테이너 리스트 (스크롤 가능) ──
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", label_text="",
        )
        self._list_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self._list_frame.grid_columnconfigure(0, weight=1)

    def refresh(self):
        """백그라운드에서 컨테이너 목록을 갱신합니다."""
        self._docker_status_label.configure(text="조회 중...")
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        from core.container import detect_docker
        from core.container_manager import list_all_containers
        docker = detect_docker()
        containers = list_all_containers() if docker.installed else []
        self.after(0, self._update_ui, docker, containers)

    def _update_ui(self, docker, containers):
        from core.container import DockerStatus
        # Docker 상태 레이블
        if not docker.installed:
            self._docker_status_label.configure(text="Docker 미설치", text_color="#e74c3c")
        elif not docker.running:
            self._docker_status_label.configure(text="Docker 데몬 미실행", text_color="#f39c12")
        else:
            ver = docker.version or "설치됨"
            self._docker_status_label.configure(
                text=f"● {ver}", text_color="#2ecc71",
            )

        # 기존 행 삭제
        for w in self._list_frame.winfo_children():
            w.destroy()

        if not containers:
            self._empty_label = ctk.CTkLabel(
                self._list_frame,
                text="컨테이너가 없습니다.\n채팅에서 'Docker로 개발환경 만들어줘'라고 입력해보세요.",
                font=("Malgun Gothic", 13), text_color="gray50",
            )
            self._empty_label.grid(row=0, column=0, pady=40)
            return

        # 열 헤더
        hdr = ctk.CTkFrame(self._list_frame, fg_color="gray20", corner_radius=6)
        hdr.grid(row=0, column=0, padx=2, pady=(0, 4), sticky="ew")
        for col, (text, w) in enumerate([
            ("상태", 50), ("이름", 160), ("이미지", 160), ("포트", 140), ("", 200),
        ]):
            ctk.CTkLabel(
                hdr, text=text, width=w,
                font=("Malgun Gothic", 11), text_color="gray60",
            ).grid(row=0, column=col, padx=4, pady=4, sticky="w")

        for i, c in enumerate(containers):
            self._build_row(i + 1, c)

    def _build_row(self, row_idx: int, c):
        bg = "gray17" if row_idx % 2 == 0 else "gray15"
        row = ctk.CTkFrame(self._list_frame, fg_color=bg, corner_radius=6)
        row.grid(row=row_idx, column=0, padx=2, pady=2, sticky="ew")

        running = _is_running(c.status)
        color   = _status_color(c.status)

        # 상태 점
        dot = ctk.CTkLabel(row, text="●", width=50, text_color=color,
                           font=("Malgun Gothic", 14))
        dot.grid(row=0, column=0, padx=4, pady=6)

        # 이름
        ctk.CTkLabel(
            row, text=c.name[:22], width=160,
            font=("Malgun Gothic", 12, "bold"), anchor="w",
        ).grid(row=0, column=1, padx=4, pady=6, sticky="w")

        # 이미지
        ctk.CTkLabel(
            row, text=c.image[:22], width=160,
            font=("Consolas", 11), text_color="gray70", anchor="w",
        ).grid(row=0, column=2, padx=4, pady=6, sticky="w")

        # 포트
        ports_text = c.ports[:20] if c.ports else "-"
        ctk.CTkLabel(
            row, text=ports_text, width=140,
            font=("Consolas", 11), text_color="gray60", anchor="w",
        ).grid(row=0, column=3, padx=4, pady=6, sticky="w")

        # 버튼 묶음
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.grid(row=0, column=4, padx=(4, 8), pady=4, sticky="e")

        name = c.name  # closure capture

        if running:
            ctk.CTkButton(
                btn_frame, text="■ 중지", width=64, height=26,
                font=("Malgun Gothic", 11),
                fg_color="#8B1A1A", hover_color="#6B1212",
                command=lambda n=name: self._action(n, "stop"),
            ).pack(side="left", padx=2)
        else:
            ctk.CTkButton(
                btn_frame, text="▶ 시작", width=64, height=26,
                font=("Malgun Gothic", 11),
                fg_color="#1A5C1A", hover_color="#145014",
                command=lambda n=name: self._action(n, "start"),
            ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="🖥 진입", width=60, height=26,
            font=("Malgun Gothic", 11),
            fg_color="gray35", hover_color="gray25",
            command=lambda n=name: self._exec(n),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="📋 로그", width=60, height=26,
            font=("Malgun Gothic", 11),
            fg_color="gray35", hover_color="gray25",
            command=lambda n=name: self._show_logs(n),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="✕", width=30, height=26,
            font=("Malgun Gothic", 12),
            fg_color="gray30", hover_color="#8B1A1A",
            command=lambda n=name: self._confirm_remove(n),
        ).pack(side="left", padx=2)

    def _action(self, name: str, action: str):
        def _worker():
            from core.container_manager import start_container, stop_container
            if action == "start":
                start_container(name)
            else:
                stop_container(name)
            self.after(500, self.refresh)
        threading.Thread(target=_worker, daemon=True).start()

    def _exec(self, name: str):
        from core.container_manager import exec_container_in_terminal
        exec_container_in_terminal(name)

    def _show_logs(self, name: str):
        if name in self._log_windows:
            try:
                self._log_windows[name].lift()
                return
            except Exception:
                pass
        win = _LogWindow(self, name)
        self._log_windows[name] = win

    def _confirm_remove(self, name: str):
        dlg = ctk.CTkInputDialog(
            text=f"컨테이너 '{name}'을(를) 삭제하려면 이름을 입력하세요:",
            title="컨테이너 삭제 확인",
        )
        val = dlg.get_input()
        if val and val.strip() == name:
            def _worker():
                from core.container_manager import remove_container
                remove_container(name)
                self.after(500, self.refresh)
            threading.Thread(target=_worker, daemon=True).start()
