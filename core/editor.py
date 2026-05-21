import tkinter as tk
from tkinter import messagebox
import os

BG = "#0f1117"
CARD = "#191c25"
ACCENT = "#6c63ff"
DANGER = "#ff5e7e"
TEXT = "#f5f7ff"
SUBTEXT = "#9aa4bf"
BUTTON = "#2d3345"

class TextEditor(tk.Toplevel):
    def __init__(self, parent, file_path, title, on_save_callback=None):
        super().__init__(parent)
        self.file_path = file_path
        self.title(f"Đang chỉnh sửa • {title}")
        self.geometry("580x620")
        self.configure(bg=BG)
        self.on_save_callback = on_save_callback

        self.initial_content = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                self.initial_content = f.read()

        # HEADER
        topbar = tk.Frame(self, bg=BG)
        topbar.pack(fill="x", padx=20, pady=(20, 10))

        tk.Label(
            topbar,
            text=title,
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 18)
        ).pack(side="left")

        # EDITOR AREA
        editor_container = tk.Frame(
            self,
            bg=CARD,
            highlightthickness=1,
            highlightbackground="#2a3042"
        )
        editor_container.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.textbox = tk.Text(
            editor_container,
            bg=CARD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            borderwidth=0,
            font=("Consolas", 11),
            padx=18,
            pady=18,
            undo=True,
            wrap="word"
        )
        self.textbox.pack(fill="both", expand=True)
        self.textbox.insert("1.0", self.initial_content)

        # BUTTONS
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=20, pady=(0, 20))

        self.create_button(btn_row, "Hoàn tác", BUTTON, self.textbox.edit_undo).pack(side="left", padx=(0, 10))
        self.create_button(btn_row, "Lưu lại", ACCENT, self.save_content).pack(side="left")
        self.create_button(btn_row, "Đóng", DANGER, self.on_close).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_button(self, parent, text, color, command):
        return tk.Button(
            parent,
            text=text,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            relief="flat",
            borderwidth=0,
            font=("Segoe UI Semibold", 10),
            padx=18,
            pady=10,
            cursor="hand2",
            command=command
        )

    def save_content(self):
        content = self.textbox.get("1.0", "end-1c")
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.initial_content = content
            
            if self.on_save_callback:
                self.on_save_callback(self.file_path)
                
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể lưu tệp:\n{e}")

    def on_close(self):
        current_content = self.textbox.get("1.0", "end-1c")
        if current_content != self.initial_content:
            response = messagebox.askyesnocancel(
                "Thay đổi chưa lưu",
                "Bạn có muốn lưu các thay đổi trước khi đóng không?"
            )
            if response is True:
                self.save_content()
                self.destroy()
            elif response is False:
                self.destroy()
        else:
            self.destroy()