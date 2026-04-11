"""
Git 초기 설정 탭 — 사용자 정보, SSH 키, 원격 연결 테스트
"""
import threading
import tkinter as tk
import customtkinter as ctk


class GitTab(ctk.CTkScrollableFrame):
    """Git 설정 탭 프레임"""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self._ssh_key_info = None
        self._build()
        self.refresh()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build(self):
        row = 0

        # ── 섹션 1: Git 사용자 정보 ──────────────────────────────────────────
        row = self._section_header(row, "👤 Git 사용자 정보")

        self._name_var  = tk.StringVar()
        self._email_var = tk.StringVar()
        self._branch_var = tk.StringVar(value="main")

        row = self._config_row(row, "이름 (user.name)",   self._name_var,  "name")
        row = self._config_row(row, "이메일 (user.email)", self._email_var, "email")
        row = self._config_row(row, "기본 브랜치 (init.defaultBranch)", self._branch_var, "branch")

        self._git_status_label = ctk.CTkLabel(
            self, text="", font=("Malgun Gothic", 12),
        )
        self._git_status_label.grid(row=row, column=0, padx=16, pady=(0, 8), sticky="w")
        row += 1

        self._separator(row); row += 1

        # ── 섹션 2: SSH 키 ────────────────────────────────────────────────────
        row = self._section_header(row, "🔑 SSH 키")

        # 키 상태 행
        self._ssh_status_label = ctk.CTkLabel(
            self, text="확인 중...", font=("Malgun Gothic", 12),
        )
        self._ssh_status_label.grid(row=row, column=0, padx=16, pady=(4, 4), sticky="w")
        row += 1

        # 공개키 표시 프레임
        self._pubkey_frame = ctk.CTkFrame(self, fg_color="gray20", corner_radius=6)
        self._pubkey_frame.grid(row=row, column=0, padx=16, pady=(0, 4), sticky="ew")
        self._pubkey_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self._pubkey_frame,
            text="공개키 (Public Key) — GitHub·GitLab에 등록하는 값으로, 공유해도 안전합니다.\n개인키(Private Key)는 표시되지 않습니다.",
            font=("Malgun Gothic", 11), text_color="gray55",
            justify="left",
        ).grid(row=0, column=0, padx=8, pady=(8, 2), sticky="w")
        self._pubkey_box = ctk.CTkTextbox(
            self._pubkey_frame, height=60, state="disabled",
            font=("Consolas", 11), wrap="char",
        )
        self._pubkey_box.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
        ctk.CTkButton(
            self._pubkey_frame, text="📋 공개키 복사", height=28,
            font=("Malgun Gothic", 12),
            command=self._copy_pubkey,
        ).grid(row=2, column=0, padx=8, pady=(0, 8), sticky="w")
        self._pubkey_frame.grid_remove()
        row += 1

        # SSH 키 생성 프레임
        self._keygen_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._keygen_frame.grid(row=row, column=0, padx=16, pady=(0, 4), sticky="ew")
        self._keygen_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self._keygen_frame, text="이메일:",
            font=("Malgun Gothic", 12),
        ).grid(row=0, column=0, padx=(0, 8), pady=4)
        self._keygen_email_var = tk.StringVar()
        ctk.CTkEntry(
            self._keygen_frame, textvariable=self._keygen_email_var,
            font=("Malgun Gothic", 12), placeholder_text="git@example.com",
        ).grid(row=0, column=1, pady=4, sticky="ew")
        ctk.CTkButton(
            self._keygen_frame, text="🔑 SSH 키 생성 (ed25519)", height=30,
            font=("Malgun Gothic", 12),
            command=self._generate_key,
        ).grid(row=0, column=2, padx=(8, 0), pady=4)
        row += 1

        self._keygen_result_label = ctk.CTkLabel(
            self, text="", font=("Malgun Gothic", 12),
        )
        self._keygen_result_label.grid(row=row, column=0, padx=16, pady=(0, 8), sticky="w")
        row += 1

        self._separator(row); row += 1

        # ── 섹션 3: 원격 연결 테스트 ─────────────────────────────────────────
        row = self._section_header(row, "🌐 원격 연결 테스트")

        test_frame = ctk.CTkFrame(self, fg_color="transparent")
        test_frame.grid(row=row, column=0, padx=16, pady=(4, 4), sticky="ew")
        row += 1

        for text, host in [("GitHub 테스트", "github.com"), ("GitLab 테스트", "gitlab.com")]:
            ctk.CTkButton(
                test_frame, text=text, height=30,
                font=("Malgun Gothic", 12), width=140,
                command=lambda h=host: self._test_connection(h),
            ).pack(side="left", padx=(0, 8))

        self._connection_label = ctk.CTkLabel(
            self, text="", font=("Malgun Gothic", 12),
        )
        self._connection_label.grid(row=row, column=0, padx=16, pady=(0, 16), sticky="w")
        row += 1

    def _section_header(self, row: int, text: str) -> int:
        ctk.CTkLabel(
            self, text=text,
            font=("Malgun Gothic", 14, "bold"),
        ).grid(row=row, column=0, padx=16, pady=(16, 8), sticky="w")
        return row + 1

    def _separator(self, row: int):
        tk.Frame(self, height=1, bg="#3d3d3d").grid(
            row=row, column=0, padx=16, pady=4, sticky="ew",
        )

    def _config_row(self, row: int, label: str, var: tk.StringVar, field: str) -> int:
        f = ctk.CTkFrame(self, fg_color="transparent")
        f.grid(row=row, column=0, padx=16, pady=2, sticky="ew")
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text=label, width=240,
                     font=("Malgun Gothic", 12), anchor="w").grid(
            row=0, column=0, padx=(0, 8))

        ctk.CTkEntry(f, textvariable=var,
                     font=("Malgun Gothic", 12)).grid(
            row=0, column=1, sticky="ew")

        ctk.CTkButton(
            f, text="저장", width=60, height=28,
            font=("Malgun Gothic", 12),
            command=lambda fld=field, v=var: self._save_config(fld, v),
        ).grid(row=0, column=2, padx=(8, 0))
        return row + 1

    # ── 동작 ─────────────────────────────────────────────────────────────────

    def refresh(self):
        threading.Thread(target=self._fetch_git_config, daemon=True).start()
        threading.Thread(target=self._fetch_ssh_key, daemon=True).start()

    def _fetch_git_config(self):
        from core.git_setup import get_git_config, is_git_installed
        if not is_git_installed():
            self.after(0, self._git_status_label.configure,
                       {"text": "⚠️  Git이 설치되어 있지 않습니다.", "text_color": "#e74c3c"})
            return
        cfg = get_git_config()
        self.after(0, self._apply_git_config, cfg)

    def _apply_git_config(self, cfg):
        self._name_var.set(cfg.user_name)
        self._email_var.set(cfg.user_email)
        if cfg.default_branch:
            self._branch_var.set(cfg.default_branch)
        # 이메일이 있으면 keygen 필드에도 채워두기
        if cfg.user_email:
            self._keygen_email_var.set(cfg.user_email)
        self._git_status_label.configure(text="", text_color="gray60")

    def _fetch_ssh_key(self):
        from core.git_setup import detect_ssh_key
        info = detect_ssh_key()
        self._ssh_key_info = info
        self.after(0, self._apply_ssh_status, info)

    def _apply_ssh_status(self, info):
        if info.exists:
            self._ssh_status_label.configure(
                text=f"✓ {info.key_type} 키 존재  ({info.key_path})",
                text_color="#2ecc71",
            )
            self._pubkey_box.configure(state="normal")
            self._pubkey_box.delete("1.0", "end")
            self._pubkey_box.insert("end", info.public_key)
            self._pubkey_box.configure(state="disabled")
            self._pubkey_frame.grid()
        else:
            self._ssh_status_label.configure(
                text="✗ SSH 키 없음 — 아래에서 생성하세요.",
                text_color="#e74c3c",
            )
            self._pubkey_frame.grid_remove()

    def _save_config(self, field: str, var: tk.StringVar):
        value = var.get().strip()
        if not value:
            return
        key_map = {
            "name":   "user.name",
            "email":  "user.email",
            "branch": "init.defaultBranch",
        }
        from core.git_setup import set_git_config
        ok = set_git_config(key_map[field], value)
        msg = f"✓ {key_map[field]} 저장됨" if ok else f"⚠️  저장 실패"
        self._git_status_label.configure(
            text=msg, text_color="#2ecc71" if ok else "#e74c3c",
        )

    def _copy_pubkey(self):
        if self._ssh_key_info and self._ssh_key_info.public_key:
            self.clipboard_clear()
            self.clipboard_append(self._ssh_key_info.public_key)
            self._git_status_label.configure(
                text="✓ 공개키가 클립보드에 복사됐습니다.",
                text_color="#2ecc71",
            )

    def _generate_key(self):
        email = self._keygen_email_var.get().strip()
        if not email:
            self._keygen_result_label.configure(
                text="⚠️  이메일을 입력해주세요.", text_color="#f39c12",
            )
            return
        self._keygen_result_label.configure(text="생성 중...", text_color="gray60")

        def _worker():
            from core.git_setup import generate_ssh_key, detect_ssh_key
            ok, msg = generate_ssh_key(email)
            if ok:
                info = detect_ssh_key()
                self.after(0, self._apply_ssh_status, info)
                self.after(0, self._keygen_result_label.configure,
                           {"text": f"✓ SSH 키 생성 완료: {msg}", "text_color": "#2ecc71"})
            else:
                self.after(0, self._keygen_result_label.configure,
                           {"text": f"⚠️  생성 실패: {msg}", "text_color": "#e74c3c"})
        threading.Thread(target=_worker, daemon=True).start()

    def _test_connection(self, host: str):
        self._connection_label.configure(
            text=f"⏳ {host} 연결 테스트 중...", text_color="gray60",
        )

        def _worker():
            from core.git_setup import test_remote_connection
            result = test_remote_connection(host)
            msg_map = {
                "success":          (f"✓ {host} 인증 성공!", "#2ecc71"),
                "permission_denied":(f"✗ {host} 권한 거부 — 공개키를 {host} 계정에 등록하세요.", "#e74c3c"),
                "no_ssh":           ("⚠️  ssh 클라이언트를 찾을 수 없습니다.", "#f39c12"),
                "failed":           (f"✗ {host} 연결 실패 — 네트워크 또는 키 설정을 확인하세요.", "#e74c3c"),
            }
            text, color = msg_map.get(result, ("알 수 없는 결과", "gray60"))
            self.after(0, self._connection_label.configure,
                       {"text": text, "text_color": color})
        threading.Thread(target=_worker, daemon=True).start()
