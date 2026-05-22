import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
from tkinter.scrolledtext import ScrolledText
import threading
import os
import time  # Imported for session tracking metrics
from core.scraper import FacebookScraper
from core.editor import TextEditor
import core.clean_logs as clean_logs


MATRIX_FOLDER = os.path.join("data", "matrix")
os.makedirs(MATRIX_FOLDER, exist_ok=True)

CONFIG_FILE = os.path.join("data", "browser_config.json")

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
# ỨNG DỤNG CHÍNH
# =========================================================

class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FB Messenger Macro")
        self.root.geometry("1450x800")
        self.root.minsize(1450, 800)
        self.root.configure(bg=BG)

        self.scraper_thread = None
        self.current_scraper = None  
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()
        
        self.preview_labels = {} 
        self.path_entry = None
        self.profile_entry = None
        self.profile_status_label = None

        # Track session timestamps and pauses
        self.start_time = None
        self.pause_start_time = None
        self.total_paused_duration = 0

        self.setup_style()
        self.setup_ui()

        self.root.after(500, self.show_custom_tutorial)

    def load_saved_paths(self):
        """Đọc đường dẫn đã lưu từ file JSON, nếu không có hoặc lỗi thì trả về mặc định."""
        default_config = {"exe_path": "Mặc định", "profile_path": "Mặc định"}
        if not os.path.exists(CONFIG_FILE):
            return default_config
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                import json
                return json.load(f)
        except Exception:
            return default_config

    def save_paths(self, exe_path, profile_path):
        """Lưu đường dẫn hiện tại vào file JSON."""
        try:
            import json
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            config_data = {"exe_path": exe_path, "profile_path": profile_path}
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Không thể ghi file cấu hình: {e}")

    def trigger_clean_logs(self):
        """Kích hoạt tiến trình dọn dẹp log từ file clean_logs.py và đẩy log lên giao diện."""
        # Xác định thư mục gốc chứa file main.py
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Gọi hàm xử lý từ module clean_logs, truyền hàm self.log_message để ghi log lên UI công cụ
        # (Nếu hàm ghi log của bạn tên khác, hãy đổi self.log_message thành tên hàm tương ứng của bạn)
        clean_logs.execute_cleaning(base_dir, log_callback=self.log_message)

    def update_profile_label(self):
        """Bóc tách tên folder profile từ đường dẫn cài đặt, kiểm tra mismatch và cập nhật lên UI."""
        if not self.profile_status_label:
            return

        exe_path = self.path_entry.get() if self.path_entry else "Mặc định"
        profile_path = self.profile_entry.get() if self.profile_entry else "Mặc định"
        
        # 1. Xử lý trường hợp một trong hai hoặc cả hai ô là "Mặc định" hoặc trống
        if not exe_path or exe_path == "Mặc định" or not profile_path or profile_path == "Mặc định" or profile_path == "Không cần thiết":
            self.profile_status_label.config(text="Không xác định", fg=SUBTEXT)
            return

        # Chuẩn hóa cả 2 đường dẫn để bóc tách chính xác
        exe_path = os.path.normpath(exe_path).replace('\\', '/')
        profile_path = os.path.normpath(profile_path).replace('\\', '/')
        
        profile_name_exe = None
        profile_name_prof = None

        # --- TRƯỜNG HỢP 1: BẢN PORTABLE (Mới thêm) ---
        if "/LibreWolf/librewolf.exe" in exe_path:
            try:
                profile_name_exe = exe_path.split("/LibreWolf/")[0].split("/")[-1]
            except Exception:
                pass
        # --- TRƯỜNG HỢP 2: BẢN CÀI ĐẶT THƯỜNG (Của ông) ---
        elif "LibreWolf/" in exe_path:
            try:
                profile_name_exe = exe_path.split("/LibreWolf/")[0].split("/")[-1]
            except Exception:
                pass

        # --- TÁCH PROFILE NAME TỪ ĐƯỜNG DẪN PROFILE ---
        if "/Profile/Default" in profile_path:  # Thư mục của bản Portable
            try:
                profile_name_prof = profile_path.split("/Profile/Default")[0].split("/")[-1]
            except Exception:
                pass
        elif "Profiles/Default" in profile_path:  # Thư mục bản cài đặt thường
            try:
                profile_name_prof = profile_path.split("/Profiles/Default")[0].split("/")[-1]
            except Exception:
                pass
        elif "/Profiles/" in profile_path: 
            try:
                profile_name_prof = profile_path.split("/Profiles/")[0].split("/")[-1]
            except Exception:
                pass

        # 2. Kiểm tra xem có lấy được tên profile hợp lệ không
        if not profile_name_exe or not profile_name_prof:
            self.profile_status_label.config(text="Không xác định", fg=SUBTEXT)
            return

        # 3. Kiểm tra Mismatch (Lệch thư mục)
        if profile_name_exe != profile_name_prof:
            self.profile_status_label.config(text=f"{profile_name_exe} (Lệch)", fg=DANGER)
            self.log_message("Đường dẫn profile khác với đường dẫn LibreWolf.exe, vui lòng kiểm tra lại.")
        else:
            # Hai đường dẫn khớp nhau hoàn toàn (Hiển thị nhãn kèm hậu tố nếu là Portable)
            if "/App/LibreWolf/" in exe_path:
                self.profile_status_label.config(text=f"{profile_name_exe} (Portable)", fg="#4da6ff")
            else:
                self.profile_status_label.config(text=profile_name_exe, fg="#4da6ff")

    def browse_path(self, entry_widget, is_folder=True):
        """Mở cửa sổ chọn đường dẫn và tự động điền ô còn lại nếu tìm thấy cấu trúc song song."""
        if is_folder:
            path = filedialog.askdirectory()
        else:
            path = filedialog.askopenfilename(filetypes=[("Executable files", "*.exe")])
        
        if not path:
            return

        # Chuẩn hóa đường dẫn (đổi dấu \ thành / để xử lý đồng nhất)
        path = os.path.normpath(path).replace('\\', '/')

        # --- LOGIC ĐẶC BIỆT: NẾU NGƯỜI DÙNG CHỌN FILE PORTABLE.EXE ---
        if not is_folder and "LibreWolf-Portable.exe" in path:
            # Lấy thư mục gốc (Ví dụ: "C:/Users/Admin/Downloads/SR0328_Jasiminethoai")
            base_dir = os.path.dirname(path)
            
            # Khớp trực tiếp vào thư mục LibreWolf và Profile/Default theo cấu trúc thực tế
            auto_exe_path = os.path.normpath(os.path.join(base_dir, "LibreWolf", "librewolf.exe"))
            auto_profile_path = os.path.normpath(os.path.join(base_dir, "Profiles", "Default"))
            
            # Đổi dấu gạch xuôi để hiển thị đồng nhất và sạch sẽ trên UI
            auto_exe_path = auto_exe_path.replace('\\', '/')
            auto_profile_path = auto_profile_path.replace('\\', '/')
            
            # Điền file lõi vào ô Path Entry
            if self.path_entry:
                self.path_entry.delete(0, tk.END)
                self.path_entry.insert(0, auto_exe_path)
                self.path_entry.config(fg="#ffffff")
                
            # Điền Profile chuẩn vào ô Profile Entry
            if self.profile_entry:
                if str(self.profile_entry['state']) == tk.DISABLED:
                    self.profile_entry.config(state=tk.NORMAL)
                self.profile_entry.delete(0, tk.END)
                self.profile_entry.insert(0, auto_profile_path)
                self.profile_entry.config(fg="#ffffff")
                
            self.log_message("Phát hiện LibreWolf Portable! Tự động chuyển hướng sang file lõi và Profile gốc.")
            
        else:
            # --- LOGIC XỬ LÝ THÔNG THƯỜNG (Giữ nguyên của ông) ---
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)
            entry_widget.config(fg="#ffffff")

            try:
                if not is_folder:  # Người dùng vừa chọn file librewolf.exe thông thường
                    if "LibreWolf/librewolf.exe" in path:
                        base_dir = path.rsplit("LibreWolf/librewolf.exe", 1)[0]
                        auto_profile_path = os.path.join(base_dir, "Profiles/Default").replace('\\', '/')
                        
                        if os.path.exists(auto_profile_path) and self.profile_entry and self.profile_entry.get() == "Mặc định":
                            self.profile_entry.delete(0, tk.END)
                            self.profile_entry.insert(0, auto_profile_path)
                            self.profile_entry.config(fg="#ffffff")
                            self.log_message("Tự động phát hiện đường dẫn Profile tương ứng!")

                else:  # Người dùng vừa chọn thư mục Profiles/Default
                    if "Profiles/Default" in path:
                        base_dir = path.rsplit("Profiles/Default", 1)[0]
                        auto_exe_path = os.path.join(base_dir, "LibreWolf/librewolf.exe").replace('\\', '/')
                        
                        if os.path.exists(auto_exe_path) and self.path_entry and self.path_entry.get() == "Mặc định":
                            self.path_entry.delete(0, tk.END)
                            self.path_entry.insert(0, auto_exe_path)
                            self.path_entry.config(fg="#ffffff")
                            self.log_message("Tự động phát hiện đường dẫn cài đặt LibreWolf tương ứng!")
            except Exception as e:
                print(f"Lỗi tự động điền đường dẫn: {e}")

        # --- LƯU LẠI CẤU HÌNH NGAY SAU KHI THAY ĐỔI ---
        current_exe = self.path_entry.get() if self.path_entry else "Mặc định"
        current_profile = self.profile_entry.get() if self.profile_entry else "Mặc định"
        self.save_paths(current_exe, current_profile)

        self.update_profile_label()
            
    def clear_browser_paths(self):
        """Xóa nhanh hai đường dẫn về 'Mặc định' và cập nhật lại trạng thái hiển thị."""
        if self.path_entry:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, "Mặc định")
            self.path_entry.config(fg=SUBTEXT)
            
        if self.profile_entry:
            self.profile_entry.delete(0, tk.END)
            self.profile_entry.insert(0, "Mặc định")
            self.profile_entry.config(fg=SUBTEXT)
            
        self.save_paths("Mặc định", "Mặc định")
        self.update_profile_label()
        self.log_message("Đã xóa đường dẫn cấu hình trình duyệt.") # <-- Sửa lại log này cho ngắn

    def show_custom_tutorial(self):
        overlay = tk.Toplevel(self.root)
        overlay.title("Lưu ý")
        overlay.geometry("750x350")
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
            "• Đăng nhập Odoo & vượt Cloudflare thủ công trước trên trình duyệt (Edge/LibreWolf) để đảm bảo độ mượt.\n"
            "• Đăng nhập đúng tài khoản Facebook trước trên cùng trình duyệt đó.\n"
            "• Đảm bảo đường truyền mạng ổn định, tốc độ cao.\n"
            "• Macro vẫn còn nhiều lỗi, nếu gặp phải, ghi lại và báo cáo.\n\n"
            "Lưu ý: Đây là phiên bản Demo. Đọc qua Hướng dẫn sử dụng trước khi dùng."
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
            self.profile_status_label = None
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
            self.path_entry.insert(0, "Mặc định")
            self.path_entry.config(state="disabled")
            self.path_entry.pack(fill="x", padx=10, pady=7)
            self.profile_entry = None

        elif browser == "LibreWolf":
            saved_config = self.load_saved_paths()
            saved_exe = saved_config.get("exe_path", "Mặc định")
            saved_profile = saved_config.get("profile_path", "Mặc định")

            # --- DÒNG PROFILE HIỆN TẠI & NÚT XÓA NHANH (CẬP NHẬT) ---
            status_container = tk.Frame(self.browser_dynamic_frame, bg=CARD)
            status_container.pack(fill="x", pady=(0, 8))
            
            # Left side để chứa text hiển thị
            text_frame = tk.Frame(status_container, bg=CARD)
            text_frame.pack(side="left")
            
            tk.Label(text_frame, text="Profile hiện tại: ", bg=CARD, fg=SUBTEXT, font=("Segoe UI", 10)).pack(side="left")
            self.profile_status_label = tk.Label(text_frame, text="Khong xac dinh", bg=CARD, fg=SUBTEXT, font=("Segoe UI Semibold", 10))
            self.profile_status_label.pack(side="left")


            # Nút Xóa nhỏ gọn tinh tế, fit hoàn toàn vào góc phải của box
            btn_clear = tk.Button(
                status_container,
                text="✕",
                bg=CARD,
                fg=SUBTEXT,  # Để mặc định màu xám nhẹ cho tinh tế
                activebackground=CARD,
                activeforeground=DANGER,  # Khi di chuột/bấm vào mới đổi sang màu đỏ cảnh báo
                relief="flat",
                borderwidth=0,
                font=("Segoe UI Semibold", 11),
                padx=5,
                pady=0,
                cursor="hand2",
                command=self.clear_browser_paths
            )
            btn_clear.pack(side="right", padx=(0, 2))

            # Hiệu ứng hover: di chuột vào nút X thì đổi sang màu đỏ, bỏ ra thì về màu xám subtext
            btn_clear.bind("<Enter>", lambda e: btn_clear.config(fg=DANGER))
            btn_clear.bind("<Leave>", lambda e: btn_clear.config(fg=SUBTEXT))

            # --- Đường dẫn cài đặt ---
            tk.Label(self.browser_dynamic_frame, text="Đường dẫn cài đặt", bg=CARD, fg=SUBTEXT).pack(anchor="w", pady=(0, 4))
            border_path = tk.Frame(self.browser_dynamic_frame, bg=INPUT, highlightthickness=1, highlightbackground="#32384d")
            border_path.pack(fill="x", pady=(0, 12))

            container_path = tk.Frame(border_path, bg=INPUT)
            container_path.pack(fill="x", padx=10, pady=5)

            exe_fg = SUBTEXT if saved_exe == "Mặc định" else "#ffffff"
            self.path_entry = tk.Entry(container_path, bg=INPUT, fg=exe_fg, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10), borderwidth=0)
            self.path_entry.pack(side="left", fill="x", expand=True)
            self.path_entry.insert(0, saved_exe)
            
            tk.Button(
                container_path, 
                text="...", 
                bg=BUTTON, 
                fg=TEXT, 
                command=lambda: self.browse_path(self.path_entry, is_folder=False) 
            ).pack(side="right", padx=(5, 0))
            
            self.setup_placeholder(self.path_entry, "Mặc định", border_path)

            # --- Đường dẫn Profile ---
            tk.Label(self.browser_dynamic_frame, text="Đường dẫn Profile", bg=CARD, fg=SUBTEXT).pack(anchor="w", pady=(0, 4))
            border_profile = tk.Frame(self.browser_dynamic_frame, bg=INPUT, highlightthickness=1, highlightbackground="#32384d")
            border_profile.pack(fill="x", pady=(0, 14))

            container_profile = tk.Frame(border_profile, bg=INPUT)
            container_profile.pack(fill="x", padx=10, pady=5)

            profile_fg = SUBTEXT if saved_profile == "Mặc định" else "#ffffff"
            self.profile_entry = tk.Entry(container_profile, bg=INPUT, fg=profile_fg, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10), borderwidth=0)
            self.profile_entry.pack(side="left", fill="x", expand=True)
            self.profile_entry.insert(0, saved_profile)

            tk.Button(
                container_profile, 
                text="...", 
                bg=BUTTON, 
                fg=TEXT, 
                command=lambda: self.browse_path(self.profile_entry, is_folder=True)
            ).pack(side="right", padx=(5, 0))

            self.setup_placeholder(self.profile_entry, "Mặc định", border_profile)
            
            # Khởi chạy cập nhật text ngay khi render xong giao diện dựa vào dữ liệu đã load thành công trước đó
            self.update_profile_label()

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

        # CENTER COLUMN
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

        # TRÌNH DUYỆT
        tk.Label(content, text="Trình duyệt", bg=CARD, fg=SUBTEXT).pack(anchor="w")
        self.browser_var = tk.StringVar(value="LibreWolf")
        self.browser_cb = ttk.Combobox(
            content,
            textvariable=self.browser_var,
            values=["LibreWolf", "Edge"],
            state="readonly",
            style="Modern.TCombobox"
        )
        self.browser_cb.pack(fill="x", pady=(6, 12))

        # Ô NHẬP ĐỘNG
        self.browser_dynamic_frame = tk.Frame(content, bg=CARD)
        self.browser_dynamic_frame.pack(fill="x")
        self.browser_cb.bind("<<ComboboxSelected>>", self.handle_browser_layout_change)

        # ODOO CẤU HÌNH
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

        # DELAY
        tk.Label(content, text="Thời gian trì hoãn gửi (giây)", bg=CARD, fg=SUBTEXT).pack(anchor="w", pady=(0, 4))
        border_delay = tk.Frame(content, bg=INPUT, highlightthickness=1, highlightbackground="#32384d")
        border_delay.pack(fill="x", pady=(0, 15))

        self.delay_var = tk.StringVar(value="0")
        self.delay_entry = tk.Entry(
            border_delay, bg=INPUT, fg=TEXT, textvariable=self.delay_var,
            insertbackground=TEXT, relief="flat", font=("Segoe UI", 10),
            borderwidth=0, highlightthickness=0
        )
        self.delay_entry.pack(fill="x", padx=10, pady=7)

        # --- ĐOẠN ĐƯỢC SỬA CHẮC CHẮN: CUSTOM CHECKBOX ĐẸP CAO CẤP ---
        group_post_check_frame = tk.Frame(content, bg=CARD)
        group_post_check_frame.pack(fill="x", pady=(0, 15), anchor="w")

        # Container đồng bộ vùng click di chuột
        custom_cb_container = tk.Frame(group_post_check_frame, bg=CARD, cursor="hand2")
        custom_cb_container.pack(anchor="w")

        # Khởi tạo biến lưu trạng thái core (Gốc luôn giữ nguyên để backend đọc tốt)
        self.check_group_post_var = tk.BooleanVar(value=True)

        # Hàm chuyển đổi trạng thái khi click
        def toggle_custom_checkbox(event=None):
            new_val = not self.check_group_post_var.get()
            self.check_group_post_var.set(new_val)
            if new_val:
                lbl_checkbox_icon.config(text="✓", bg=ACCENT, fg="white")
            else:
                lbl_checkbox_icon.config(text=" ", bg=INPUT, fg=TEXT)

        # 1. Ô vuông dấu tích giả lập Checkbox (Styled phẳng, bo bằng padding)
        lbl_checkbox_icon = tk.Label(
            custom_cb_container,
            text="✓",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT,
            fg="white",
            width=3,
            height=1,
            relief="flat",
            bd=0
        )
        lbl_checkbox_icon.pack(side="left", padx=(0, 10))

        # 2. Chữ hiển thị nhãn đi kèm
        lbl_checkbox_text = tk.Label(
            custom_cb_container,
            text="Tự động kiểm tra Nhóm & Like bài viết chỉ định",
            bg=CARD,
            fg=TEXT,
            font=("Segoe UI", 10)
        )
        lbl_checkbox_text.pack(side="left")

        # 3. Tạo hiệu ứng đổi màu mượt mà khi di chuột qua (Hover)
        def on_cb_hover(e):
            lbl_checkbox_text.config(fg=ACCENT)  # Chữ sáng lên theo màu chủ đạo app
            if self.check_group_post_var.get():
                lbl_checkbox_icon.config(bg="#5b54de")  # Ô vuông BẬT đổi sắc độ nhẹ
            else:
                lbl_checkbox_icon.config(bg="#3c445c")  # Ô vuông TẮT đổi sắc độ nhẹ

        def on_cb_leave(e):
            lbl_checkbox_text.config(fg=TEXT)    # Trả về màu chữ bình thường
            if self.check_group_post_var.get():
                lbl_checkbox_icon.config(bg=ACCENT)
            else:
                lbl_checkbox_icon.config(bg=INPUT)

        # Ràng buộc sự kiện (Bấm vào chữ hay ô vuông đều ăn)
        custom_cb_container.bind("<Button-1>", toggle_custom_checkbox)
        lbl_checkbox_icon.bind("<Button-1>", toggle_custom_checkbox)
        lbl_checkbox_text.bind("<Button-1>", toggle_custom_checkbox)

        custom_cb_container.bind("<Enter>", on_cb_hover)
        custom_cb_container.bind("<Leave>", on_cb_leave)
        # --- KẾT THÚC ĐOẠN SỬA ---

        # BUTTONS ĐIỀU KHIỂN
        button_row = tk.Frame(content, bg=CARD)
        button_row.pack(fill="x", pady=(0, 10))

        self.btn_start = self.modern_button(button_row, "Bắt đầu", ACCENT, self.start)
        self.btn_start.configure(width=12)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_pause = self.modern_button(button_row, "Tạm dừng", BUTTON, self.pause)
        self.btn_pause.config(state=tk.DISABLED, width=12)
        self.btn_pause.pack(side="left", fill="x", expand=True, padx=6)

        self.btn_stop = self.modern_button(button_row, "Dừng", DANGER, self.stop)
        self.btn_stop.config(state=tk.DISABLED, width=12)
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=(6, 0))

        # HÀNG RIÊNG CHO NÚT DỌN DẸP LOGS
        action_row = tk.Frame(content, bg=CARD)
        action_row.pack(fill="x", pady=(5, 0))

        btn_clean = tk.Button(
            action_row,
            text="Xóa Logs và Hình ảnh cũ",
            bg=CARD,
            fg=SUBTEXT,
            activebackground=CARD,
            activeforeground=DANGER,
            relief="flat",
            borderwidth=1,
            highlightthickness=0,
            font=("Segoe UI Semibold", 10),
            padx=10,
            pady=5,
            cursor="hand2",
            command=self.trigger_clean_logs
        )
        btn_clean.pack(fill="x", expand=True)

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

        # Kích hoạt cập nhật layout động sau khi toàn bộ UI cơ sở đã dựng xong an toàn
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
        # Gọi trực tiếp lớp TextEditor đã import từ file editor.py phụ bên ngoài
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
        
        try:
            custom_delay = int(self.delay_var.get().strip())
            if custom_delay < 0:
                custom_delay = 0
        except ValueError:
            custom_delay = 0

        custom_exe_path = None
        custom_profile_path = None
        
        if self.path_entry and self.path_entry.get() != "Mặc định":
            custom_exe_path = self.path_entry.get()
        if self.profile_entry and self.profile_entry.get() != "Mặc định":
            custom_profile_path = self.profile_entry.get()
        
        self.start_time = time.time()
        self.pause_start_time = None
        self.total_paused_duration = 0
        
        self.btn_start.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.NORMAL)
        self.pause_event.clear()
        self.stop_event.clear()
        
        self.log_message(f"Bắt đầu tiến trình trên {selected_browser} [Delay: {custom_delay}s]...")
        self.update_live_timer()

        self.current_scraper = FacebookScraper(
            matrix, self.log_message, self.pause_event, self.stop_event, url, self.root, 
            browser=selected_browser, exe_path=custom_exe_path, profile_path=custom_profile_path,
            custom_delay=custom_delay
        )
        self.scraper_thread = threading.Thread(target=self.run_scraper, args=(self.current_scraper,), daemon=True)
        self.scraper_thread.start()

    def run_scraper(self, scraper):
        try:
            scraper.run()
        except Exception as e:
            if not self.stop_event.is_set():
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
            self.btn_pause.config(text="Tạm dừng", bg=BUTTON, activebackground=BUTTON)
            self.log_message("Đã tiếp tục tiến trình.")
        else:
            self.pause_start_time = time.time()
            self.pause_event.set()
            self.btn_pause.config(text="Tiếp tục ➜", bg="#ffb03a", activebackground="#ffb03a")
            self.log_message("Đã tạm dừng tiến trình.")

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()  # Giải phóng nếu đang pause
        self.log_message("Đang yêu cầu dừng tiến trình...")

if __name__ == "__main__":
    root = tk.Tk()
    app = MacroApp(root)
    root.mainloop()