import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import threading
import os
import random
from core.scraper import FacebookScraper

# Constants
MATRIX_FOLDER = os.path.join("data", "matrix")
os.makedirs(MATRIX_FOLDER, exist_ok=True)

ODOO_URLS = {
    "B2C": "https://b2c.sge.vn/odoo/crm",
    "None": None
}

class TextEditor(tk.Toplevel):
    def __init__(self, parent, file_path, title):
        super().__init__(parent)
        self.file_path = file_path
        self.title(f"Editing: {title}")
        self.geometry("500x550")
        self.configure(bg="#2b2d31")
        
        # Track initial content to check for unsaved changes
        self.initial_content = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                self.initial_content = f.read()

        # The Text Widget with Undo enabled
        self.textbox = tk.Text(
            self, bg="#1e1f22", fg="#d7dce2", 
            insertbackground="white", relief="flat", 
            font=("Consolas", 11), padx=10, pady=10,
            undo=True  # Enables Ctrl+Z naturally
        )
        self.textbox.pack(fill="both", expand=True, padx=15, pady=15)
        self.textbox.insert("1.0", self.initial_content)

        # Button Container (Bottom Row)
        btn_frame = tk.Frame(self, bg="#2b2d31")
        btn_frame.pack(fill="x", side="bottom", pady=(0, 15), padx=15)

        # Undo Button
        self.undo_btn = tk.Button(
            btn_frame, text="UNDO", bg="#4e5058", fg="white", 
            relief="flat", font=("Segoe UI Bold", 9), width=10,
            command=self.textbox.edit_undo
        )
        self.undo_btn.pack(side="left", padx=5)

        # Save Button
        self.save_btn = tk.Button(
            btn_frame, text="SAVE", bg="#5865f2", fg="white", 
            relief="flat", font=("Segoe UI Bold", 9), width=10,
            command=self.save_content
        )
        self.save_btn.pack(side="left", padx=5)

        # Close Button
        self.close_btn = tk.Button(
            btn_frame, text="CLOSE", bg="#ed4245", fg="white", 
            relief="flat", font=("Segoe UI Bold", 9), width=10,
            command=self.on_close
        )
        self.close_btn.pack(side="right", padx=5)

        # Intercept the 'X' button on the window
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def save_content(self):
        content = self.textbox.get("1.0", "end-1c")
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.initial_content = content # Update initial state after saving
            # Optional: simple flash or log to show it saved
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file: {e}")

    def on_close(self):
        current_content = self.textbox.get("1.0", "end-1c")
        if current_content != self.initial_content:
            response = messagebox.askyesnocancel(
                "Unsaved Changes", 
                "You have unsaved changes. Do you want to save before closing?"
            )
            if response is True: # Yes
                self.save_content()
                self.destroy()
            elif response is False: # No
                self.destroy()
            # If 'cancel', do nothing and stay in editor
        else:
            self.destroy()

class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FB Messenger Macro")
        self.root.geometry("850x780")
        self.root.configure(bg="#1e1f22")

        self.scraper_thread = None
        self.pause_event = threading.Event()
        self.stop_event = threading.Event()

        self.setup_style()
        self.setup_ui()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background="#1e1f22", foreground="white", fieldbackground="#2b2d31", font=("Segoe UI", 10))
        style.configure("Card.TFrame", background="#2b2d31")
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 20), background="#1e1f22", foreground="white")
        style.configure("Sub.TLabel", font=("Segoe UI", 10), background="#1e1f22", foreground="#b5bac1")
        style.configure("Modern.TButton", font=("Segoe UI Semibold", 10), padding=10, background="#5865f2", foreground="white")
        style.map("Modern.TButton", background=[("active", "#6d78ff"), ("disabled", "#3a3c42")])
        style.configure("Matrix.TButton", font=("Segoe UI", 9), padding=5, background="#404249", foreground="white")
        style.map("Matrix.TButton", background=[("active", "#4e5058")])

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1e1f22")
        header.pack(fill="x", padx=25, pady=(20, 10))
        ttk.Label(header, text="FB Messenger Macro", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="3x3 Matrix Controller", style="Sub.TLabel").pack(anchor="w")

        # Main Card
        card = ttk.Frame(self.root, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=20, pady=10)

        # Matrix Section
        matrix_label = tk.Label(card, text="MESSAGE MATRIX (CLICK TO EDIT 0-8.txt)", bg="#2b2d31", fg="#b5bac1", font=("Segoe UI Semibold", 10))
        matrix_label.pack(anchor="w", padx=20, pady=(15, 5))
        
        matrix_frame = tk.Frame(card, bg="#2b2d31")
        matrix_frame.pack(padx=20, pady=10)

        file_idx = 0
        for r in range(3):
            for c in range(3):
                file_name = f"{file_idx}.txt"
                path = os.path.join(MATRIX_FOLDER, file_name)
                if not os.path.exists(path):
                    with open(path, "w") as f: f.write(f"Sample line for {file_name}")
                
                btn = tk.Button(matrix_frame, text=f"Edit {file_name}\n(Row {r+1} Opt {c+1})", 
                                bg="#404249", fg="white", relief="flat", width=22, height=3,
                                command=lambda p=path, n=file_name: self.open_editor(p, n))
                btn.grid(row=r, column=c, padx=5, pady=5)
                file_idx += 1

        # Controls Section
        controls = tk.Frame(card, bg="#2b2d31")
        controls.pack(fill="x", padx=20, pady=20)

        tk.Label(controls, text="Target URL:", bg="#2b2d31", fg="white").pack(side="left", padx=(0, 10))
        self.url_var = tk.StringVar(value="B2C")
        self.dropdown = ttk.Combobox(controls, textvariable=self.url_var, values=list(ODOO_URLS.keys()), state="readonly", width=25)
        self.dropdown.pack(side="left", padx=(0, 20))

        self.btn_start = ttk.Button(controls, text="Start", style="Modern.TButton", command=self.start)
        self.btn_start.pack(side="left", padx=5)
        self.btn_pause = ttk.Button(controls, text="Pause", style="Modern.TButton", command=self.pause, state=tk.DISABLED)
        self.btn_pause.pack(side="left", padx=5)
        self.btn_stop = ttk.Button(controls, text="Stop", style="Modern.TButton", command=self.stop, state=tk.DISABLED)
        self.btn_stop.pack(side="left", padx=5)

        # Logs Section
        console_frame = tk.Frame(card, bg="#2b2d31")
        console_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.log_widget = ScrolledText(console_frame, state=tk.DISABLED, bg="#111214", fg="#d7dce2", relief="flat", font=("Consolas", 10), padx=10, pady=10)
        self.log_widget.pack(fill="both", expand=True)

    def open_editor(self, path, name):
        TextEditor(self.root, path, name)

    def log_message(self, message):
        def append():
            self.log_widget.config(state=tk.NORMAL)
            self.log_widget.insert(tk.END, f"-> {message}\n")
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

        scraper = FacebookScraper(matrix, self.log_message, self.pause_event, self.stop_event, url)
        self.scraper_thread = threading.Thread(target=self.run_scraper, args=(scraper,), daemon=True)
        self.scraper_thread.start()

    def run_scraper(self, scraper):
        scraper.run()
        self.root.after(0, self.reset_buttons)

    def reset_buttons(self):
        self.btn_start.config(state=tk.NORMAL)
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.DISABLED)

    def pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.btn_pause.config(text="Pause")
            self.log_message("Resumed.")
        else:
            self.pause_event.set()
            self.btn_pause.config(text="Resume")
            self.log_message("Paused.")

    def stop(self):
        self.log_message("Stopping...")
        self.stop_event.set()

if __name__ == "__main__":
    root = tk.Tk()
    app = MacroApp(root)
    root.mainloop()