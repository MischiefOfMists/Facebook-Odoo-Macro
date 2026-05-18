import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import os
import time  # Imported for session tracking metrics
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

# =========================================================
# ỨNG DỤNG CHÍNH
# =========================================================

class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FB Messenger Macro")
        self.root.geometry("1450x720")
        self.root.minsize(1450, 720)
        self.root.configure(bg=BG)

        self.scraper_thread = None
        self.current_scraper = None  
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        
        self.preview_labels = {} 
        self.path_entry = None
        self.profile_entry = None

        # Track session timestamps and pauses
        self.start_time = None
        self.pause_start_time = None
        self.total_paused_duration = 0

        self.setup_style()
        self.setup_ui()

        self.root.after(500, self.show_custom_tutorial)

    def show_custom_tutorial(self):
        overlay = tk.Toplevel(self.root)
        overlay.title("Hướng dẫn sử dụng")
        overlay.geometry("650x350")
        overlay.configure(bg=CARD)
        overlay.resizable(False, False)
        overlay.transient(self.root) 
        overlay.grab_set() 

        # Center pop-up
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 325  
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 175
        overlay.geometry(f"+{x}+{y}")

        tk.Label(
            overlay, text="LƯU Ý TRƯỚC KHI CHẠY", 
            bg=CARD, fg=ACCENT, font=("Segoe UI Semibold", 16)
        ).pack(pady=(20, 10))

        msg = (
            "Script sử dụng Profile Trình duyệt được cấu hình. Trước khi bắt đầu script, hãy:\n\n"
            "• Đăng nhập Odoo & vượt Cloudflare thủ công trước trên trình duyệt để đảm bảo độ mượt.\n"
            "• Đăng nhập đúng tài khoản Facebook trước trên trình duyệt đó.\n"
            "• Đảm bảo đường truyền mạng ổn định, tốc độ cao.\n\n"
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

    def update_live_timer(self):
        if self.start_time is None:
            return

        if self.pause_event.is_set():
            self.root.after(1000, self.update_live_timer)
            return

        elapsed_seconds = int(time.time() - self.start_time - self.total_paused_duration)
        if elapsed_seconds < 0:
            elapsed_seconds = 0

        hours = elapsed_seconds // 3600
        minutes = (elapsed_seconds % 3600) // 60
        seconds = elapsed_seconds % 60
        
        clock_string = f" ({hours:02d}:{minutes:02d}:{seconds:02d})"
        self.timer_label.config(text=clock_string)
        self.root.after(1000, self.update_live_timer)

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

    def setup_placeholder(self, entry, placeholder_text, border_frame=None):
        """Xử lý placeholder biến mất khi gõ và xuất hiện lại khi rỗng."""
        def on_focus_in(event):
            if entry.get() == placeholder_text:
                entry.delete(0, tk.END)
                entry.config(fg=TEXT)
            if border_frame:
                border_frame.config(highlightbackground=ACCENT)

        def on_focus_out(event):
            if not entry.get():
                entry.insert(0, placeholder_text)
                entry.config(fg=SUBTEXT)
            if border_frame:
                border_frame.config(highlightbackground="#32384d")

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def handle_browser_layout_change(self, event=None):
        """Cập nhật các ô nhập tùy biến dựa theo trình duyệt được chọn."""
        for widget in self.browser_dynamic_frame.winfo_children():
            widget.destroy()

        browser = self.browser_var.get()

        if browser == "Edge":
            # Ô nhập đường dẫn bị khóa (Disabled)
            tk.Label(self.browser_dynamic_frame, text="Đường dẫn cài đặt", bg=CARD, fg=SUBTEXT).pack(anchor="w", pady=(0, 4))
            
            border_frame = tk.Frame(
                self.browser_dynamic_frame,
                bg=INPUT,
                highlightthickness=1,
                highlightbackground="#2d3345"
            )
            border_frame.pack(fill="x", pady=(0, 14))

            self.path_entry = tk.Entry(
                border_frame,
                bg=INPUT,
                fg="#4a526d",
                disabledbackground=INPUT,
                disabledforeground="#4a526d",
                relief="flat",
                font=("Segoe UI", 10),
                borderwidth=0,
                highlightthickness=0
            )
            self.path_entry.insert(0, "Default")
            self.path_entry.config(state="disabled")
            self.path_entry.pack(fill="x", padx=10, pady=7)
            self.profile_entry = None

        elif browser == "LibreWolf":
            # Ô nhập đường dẫn mở khóa
            tk.Label(self.browser_dynamic_frame, text="Đường dẫn cài đặt", bg=CARD, fg=SUBTEXT).pack(anchor="w", pady=(0, 4))
            
            border_path = tk.Frame(
                self.browser_dynamic_frame,
                bg=INPUT,
                highlightthickness=1,
                highlightbackground="#32384d"
            )
            border_path.pack(fill="x", pady=(0, 12))

            self.path_entry = tk.Entry(
                border_path,
                bg=INPUT,
                fg=SUBTEXT,
                insertbackground=TEXT,
                relief="flat",
                font=("Segoe UI", 10),
                borderwidth=0,
                highlightthickness=0
            )
            self.path_entry.insert(0, "Default")
            self.path_entry.pack(fill="x", padx=10, pady=7)
            self.setup_placeholder(self.path_entry, "Default", border_path)

            # Trường Profile Path cho LibreWolf
            tk.Label(self.browser_dynamic_frame, text="Đường dẫn Profile", bg=CARD, fg=SUBTEXT).pack(anchor="w", pady=(0, 4))
            
            border_profile = tk.Frame(
                self.browser_dynamic_frame,
                bg=INPUT,
                highlightthickness=1,
                highlightbackground="#32384d"
            )
            border_profile.pack(fill="x", pady=(0, 14))

            self.profile_entry = tk.Entry(
                border_profile,
                bg=INPUT,
                fg=SUBTEXT,
                insertbackground=TEXT,
                relief="flat",
                font=("Segoe UI", 10),
                borderwidth=0,
                highlightthickness=0
            )
            self.profile_entry.insert(0, "Default")
            self.profile_entry.pack(fill="x", padx=10, pady=7)
            self.setup_placeholder(self.profile_entry, "Default", border_profile)

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

        # MAIN LAYOUT
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=25, pady=(5, 25))
        main.grid_columnconfigure(0, weight=0, minsize=340)  
        main.grid_columnconfigure(1, weight=0, minsize=340)
        main.grid_columnconfigure(2, weight=1)
        main.grid_rowconfigure(0, weight=1)  

        # LEFT COLUMN (LOGS)
        left = tk.Frame(main, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.create_section_title(left, "Log")
        log_card = tk.Frame(left, bg=CARD, highlightthickness=1, highlightbackground="#2a3042", width=340)
        log_card.pack(fill="both", expand=True)  
        log_card.pack_propagate(False) 

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

        self.log_widget.config(state=tk.NORMAL)
        self.log_widget.insert(tk.END, "➜ Trực quan hóa hoạt động\n")
        self.log_widget.config(state=tk.DISABLED)  

        # CENTER COLUMN (SETUP & TIMED TRACKING)
        center = tk.Frame(main, bg=BG)
        center.grid(row=0, column=1, sticky="nsew", padx=10)
        
        title_frame = tk.Frame(center, bg=BG)
        title_frame.pack(anchor="w", fill="x", pady=(0, 12))
        
        tk.Label(
            title_frame,
            text="Cấu hình",
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 18)
        ).pack(side="left")
        
        self.timer_label = tk.Label(
            title_frame,
            text=" (00:00:00)",
            bg=BG,
            fg="#6c63ff",  
            font=("Segoe UI Semibold", 14)
        )
        self.timer_label.pack(side="left", padx=4, pady=(4, 0))
        
        setup_card = self.create_card(center)
        setup_card.pack(fill="x")
        content = tk.Frame(setup_card, bg=CARD)
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # KHU VỰC TRÌNH DUYỆT CẤU HÌNH
        tk.Label(content, text="Trình duyệt", bg=CARD, fg=SUBTEXT).pack(anchor="w")
        self.browser_var = tk.StringVar(value="Edge")
        self.browser_cb = ttk.Combobox(
            content,
            textvariable=self.browser_var,
            values=["Edge", "LibreWolf"],
            state="readonly",
            style="Modern.TCombobox"
        )
        self.browser_cb.pack(fill="x", pady=(6, 12))

        # KHU VỰC CHỨA Ô NHẬP ĐỘNG (Dòng này bắt buộc phải tạo trước khi gọi Layout Change)
        self.browser_dynamic_frame = tk.Frame(content, bg=CARD)
        self.browser_dynamic_frame.pack(fill="x")

        # Bind sự kiện thay đổi Combobox trình duyệt
        self.browser_cb.bind("<<ComboboxSelected>>", self.handle_browser_layout_change)

        # KHU VỰC ODOO CẤU HÌNH
        tk.Label(content, text="Trang nguồn (Odoo)", bg=CARD, fg=SUBTEXT).pack(anchor="w")
        self.url_var = tk.StringVar(value="Yingbo Demo")
        self.dropdown = ttk.Combobox(
            content,
            textvariable=self.url_var,
            values=list(ODOO_URLS.keys()),
            state="readonly",
            style="Modern.TCombobox"
        )
        self.dropdown.pack(fill="x", pady=(6, 12))

        # KHU VỰC CHECKBOX ANTI-SPAM MODE
        self.antispam_var = tk.BooleanVar(value=False)
        self.chk_antispam = tk.Checkbutton(
            content,
            text="Anti-Spam Mode (Delay gửi 30-60s)",
            variable=self.antispam_var,
            bg=CARD,
            fg=TEXT,
            selectcolor=CARD_2,      
            activebackground=CARD,
            activeforeground=TEXT,
            font=("Segoe UI", 10),
            anchor="w",
            padx=2,
            pady=8
        )
        self.chk_antispam.pack(fill="x", pady=(0, 15))

        # KHU VỰC BUTTONS ĐIỀU KHIỂN
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
            grid_container.grid_rowconfigure(i, weight=1, uniform="row") 
            
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

                cell = tk.Frame(grid_container, bg=CARD_2, highlightthickness=1, highlightbackground="#32384d", cursor="hand2")
                cell.grid(row=r, column=c, sticky="nsew", padx=6, pady=6)
                cell.grid_propagate(False)
                cell.pack_propagate(False) 
                
                cell.bind("<Button-1>", lambda e, p=path, n=file_name: self.open_editor(p, n))

                top = tk.Frame(cell, bg=CARD_2)
                top.pack(fill="x", padx=10, pady=(10, 0))
                tk.Label(top, text=file_name, bg=CARD_2, fg=TEXT, font=("Segoe UI Semibold", 10)).pack(anchor="w")

                preview = tk.Label(
                    cell, text=preview_text, bg=CARD_2, fg=SUBTEXT,
                    justify="left", anchor="nw", font=("Segoe UI", 8)
                )
                preview.bind("<Button-1>", lambda e, p=path, n=file_name: self.open_editor(p, n))
                preview.pack(fill="both", expand=True, padx=10, pady=10)
                
                cell.bind("<Configure>", lambda e, lbl=preview: lbl.config(wraplength=e.width - 20))
                
                self.preview_labels[path] = preview
                file_idx += 1

        # =========================================================
        # GỌI HÀM NÀY Ở DƯỚI CÙNG ĐỂ KHỞI TẠO LAYOUT BAN ĐẦU CHO EDGE
        # TẤT CẢ BIẾN FRAME VÀ WIDGET ĐÃ SẴN SÀNG -> KHÔNG BỊ LỖI NỮA
        # =========================================================
        self.handle_browser_layout_change()

    def refresh_grid(self, path):
        if path in self.preview_labels:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
            except Exception:
                content = ""
            
            if not content:
                content = "(trống)"
                
            preview_text = content[:120] 
            self.preview_labels[path].config(text=preview_text) 

    def open_editor(self, path, name):
        TextEditor(self.root, path, name, on_save_callback=self.refresh_grid)

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
        selected_browser = self.browser_var.get()  
        anti_spam_active = self.antispam_var.get()

        custom_exe_path = None
        custom_profile_path = None
        
        if selected_browser == "LibreWolf":
            if self.path_entry and self.path_entry.get() != "Default":
                custom_exe_path = self.path_entry.get()
            if self.profile_entry and self.profile_entry.get() != "Default":
                custom_profile_path = self.profile_entry.get()
        
        self.start_time = time.time()
        self.pause_start_time = None
        self.total_paused_duration = 0
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.NORMAL)
        self.pause_event.clear()
        self.stop_event.clear()
        
        spam_log_status = "BẬT" if anti_spam_active else "TẮT"
        self.log_message(f"Bắt đầu tiến trình trên {selected_browser} [Anti-Spam: {spam_log_status}]...")

        self.update_live_timer()

        self.current_scraper = FacebookScraper(
            matrix, self.log_message, self.pause_event, self.stop_event, url, self.root, 
            browser=selected_browser, exe_path=custom_exe_path, profile_path=custom_profile_path,
            anti_spam=anti_spam_active
        )
        self.scraper_thread = threading.Thread(target=self.run_scraper, args=(self.current_scraper,), daemon=True)
        self.scraper_thread.start()

    def run_scraper(self, scraper):
        try:
            scraper.run()
        except Exception as e:
            if self.stop_event.is_set():
                pass
            else:
                self.log_message(f"Lỗi tiến trình: {e}")
        finally:
            self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        self.start_time = None
        self.pause_start_time = None
        self.total_paused_duration = 0
        self.current_scraper = None
        self.timer_label.config(text=" (00:00:00)")
        
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED, text="Tạm dừng")
        self.btn_stop.config(state=tk.DISABLED)

    def pause(self):
        if self.pause_event.is_set():
            if self.pause_start_time is not None:
                self.total_paused_duration += (time.time() - self.pause_start_time)
                self.pause_start_time = None

            self.pause_event.clear()
            self.btn_pause.config(text="Tạm dừng")
            self.log_message("Đã tiếp tục.")
        else:
            self.pause_start_time = time.time()
            self.pause_event.set()
            self.btn_pause.config(text="Tiếp tục")
            self.log_message("Đã tạm dừng.")

    def stop(self):
        self.log_message("Đang dừng...")
        self.stop_event.set()
        
        if self.start_time is not None:
            current_pause_delta = 0
            if self.pause_event.is_set() and self.pause_start_time is not None:
                current_pause_delta = time.time() - self.pause_start_time

            final_elapsed = int(time.time() - self.start_time - self.total_paused_duration - current_pause_delta)
            if final_elapsed < 0:
                final_elapsed = 0

            hours = final_elapsed // 3600
            minutes = (final_elapsed % 3600) // 60
            seconds = final_elapsed % 60
            
            self.log_message(f"Thời gian chạy tổng cộng: {hours:02d}:{minutes:02d}:{seconds:02d}")

        if self.current_scraper and hasattr(self.current_scraper, 'driver') and self.current_scraper.driver:
            try:
                self.current_scraper.driver.quit()
                self.log_message("Đã đóng trình duyệt cưỡng bức.")
            except Exception:
                pass

if __name__ == "__main__":
    root = tk.Tk()
    app = MacroApp(root)
    root.mainloop()