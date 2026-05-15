import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import os
from core.scraper import FacebookScraper

# =========================================================
# HẰNG SỐ
# =========================================================

MATRIX_FOLDER = os.path.join("data", "matrix")
os.makedirs(MATRIX_FOLDER, exist_ok=True)

ODOO_URLS = {
    "B2C": "https://b2c.sge.vn/odoo/crm",
    "Yingbo Demo": "https://yingbo_demo.sge.vn/odoo/crm"
}

# =========================================================
# MÀU SẮC
# =========================================================

BG = "#0f1117"
CARD = "#191c25"
CARD_2 = "#232734"
ACCENT = "#6c63ff"
DANGER = "#ff5e7e"
TEXT = "#f5f7ff"
SUBTEXT = "#9aa4bf"
BUTTON = "#2d3345"
INPUT = "#242938"

# =========================================================
# TRÌNH CHỈNH SỬA VĂN BẢN
# =========================================================

class TextEditor(tk.Toplevel):
    def __init__(self, parent, file_path, title):
        super().__init__(parent)
        self.file_path = file_path
        self.title(f"Đang chỉnh sửa • {title}")
        self.geometry("580x620")
        self.configure(bg=BG)

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

# =========================================================
# ỨNG DỤNG CHÍNH
# =========================================================

class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FB Messenger Macro")
        self.root.geometry("1180x720")
        self.root.minsize(1250, 720)
        self.root.configure(bg=BG)

        self.scraper_thread = None
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()

        self.setup_style()
        self.setup_ui()

        self.root.after(500, self.show_custom_tutorial)

    def show_custom_tutorial(self):
        overlay = tk.Toplevel(self.root)
        overlay.title("Hướng dẫn sử dụng")
        overlay.geometry("650x350")
        overlay.configure(bg=CARD)
        overlay.resizable(False, False)
        overlay.transient(self.root) # Luôn nằm trên cửa sổ chính
        overlay.grab_set() # Khóa tương tác với cửa sổ chính cho đến khi đóng pop-up

        # Center pop-up
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 250
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 175
        overlay.geometry(f"+{x}+{y}")

        tk.Label(
            overlay, text="LƯU Ý TRƯỚC KHI CHẠY", 
            bg=CARD, fg=ACCENT, font=("Segoe UI Semibold", 16)
        ).pack(pady=(20, 10))

        msg = (
            "Script sử dụng Profile Edge hiện tại của bạn. Trước khi bắt đầu script, hãy:\n\n"
            "• Đăng nhập Odoo & vượt Cloudflare thủ công trước trên Edge để đảm bảo độ mượt.\n"
            "• Dăng nhập đúng tài khoản Facebook trước trên Edge.\n"
            "• Đảm bảo đường truyền mạng ổn định, tốc độ cao.\n\n"
            "Lưu ý: Đây là phiên bản Demo."
        )

        tk.Label(
            overlay, text=msg, bg=CARD, fg=TEXT, 
            font=("Segoe UI", 11), justify="left", padx=30
        ).pack(fill="x", pady=10)

        self.modern_button(
            overlay, "Đã hiểu", ACCENT, overlay.destroy
        ).pack(pady=20)

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Modern.TCombobox",
            fieldbackground=INPUT,
            background=INPUT,
            foreground=TEXT,
            bordercolor="#32384d",
            lightcolor="#32384d",
            darkcolor="#32384d",
            arrowcolor=TEXT,
            padding=10,
            font=("Segoe UI", 10)
        )
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", INPUT), ("active", INPUT)],
            background=[("readonly", INPUT), ("active", INPUT)],
            foreground=[("readonly", TEXT), ("active", TEXT)],
            arrowcolor=[("active", TEXT), ("readonly", TEXT)],
            bordercolor=[("focus", ACCENT), ("readonly", "#32384d")]
        )
        self.root.option_add("*TCombobox*Listbox.background", CARD_2)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.root.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

    def create_card(self, parent):
        return tk.Frame(
            parent,
            bg=CARD,
            highlightthickness=1,
            highlightbackground="#2a3042"
        )

    def create_section_title(self, parent, title):
        tk.Label(
            parent,
            text=title,
            bg=parent["bg"],
            fg=TEXT,
            font=("Segoe UI Semibold", 18)
        ).pack(anchor="w", pady=(0, 12))

    def modern_button(self, parent, text, color, command):
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
            padx=16,
            pady=10,
            cursor="hand2",
            command=command
        )

    def setup_ui(self):
        # HEADER
        topbar = tk.Frame(self.root, bg=BG)
        topbar.pack(fill="x", padx=25, pady=(20, 10))

        tk.Label(
            topbar,
            text="FB Messenger Macro",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 24)
        ).pack(anchor="w")

        tk.Label(
            topbar,
            text="Bảng điều khiển Matrix Hiện đại",
            bg=BG,
            fg=SUBTEXT,
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        # MAIN LAYOUT
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=25, pady=(5, 25))
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_columnconfigure(2, weight=1)

        # LEFT COLUMN (LOGS)
        left = tk.Frame(main, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.create_section_title(left, "Nhật ký hoạt động")
        log_card = self.create_card(left)
        log_card.pack(fill="both", expand=True)

        self.log_widget = ScrolledText(
            log_card,
            state=tk.DISABLED,
            bg=CARD,
            fg="#dbe2ff",
            insertbackground="white",
            relief="flat",
            borderwidth=0,
            font=("Consolas", 10),
            padx=15,
            pady=15
        )
        self.log_widget.pack(fill="both", expand=True)

        # CENTER COLUMN (SETUP)
        center = tk.Frame(main, bg=BG)
        center.grid(row=0, column=1, sticky="nsew", padx=10)
        
        self.create_section_title(center, "Thẻ hiện tại")
        current_card = self.create_card(center)
        current_card.pack(fill="x")

        preview_area = tk.Frame(current_card, bg=CARD_2, height=180)
        preview_area.pack(fill="both", expand=True, padx=15, pady=15)
        preview_area.pack_propagate(False)

        tk.Label(
            preview_area,
            text="Chưa triển khai",
            bg=CARD_2,
            fg=SUBTEXT,
            font=("Segoe UI", 14)
        ).place(relx=0.5, rely=0.5, anchor="center")

        tk.Frame(center, bg=BG, height=20).pack()
        self.create_section_title(center, "Cấu hình")

        setup_card = self.create_card(center)
        setup_card.pack(fill="x")
        content = tk.Frame(setup_card, bg=CARD)
        content.pack(fill="both", expand=True, padx=15, pady=15)

        tk.Label(content, text="Trình duyệt", bg=CARD, fg=SUBTEXT).pack(anchor="w")
        self.browser_var = tk.StringVar(value="Edge")
        ttk.Combobox(
            content,
            textvariable=self.browser_var,
            values=["Edge"],
            state="readonly",
            style="Modern.TCombobox"
        ).pack(fill="x", pady=(6, 18))

        tk.Label(content, text="Trang nguồn (Odoo)", bg=CARD, fg=SUBTEXT).pack(anchor="w")
        self.url_var = tk.StringVar(value="Yingbo Demo")
        self.dropdown = ttk.Combobox(
            content,
            textvariable=self.url_var,
            values=list(ODOO_URLS.keys()),
            state="readonly",
            style="Modern.TCombobox"
        )
        self.dropdown.pack(fill="x", pady=(6, 25))

        button_row = tk.Frame(content, bg=CARD)
        button_row.pack(fill="x")

        self.btn_start = self.modern_button(button_row, "Bắt đầu", ACCENT, self.start)
        self.btn_start.configure(width=12)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_pause = self.modern_button(button_row, "Tạm dừng", BUTTON, self.pause)
        self.btn_pause.config(state=tk.DISABLED, width=12)
        self.btn_pause.pack(side="left", fill="x", expand=True, padx=6)

        self.btn_stop = self.modern_button(button_row, "Dừng", DANGER, self.stop)
        self.btn_stop.config(state=tk.DISABLED, width=12)
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # RIGHT COLUMN (MATRIX)
        right = tk.Frame(main, bg=BG)
        right.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        self.create_section_title(right, "Ma trận nội dung")
        matrix_card = self.create_card(right)
        matrix_card.pack(fill="both", expand=True)

        grid_container = tk.Frame(matrix_card, bg=CARD)
        grid_container.pack(fill="both", expand=True, padx=10, pady=10)

        for i in range(3):
            grid_container.grid_columnconfigure(i, weight=1, uniform="col")
            grid_container.grid_rowconfigure(i, minsize=120)
            
        file_idx = 0
        for r in range(3):
            for c in range(3):
                file_name = f"{file_idx}.txt"
                path = os.path.join(MATRIX_FOLDER, file_name)
                if not os.path.exists(path):
                    with open(path, "w", encoding="utf-8") as f: f.write("")

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        preview_text = f.read().strip()
                except: preview_text = ""

                if not preview_text: preview_text = "(trống)"
                preview_text = preview_text[:120]

                cell = tk.Frame(
                    grid_container, bg=CARD_2, highlightthickness=1,
                    highlightbackground="#32384d", cursor="hand2", height=120
                )
                cell.grid(row=r, column=c, sticky="ew", padx=6, pady=6)
                cell.grid_propagate(False)
                cell.bind("<Button-1>", lambda e, p=path, n=file_name: self.open_editor(p, n))

                top = tk.Frame(cell, bg=CARD_2)
                top.pack(fill="x", padx=10, pady=(10, 0))
                tk.Label(top, text=file_name, bg=CARD_2, fg=TEXT, font=("Segoe UI Semibold", 10)).pack(anchor="w")

                preview = tk.Label(
                    cell, text=preview_text, bg=CARD_2, fg=SUBTEXT,
                    justify="left", anchor="nw", wraplength=120, font=("Segoe UI", 8)
                )
                preview.bind("<Button-1>", lambda e, p=path, n=file_name: self.open_editor(p, n))
                preview.pack(fill="both", expand=True, padx=10, pady=10)
                file_idx += 1

    def open_editor(self, path, name):
        TextEditor(self.root, path, name)

    def log_message(self, message):
        def append():
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.insert(tk.END, f"➜ {message}\n")
            self.log_widget.see(tk.END)
            self.log_widget.config(state=tk.DISABLED)
        self.root.after(0, append)

    def get_matrix_data_from_files(self):
        matrix = []
        idx = 0
        for r in range(3):
            row_data = []
            for c in range(3):
                with open(os.path.join(MATRIX_FOLDER, f"{idx}.txt"), "r", encoding="utf-8") as f:
                    row_data.append(f.read())
                idx += 1
            matrix.append(row_data)
        return matrix

    def start(self):
        url = ODOO_URLS.get(self.url_var.get())
        matrix = self.get_matrix_data_from_files()
        self.btn_start.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.NORMAL)
        self.pause_event.clear()
        self.stop_event.clear()
        self.log_message("Bắt đầu tiến trình...")

        scraper = FacebookScraper(matrix, self.log_message, self.pause_event, self.stop_event, url, self.root)
        self.scraper_thread = threading.Thread(target=self.run_scraper, args=(scraper,), daemon=True)
        self.scraper_thread.start()

    def run_scraper(self, scraper):
        scraper.run()
        self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED, text="Tạm dừng")
        self.btn_stop.config(state=tk.DISABLED)

    def pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.btn_pause.config(text="Tạm dừng")
            self.log_message("Đã tiếp tục.")
        else:
            self.pause_event.set()
            self.btn_pause.config(text="Tiếp tục")
            self.log_message("Đã tạm dừng.")

    def stop(self):
        self.log_message("Đang dừng...")
        self.stop_event.set()

if __name__ == "__main__":
    root = tk.Tk()
    app = MacroApp(root)
    root.mainloop()