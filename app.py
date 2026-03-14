import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class DevSetupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("개발환경 세팅 도우미")
        self.geometry("700x600")
        self.minsize(500, 400)

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 대화창
        self.chat_box = ctk.CTkTextbox(self, state="disabled", wrap="word", font=("Malgun Gothic", 14))
        self.chat_box.grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 8), sticky="nsew")

        # 입력창
        self.input_field = ctk.CTkEntry(
            self, placeholder_text="메시지를 입력하세요...", font=("Malgun Gothic", 14)
        )
        self.input_field.grid(row=1, column=0, padx=(16, 8), pady=(0, 16), sticky="ew")
        self.input_field.bind("<Return>", lambda e: self._on_send())

        # 전송 버튼
        self.send_button = ctk.CTkButton(
            self, text="전송", width=80, font=("Malgun Gothic", 14), command=self._on_send
        )
        self.send_button.grid(row=1, column=1, padx=(0, 16), pady=(0, 16))

        self.grid_rowconfigure(1, minsize=50)

    def _append_message(self, sender: str, message: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{sender}\n{message}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _on_send(self):
        text = self.input_field.get().strip()
        if not text:
            return

        self._append_message("나:", text)
        self.input_field.delete(0, "end")

        # 고정 응답 (추후 AI 연동 예정)
        self._append_message("AI:", "반갑습니다. 당신의 개발환경 세팅을 도와드릴게요.")


if __name__ == "__main__":
    app = DevSetupApp()
    app.mainloop()
