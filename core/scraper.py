import os
import time
import random
import subprocess
import pyperclip
import win32clipboard
import threading
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions

class FacebookScraper:
    def __init__(self, matrix, log_callback, pause_event, stop_event, initial_url, root, browser="Edge", exe_path=None, profile_path=None):
        self.queue_count = 0
        self.matrix = matrix 
        
        # 1. Save original UI callback to a new variable
        self.ui_log = log_callback 
        
        # 2. Redirect self.log to our new dual-logging file method
        self.log = self._write_to_session_log 
        self.log_file_path = None
        
        # 3. Initialize the log file immediately when the scraper object is built
        self.setup_session_logger()

        self.pause_event = pause_event
        self.stop_event = stop_event
        self.initial_url = initial_url
        self.driver = None
        self.odoo_tab = None
        self.root = root
        
        # 4. Custom Browser Configuration
        self.browser = browser
        self.exe_path = exe_path
        self.profile_path = profile_path
        
        self.is_running = False
        
    def init_driver(self):
        """Initializes the correct browser engine based on UI selection."""
        # Import thư viện gốc ngay đầu hàm để tránh lỗi cục bộ (Local Variable Error)
        from selenium import webdriver
        import os
        import time
        import subprocess
        
        # 1. Close and clean up background tasks depending on the chosen platform
        if self.browser != "LibreWolf":
            self.close_all_edge_instances()
        else:
            try:
                self.log("Hệ thống: Đang dọn dẹp các tiến trình LibreWolf cũ...")
                subprocess.run(["taskkill", "/F", "/IM", "librewolf.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
            except Exception:
                pass

        # 2. LAUNCH LIBREWOLF ROUTINE
        if self.browser == "LibreWolf":
            self.log("Đang cấu hình trình duyệt LibreWolf...")
            
            from selenium.webdriver.firefox.service import Service as FirefoxService
            from webdriver_manager.firefox import GeckoDriverManager
            
            # Sử dụng lớp Options tổng quát để cấu hình trực tiếp nhằm vượt qua lỗi nạp module
            from selenium.webdriver.common.options import ArgOptions
            options = ArgOptions()
            options.set_capability("browserName", "firefox")
            
            import sys
            if hasattr(sys, '_MEIPASS'):
                root_dir = os.path.dirname(sys.executable)
            else:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                root_dir = os.path.dirname(current_dir) if os.path.basename(current_dir) == "core" else current_dir

            # --- GIỮ NGUYÊN ĐƯỜNG DẪN MẶC ĐỊNH CỦA BRO ---
            librewolf_path = os.path.join(root_dir, "LibreWolf", "librewolf.exe")
            profile_path = os.path.join(root_dir, "Profiles", "Default")
            
            # --- CODE THÊM MỚI: Ghi đè nếu có đường dẫn tùy chỉnh từ UI ---
            if hasattr(self, 'exe_path') and self.exe_path and self.exe_path != "Default":
                librewolf_path = self.exe_path
                
            if hasattr(self, 'profile_path') and self.profile_path and self.profile_path != "Default":
                profile_path = self.profile_path
            # -------------------------------------------------------------
            
            self.log(f"Hệ thống: Đường dẫn LibreWolf chính xác -> {librewolf_path}")
            self.log(f"Hệ thống: Đường dẫn Hồ sơ chính xác -> {profile_path}")

            # Đóng gói cấu hình nhị phân và profile trực tiếp vào capabilities
            options.set_capability("moz:firefoxOptions", {
                "binary": librewolf_path,
                "args": ["-profile", profile_path],
                "prefs": {
                    "dom.webdriver.enabled": False,
                    "useAutomationExtension": False
                }
            })
            
            try:
                # 1. Tải và định vị chính xác đường dẫn Driver thực thi cục bộ
                driver_path = GeckoDriverManager().install()
                service = FirefoxService(executable_path=driver_path)
                
                # 2. KHỞI ĐỘNG TIẾN TRÌNH GECKODRIVER NGẦM
                service.start()
                
                # 3. KHỞI TẠO ĐỐI TƯỢNG DRIVER THEO CHUẨN SELENIUM MỚI
                from selenium.webdriver.remote.webdriver import WebDriver as BaseWebDriver
                
                # Đưa chuỗi url dịch vụ vào command_executor VÀ truyền service để duy trì vòng đời
                self.driver = BaseWebDriver(
                    command_executor=service.service_url, 
                    options=options
                )
                
                # Gắn chặt đối tượng service vào driver để tự động tắt sạch tiến trình khi gọi driver.quit()
                self.driver._service = service 
                
                self.driver.maximize_window()
                return True
            except Exception as e:
                self.log(f"Nghiêm trọng: Lỗi khởi tạo LibreWolf -> {str(e)}")
                return False
                
        # 3. LAUNCH EDGE ROUTINE
        else:
            self.log("Đang cấu hình trình duyệt Microsoft Edge...")
            from selenium.webdriver.edge.options import Options as EdgeOptions
            
            options = EdgeOptions()
            options.add_argument("--start-maximized")
            options.add_argument("--remote-allow-origins=*")
            options.add_argument("--disable-restore-session-state")
            options.add_argument("--no-first-run")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_argument("--log-level=3")
            options.add_experimental_option("detach", True)
            
            # --- GIỮ NGUYÊN ĐƯỜNG DẪN PROFILE MẶC ĐỊNH CỦA BRO ---
            profile_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
            
            # --- CODE THÊM MỚI: Ghi đè nếu có đường dẫn tùy chỉnh từ UI ---
            if hasattr(self, 'profile_path') and self.profile_path and self.profile_path != "Default":
                profile_path = self.profile_path
                
            if hasattr(self, 'exe_path') and self.exe_path and self.exe_path != "Default":
                options.binary_location = self.exe_path
            # -------------------------------------------------------------

            options.add_argument(f"--user-data-dir={profile_path}")
            options.add_argument("--profile-directory=Default")
            
            try:
                # Đã được sửa lỗi: webdriver hiện tại được gọi an toàn từ đầu hàm
                self.driver = webdriver.Edge(options=options)
                return True
            except Exception as e:
                self.log(f"Nghiêm trọng: Lỗi khởi tạo Microsoft Edge -> {str(e)}")
                return False
            
    def setup_session_logger(self):
        """Creates the session_logs directory and prepares a unique file for this run."""
        try:
            log_dir = "session_logs"
            os.makedirs(log_dir, exist_ok=True)
            
            # Generate filename using a neat date-time stamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.log_file_path = os.path.join(log_dir, f"session_{timestamp}.log")
            
            # Write a clean initialization header line
            with open(self.log_file_path, "w", encoding="utf-8") as f:
                f.write(f"=== BIÊN BẢN PHIÊN CHẠY MÁY - {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
        except Exception as e:
            # Fallback to standard print if file creation fails so app doesn't crash
            print(f"Hệ thống không thể tạo file log: {str(e)}")

    def _write_to_session_log(self, message):
        """Intercepts all log calls, updates UI, and records history to disk with time hooks."""
        # 1. Push message to your original Tkinter dashboard terminal
        if self.ui_log:
            self.ui_log(message)
        
        # 2. Silently append the message with a crisp timestamp into the session log file
        if self.log_file_path:
            try:
                time_hook = time.strftime("[%H:%M:%S]")
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"{time_hook} {message}\n")
            except Exception:
                pass # Ensures file locks or read/write collisions won't halt the automation loop
    def close_all_edge_instances(self):
        try:
            self.log("Hệ thống: Đang đóng Edge và thực hiện dọn dẹp tab...")
            
            # 1. Force kill processes to release file locks
            subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "msedgedriver.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(random.uniform(2, 4))

            # 2. Define the 'Default' profile path
            profile_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default")
            
            # 3. List of session files that force tabs to reopen
            # We leave 'Cookies', 'Network', and 'Local Storage' alone so you stay logged in
            session_files = [
                "Last Session",
                "Last Tabs",
                "Current Session",
                "Current Tabs",
                "Session Storage" # This is a folder, handled below
            ]
            
            for item in session_files:
                target = os.path.join(profile_path, item)
                if os.path.exists(target):
                    try:
                        if os.path.isdir(target):
                            import shutil
                            shutil.rmtree(target)
                        else:
                            os.remove(target)
                    except Exception:
                        pass 

            # 4. CRITICAL: Reset the Preferences file
            # Edge stores a "exit_type" here. If it's "Crashed", it reopens tabs.
            pref_path = os.path.join(profile_path, "Preferences")
            if os.path.exists(pref_path):
                try:
                    with open(pref_path, 'r', encoding='utf-8') as f:
                        import json
                        data = json.load(f)
                    
                    # Force Edge to think it closed normally
                    if "profile" in data and "exit_type" in data["profile"]:
                        data["profile"]["exit_type"] = "Normal"
                    
                    with open(pref_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f)
                except Exception:
                    pass

            self.log("Hệ thống: Các tab đã được dọn dẹp. Phiên đăng nhập được giữ lại.")
        except Exception as e:
            self.log(f"Lỗi dọn dẹp: {str(e)}")

    def check_odoo_connection(self):
        try:
            lost_conn_xpath = "//span[contains(@class, 'o_notification_content') and contains(text(), 'Connection lost')]"
            notifications = self.driver.find_elements(By.XPATH, lost_conn_xpath)
            if notifications:
                self.log("Odoo: Phát hiện mất kết nối. Đang tải lại...")
                self.driver.refresh()
                time.sleep(random.uniform(9, 11))
                self.clear_odoo_filters() # Clear filter after refresh
                return True
            return False
        except Exception:
            return False

    def clear_odoo_filters(self):
        """Surgical check to remove 'My Pipeline' facets if on the demo site."""
        # if "yingbo_demo.sge.vn" in self.driver.current_url:
        #     try:
        #         # Short 3s wait: if it's not there, we don't want to waste time
        #         facet_remove_btn = WebDriverWait(self.driver, 3).until(
        #             EC.element_to_be_clickable((By.CSS_SELECTOR, "button.o_facet_remove.oi-close"))
        #         )
        #         self.driver.execute_script("arguments[0].click();", facet_remove_btn)
        #         self.log("Odoo: Default filters cleared.")
        #         time.sleep(10) # Allow Kanban to reload
        #         return True
        #     except Exception:
        #         # Skip silently if the button is not found
        #         return False
        return False
    
    def verify_initial_access(self):
        self.log(f"Odoo: Đang mở {self.initial_url}")
        self.driver.get(self.initial_url)
        time.sleep(random.uniform(9, 12))

        # 1. Cloudflare Check
        if self.driver.find_elements(By.CSS_SELECTOR, "div#turnstile-wrapper, #cf-challenge"):
            self.log("Nghiêm trọng: Phát hiện Cloudflare.")
            return False
        
        # CAPTURE INITIAL QUEUE COUNT
        try:
            new_col_xpath = "//div[contains(@class, 'o_kanban_group')][.//span[text()='New'] or .//span[text()='Mới']]"
            new_column = self.driver.find_element(By.XPATH, new_col_xpath)
            progress_bar = new_column.find_element(By.CSS_SELECTOR, "div[role='progressbar']")
            val = progress_bar.get_attribute("aria-valuemax")
            self.queue_count = int(val) if val else 0
            self.log(f"Hệ thống: Phát hiện số lượng hàng đợi ban đầu là {self.queue_count}")
        except Exception:
            self.log("Cảnh báo: Không thể phát hiện số lượng hàng đợi ban đầu. Mặc định về 0.")
            self.queue_count = 0

        # 2. Interactivity Check
        self.log("Odoo: Đang kiểm tra khả năng tương tác...")
        try:
            # We use a more generic selector to find ANY Kanban record available
            # article.o_kanban_record is the standard Odoo class
            kanban_card = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "article.o_kanban_record"))
            )
            
            # Scroll to it first to ensure it's "active" in the browser's view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", kanban_card)
            time.sleep(random.uniform(5, 8))
            
            # Force the click via JS (ignores overlays and "is_clickable" restrictions)
            self.log("Odoo: Đang thử click vào thẻ bằng JS...")
            self.driver.execute_script("arguments[0].click();", kanban_card)
            
            # Verify by looking for the 'name' textarea or the field container
            # Added multiple selectors for the detail view to be safe
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[name='name'], textarea.o_input#name_0"))
            )
            
            self.log("Odoo: Khả năng tương tác đã được xác minh.")
            self.driver.get(self.initial_url)
            time.sleep(random.uniform(5, 8))
            return True
            
        except Exception as e:
            self.log(f"Nghiêm trọng: Bị kẹt tại bước Xác minh -> {str(e)}")
            # Take a screenshot if you have the capability to check why it's stuck
            return False

    def like_recent_post(self):
        """Scrolls down to find and click an unliked post if the initial ones are already liked."""
        try:
            self.log("Facebook: Đang tìm kiếm bài viết để like...")
            
            like_xpath = "//div[(@aria-label='Thích' or @aria-label='Like') and @role='button']"
            already_liked_xpath = "//div[(@aria-label='Gỡ Thích' or @aria-label='Remove Like') and @role='button']"
            
            # Set a threshold so it doesn't infinite loop on profiles with no content
            max_scroll_attempts = 3
            
            for attempt in range(max_scroll_attempts):
                # Always re-scan the DOM for unliked buttons after a scroll
                like_buttons = self.driver.find_elements(By.XPATH, like_xpath)
                
                if like_buttons:
                    target_button = like_buttons[0]
                    
                    # 1. Smooth scroll to the discovered unliked post node
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                        target_button
                    )
                    # Use your dynamic random buffer to look human while scrolling
                    time.sleep(random.uniform(2.0, 4.5))

                    # 2. Click the unliked button
                    self.driver.execute_script("arguments[0].click();", target_button)
                    self.log(f"Thành công: Đã tìm thấy bài viết chưa tương tác và nhấn like (Lần thử {attempt + 1}).")
                    time.sleep(random.uniform(1.5, 3.0))
                    return  # Target acquired and processed. Drop out of function cleanly!
                
                # If we get here, no UNLIKED buttons were seen. Let's see if we hit an already liked one.
                has_already_liked = len(self.driver.find_elements(By.XPATH, already_liked_xpath)) > 0
                
                if has_already_liked:
                    self.log(f"Trạng thái: Bài viết hiện tại đã liked. Đang cuộn xuống tìm bài tiếp theo (Vòng {attempt + 1}/{max_scroll_attempts})...")
                else:
                    self.log(f"Cảnh báo: Không phát hiện bài viết. Đang cuộn tải thêm dữ liệu (Vòng {attempt + 1}/{max_scroll_attempts})...")
                
                # 3. Physically scroll down by 750 pixels to trigger Facebook's lazy loading
                self.driver.execute_script("window.scrollBy(0, 750);")
                
                # CRUCIAL: Give Facebook's React engine time to fetch and render new HTML nodes
                time.sleep(random.uniform(3.0, 4.5))
                
            self.log("Kết quả: Đã thử cuộn qua nhiều bài viết nhưng tất cả đều đã được thích từ trước. Bỏ qua.")
                
        except Exception as e:
            self.log(f"Lỗi Like: {str(e)}")

    def close_active_chats(self):
        """Finds and clicks the close 'X' button on any active chat windows."""
        self.log("Đang dọn dẹp các cửa sổ chat đang mở...")
        try:
            # Khởi tạo danh sách chứa các nút tìm được
            close_buttons = []

            # TẦNG 1: Quét Xpath đặc trị dựa trên HTML thực tế của Facebook (Bắt theo data thuộc tính và SVG path)
            # Đường dẫn này quét thẳng vào div role='button' có chứa svg dấu X độ phân giải 16x16
            spec_buttons = self.driver.find_elements(
                "xpath", 
                "//div[@role='button'][@aria-label='Đóng đoạn chat' or @aria-label='Close chat'][@data-prevent_chattab_focus='1']"
            )
            if spec_buttons:
                close_buttons.extend(spec_buttons)

            # TẦNG 2: Fallback bằng cách định vị thẻ path vẽ dấu X đặc trưng của nút đóng FB nếu Class cha thay đổi
            if not close_buttons:
                path_buttons = self.driver.find_elements(
                    "xpath",
                    "//div[@role='button'] [./* [local-name()='svg'] /* [local-name()='path' and contains(@d, 'M13.457 3.957')]]"
                )
                if path_buttons:
                    close_buttons.extend(path_buttons)

            # TẦNG 3: Giữ lại các bộ quét cũ diện rộng của bro để dự phòng khi FB cập nhật layout ở luồng khác
            if not close_buttons:
                old_buttons = self.driver.find_elements(
                    "xpath", 
                    "//div[@aria-label='Đóng đoạn chat' or @aria-label='Close chat' or @aria-label='Close']"
                )
                if old_buttons:
                    close_buttons.extend(old_buttons)

            # TIẾN HÀNH XỬ LÝ CLICK ĐỒNG BỘ CHO ĐA TRÌNH DUYỆT (EDGE & LIBREWOLF)
            if close_buttons:
                # Loại bỏ trùng lặp nếu các tầng quét trùng element
                close_buttons = list(set(close_buttons))
                
                self.log(f"Tìm thấy {len(close_buttons)} cửa sổ chat đang mở. Đang tiến hành đóng.")
                for btn in close_buttons:
                    try:
                        # KHÔNG DÙNG btn.is_displayed() để tránh LibreWolf chặn nhầm các thẻ có style phức tạp.
                        # Ép kích hoạt trực tiếp từ gốc JavaScript để cả Edge và LibreWolf đều click xuyên qua lớp div shadow.
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1) # Delay nhẹ để trình duyệt kịp giải phóng DOM cũ
                    except Exception:
                        pass # Bỏ qua nếu element biến mất trong quá trình vòng lặp quét
            else:
                self.log("Không phát hiện cửa sổ chat nào đang mở.")
                
        except Exception as e:
            self.log(f"Cảnh báo trong quá trình dọn dẹp chat: {str(e)}")

    def send_fb_message(self, text):
        """Targets Messenger with a single bulk paste for speed and reliability."""
        try:
            # 1. Locate and Scroll to Message Button
            msg_btn_xpath = "//div[@aria-label='Message'] | //div[@aria-label='Nhắn tin'] | //div[@role='button'][contains(., 'Message')]"
            msg_btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, msg_btn_xpath))
            )
            
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", msg_btn)
            time.sleep(random.uniform(3, 5))
            msg_btn.click()
            self.log("Messenger: Đang mở cửa sổ chat...")
            
            # 2. Wait for the textbox
            input_selector = 'div[role="textbox"][aria-placeholder="Aa"], div[aria-label="Message"], div[aria-label="Tin nhắn"]'
            chat_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, input_selector))
            )
            
            # 3. Bulk Paste Logic
            chat_input.click()
            time.sleep(random.uniform(2, 4))
            
            # Copy the whole message from your file to the clipboard
            pyperclip.copy(text)
            
            # Select all (to clear any residue) and Paste
            chat_input.send_keys(Keys.CONTROL, "a")
            chat_input.send_keys(Keys.BACKSPACE)
            chat_input.send_keys(Keys.CONTROL, "v")
            
            # Brief pause to let the UI register the paste before hitting Enter
            time.sleep(random.uniform(2, 4))
            chat_input.send_keys(Keys.ENTER)
            
            self.log("Thành công: Đã dán và gửi tin nhắn.")
            time.sleep(3) 
        except Exception as e:
            self.log(f"Lỗi Messenger: {str(e)}")
            try:
                webdriver.ActionChains(self.driver).send_keys(Keys.ENTER).perform()
            except: pass

    def construct_random_message(self):
        """Picks 1 random line from 1 of the 9 files. Returns None on empty content."""
        all_texts = [content for row in self.matrix for content in row]
        
        if not all_texts:
            self.log("Lỗi: Ma trận tin nhắn hoàn toàn trống.")
            return None

        chosen_content = random.choice(all_texts)
        
        if not chosen_content or not chosen_content.strip():
            self.log("Lỗi: Ô/file tin nhắn được chọn bị trống.")
            return None
        
        lines = [l.strip() for l in chosen_content.split('\n') if l.strip()]
        
        if not lines:
            self.log("Lỗi: File được chọn không chứa dòng hợp lệ nào.")
            return None
            
        return chosen_content.strip()
    
    def capture_screenshot(self):
        """Captures the current screen and returns the absolute path."""
        try:
            log_dir = "fb_screenshots"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            file_path = os.path.abspath(f"{log_dir}/FB_{timestamp}.png")
            self.driver.save_screenshot(file_path)
            self.log(f"Hệ thống: Đã chụp màn hình tại {file_path}")
            return file_path
        except Exception as e:
            self.log(f"Lỗi chụp màn hình: {str(e)}")
            return None

    def paste_image_to_clipboard(self, file_path):
        """Converts file to DIB format so Windows treats it as an image, not a file."""
        try:
            image = Image.open(file_path)
            output = BytesIO()
            image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]  # Remove BMP header
            output.close()

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            return True
        except Exception as e:
            self.log(f"Lỗi Clipboard: {str(e)}")
            return False
        
    def handle_b2c_quick_note(self, file_path):
        """Standalone handler for B2C KYC Image paste."""
        try:
            self.driver.switch_to.window(self.odoo_tab)
            
            # 1. Prepare Clipboard
            if not self.paste_image_to_clipboard(file_path):
                return False

            # 2. Target the KYC Image Editor Div
            # Odoo 19 uses 'note-editable' inside the field wrapper
            self.log("Odoo B2C: Đang nhắm tới trường ảnh KYC...")
            kyc_editor = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[name="x_kyc_image"] div.note-editable'))
            )
            
            # 3. Direct Click & Paste (WhatsApp Style)
            kyc_editor.click()
            time.sleep(1)
            kyc_editor.send_keys(Keys.CONTROL, "v")
            
            # CRITICAL: B2C needs time to process the image upload
            self.log("Odoo B2C: Đã dán ảnh. Đang chờ xử lý...")
            time.sleep(6) 

            # 4. Handle the text Note field
            note_editor = self.driver.find_element(By.CSS_SELECTOR, 'div[name="note"] div.note-editable')
            note_editor.click()
            note_editor.send_keys(Keys.CONTROL, "a", Keys.DELETE)
            note_editor.send_keys("Đã gửi tin nhắn")
            
            # 5. Save the Quick Note
            save_btn = self.driver.find_element(By.XPATH, '//button[@name="action_save"]')
            self.driver.execute_script("arguments[0].click();", save_btn)
            self.log("Odoo B2C: Ghi chú nhanh đã lưu. Đang chờ giao diện tải lại...")
            
            # Wait for the Quick Note modal/overlay to actually disappear
            time.sleep(random.uniform(5, 8))

            # 6. Re-find the Card to hit 'Qualified'
            # We target the card that has the specific record class
            self.log("Odoo B2C: Đang nhắm mục tiêu lại thẻ Kanban...")
            try:
                # Target the article directly. If there are multiple, we take the first one 
                # (which is usually the one we just edited in Odoo's Kanban)
                kanban_card = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.o_kanban_record"))
                )

                # # Scroll into view to ensure it's loaded in the DOM properly
                # self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", kanban_card)
                # time.sleep(1)

                # Use JS Click to bypass any invisible 'o_loading' or modal-backdrop divs
                self.driver.execute_script("arguments[0].click();", kanban_card)
                self.log("Odoo B2C: Đã click vào thẻ qua JS.")
            
            except Exception as card_err:
                self.log(f"B2C: Click thẻ thất bại, đang thử tải lại... {str(card_err)}")
                self.driver.refresh()
                time.sleep(5)
                # Try clicking again after refresh
                kanban_card = self.driver.find_element(By.CSS_SELECTOR, "article.o_kanban_record")
                self.driver.execute_script("arguments[0].click();", kanban_card)

            # 7. Move to Qualified
            time.sleep(random.uniform(2, 6))
            qualified_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-value='2' or contains(., 'Qualified')]"))
            )
            self.driver.execute_script("arguments[0].click();", qualified_btn)
            self.log("Odoo B2C: Trạng thái đã cập nhật thành Qualified.")
            
            self.queue_count -= 1
            self.log(f"Hệ thống: Đã xử lý thẻ. Còn lại {self.queue_count} trong bộ nhớ phiên.")
            return True

        except Exception as e:
            self.log(f"B2C Thất bại: {str(e)}")
            return False
    
    def copy_image_to_clipboard(self, file_path):
        """Sử dụng PowerShell hệ thống để đưa ảnh vào Clipboard (Chạy ngầm hoàn toàn không hiện Terminal)"""
        try:
            import subprocess
            powershell_cmd = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('{file_path}'))"
            
            # Sử dụng CREATE_NO_WINDOW để ép buộc ẩn cửa sổ Terminal đen popup lên màn hình
            subprocess.run(
                ["powershell", "-Command", powershell_cmd],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW  # 0x08000000: Ẩn terminal hoàn toàn
            )
            return True
        except Exception as e:
            self.log(f"Hệ thống: Lỗi nạp ảnh vào Clipboard -> {str(e)}")
            return False
        
    def handle_odoo_logging(self, file_path):
        """Refocused logging using exact human-like Ctrl+V paste and dual-submit validation."""
        try:
            self.driver.switch_to.window(self.odoo_tab)
            
            # 1. Kích hoạt mở tab Log Note (Ghi chú)
            log_tab_xpath = (
                "//button[contains(@class, 'o-mail-Chatter-logNote')]"
                "|//button[contains(@class, 'o_Chatter_buttonLogNote')]"
                "|//button[contains(text(), 'Log note')]"
                "|//button[contains(text(), 'Ghi chú')]"
            )
            log_tab = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, log_tab_xpath))
            )
            self.driver.execute_script("arguments[0].click();", log_tab)
            time.sleep(1)

            # 2. Định vị và click vào Textarea để lấy Focus bắt buộc
            real_input_selector = "textarea.o-mail-Composer-input"
            composer_textarea = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, real_input_selector))
            )
            self.driver.execute_script("arguments[0].click(); focus();", composer_textarea)
            time.sleep(1)

            # 3. Thực hiện sao chép và dán ảnh qua tổ hợp phím
            if file_path and os.path.exists(file_path):
                self.log("Odoo: Đang đưa ảnh vào Clipboard chạy ngầm...")
                if self.copy_image_to_clipboard(file_path):
                    self.log("Odoo: Đang thực hiện dán ảnh bằng Ctrl + V...")
                    actions = webdriver.ActionChains(self.driver)
                    actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    time.sleep(4)  # Chờ 4 giây cho Odoo xử lý render ảnh dán vào

            # 4. ƯU TIÊN THỬ LỆNH GỬI BẰNG CTRL + ENTER TRƯỚC
            self.log("Odoo: Thử gửi Log Note bằng phím tắt Ctrl + Enter...")
            actions = webdriver.ActionChains(self.driver)
            actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
            time.sleep(2)  # Đợi 2 giây xem Odoo có đóng khung chat và gửi đi không

            # KIỂM TRA: Nếu khung chat hoặc nút gửi vẫn còn hiển thị -> Gửi bằng phím tắt đã thất bại
            is_form_still_open = False
            try:
                # Kiểm tra nhanh xem textarea còn nằm trên màn hình không
                is_form_still_open = composer_textarea.is_displayed()
            except Exception:
                is_form_still_open = False

            if is_form_still_open:
                # NẾU KHÔNG ĐƯỢC: Đợi thêm 3 giây rồi chuyển sang phương án tìm và bấm nút Log thủ công
                self.log("Odoo: Phím tắt không thành công hoặc Form chưa đóng. Đợi 3 giây rồi tìm ấn nút Log...")
                time.sleep(3)
                
                send_btn_xpath = (
                    "//button[contains(@class, 'o-mail-Composer-send')]" 
                    "|//button[@aria-label='Log']"
                    "|//button[contains(text(), 'Log')]"
                    "|//button[contains(text(), 'Ghi lại')]"
                    "|//div[contains(@class, 'o-mail-Composer-actions')]//button"
                )
                
                send_buttons = self.driver.find_elements(By.XPATH, send_btn_xpath)
                button_clicked = False
                for btn in send_buttons:
                    try:
                        btn_label = btn.get_attribute("aria-label") or ""
                        btn_name = btn.get_attribute("name") or ""
                        
                        if "emoji" in btn_name or "emoji" in btn_label:
                            continue
                            
                        self.driver.execute_script("arguments[0].click();", btn)
                        button_clicked = True
                        self.log("Odoo: Đã ép kích hoạt nút gửi Log Note bằng JS.")
                        break
                    except Exception:
                        continue
            else:
                self.log("Odoo: Gửi thành công bằng phím tắt Ctrl + Enter.")

            # 5. Chuyển trạng thái cơ hội sang giai đoạn Qualified
            time.sleep(4) 
            self.log("Odoo: Đang chuyển sang giai đoạn Qualified...")
            qualified_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-value='2' or contains(., 'Qualified') or contains(., 'Đạt tiêu chuẩn')]"))
            )
            self.driver.execute_script("arguments[0].click();", qualified_btn)
            
            time.sleep(2)
            self.queue_count -= 1
            self.log(f"Hệ thống: Đã xử lý thẻ. Còn lại {self.queue_count} trong bộ nhớ phiên.")
            return True

        except Exception as e:
            self.log(f"Lỗi Logging Odoo: {str(e)}")
            return False

    def check_queue_status(self):
        """Checks if the 'New' column has any cards left using aria-valuemax."""
        try:
            # 1. Target the 'New' column specifically by finding the header text first
            new_column_xpath = "//div[contains(@class, 'o_kanban_group')][.//span[text()='New']]"
            new_column = self.driver.find_element(By.XPATH, new_column_xpath)
            
            # 2. Find the progress bar within that column
            try:
                progress_bar = new_column.find_element(By.CSS_SELECTOR, "div[role='progressbar']")
                count_str = progress_bar.get_attribute("aria-valuemax")
                count = int(count_str) if count_str else 0
                
                if count <= 0:
                    self.log("Hệ thống: Hàng đợi trống (số lượng là 0). Đang dừng ứng dụng.")
                    return False # Stop
                
                self.log(f"Hệ thống: Còn {count} thẻ trong hàng đợi 'Mới'.")
                return True # Continue
                
            except Exception:
                # If progress bar is missing, it usually means 0 records in Odoo
                self.log("Hệ thống: Không tìm thấy thanh tiến trình. Giả định hàng đợi trống.")
                return False
                
        except Exception as e:
            self.log(f"Lỗi kiểm tra hàng đợi: {str(e)}")
            return True # Continue on error to avoid false stops
        
    def start_macro(self):
        if not self.is_running:
            self.is_running = True
            self.macro_thread = threading.Thread(target=self.run, daemon=True)
            self.macro_thread.start()

    def run(self):
        if not self.init_driver(): return
        if not self.verify_initial_access():
            self.driver.quit()
            return

        self.odoo_tab = self.driver.current_window_handle

        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(1)
                continue

            try:
                self.driver.switch_to.window(self.odoo_tab)
                self.check_odoo_connection()
                fb_link = None
                
                # Identify site for logic branching
                is_demo_site = "yingbo_demo.sge.vn" in self.driver.current_url

                # --- STEP 1: GET FB LINK ---
                # B2C site logic: Try Quick Note first
                if not is_demo_site:
                    try:
                        self.log("Odoo (B2C): Đang thử lấy dữ liệu từ Ghi chú nhanh...")
                        quick_note_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.oe_kanban_action[data-tooltip="Quick note"]'))
                        )
                        self.driver.execute_script("arguments[0].click();", quick_note_btn)
                        time.sleep(2)
                        fb_link_el = self.driver.find_elements(By.CSS_SELECTOR, "div[name='x_website'] a")
                        if fb_link_el:
                            fb_link = fb_link_el[0].get_attribute("href")
                    except Exception:
                        pass

                # Demo site logic (or fallback for B2C): Use Form View
                if not fb_link or ("facebook.com" not in fb_link and "fb.com" not in fb_link):
                    self.log("Odoo: Đang điều hướng tới Form View để lấy link...")
                    kanban_card = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "article.o_kanban_record"))
                    )
                    self.driver.execute_script("arguments[0].click();", kanban_card)
                    time.sleep(4)

                    fb_input_xpath = "//input[@id='x_url_fb_profile_0']"
                    fb_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, fb_input_xpath))
                    )
                    fb_link = fb_input.get_attribute("value")

                # --- STEP 2: FACEBOOK ACTIONS ---
                if not fb_link or ("facebook.com" not in fb_link and "fb.com" not in fb_link):
                    self.log(f"Cảnh báo: Không có link FB hợp lệ. Đang bỏ qua.")
                    self.driver.get(self.initial_url)
                    time.sleep(5)
                    self.clear_odoo_filters() # Kept as requested
                    continue

                self.driver.execute_script(f"window.open('{fb_link}', '_blank');")
                time.sleep(2)
                fb_tab = self.driver.window_handles[-1]
                self.driver.switch_to.window(fb_tab)
                
                self.log(f"Facebook: Đang truy cập {fb_link}")
                time.sleep(5) 

                self.close_active_chats() 
                time.sleep(1)

                self.like_recent_post()
                
                msg = self.construct_random_message()
                if msg:
                    self.send_fb_message(msg)
                    time.sleep(2)

                screenshot_path = self.capture_screenshot() 
                time.sleep(3)

                self.driver.close()
                self.driver.switch_to.window(self.odoo_tab)
                
                # --- STEP 3: ODOO LOGGING (FLIPPED LOGIC) ---
                if screenshot_path:
                    if is_demo_site:
                        # Demo site = handle_odoo_logging
                        self.log("Odoo: Trang demo -> Sử dụng Log Note chuẩn.")
                        self.handle_odoo_logging(screenshot_path)
                    else:
                        # B2C site = handle_b2c_quick_note
                        self.log("Odoo: Trang B2C -> Sử dụng dán Ghi chú nhanh.")
                        self.handle_b2c_quick_note(screenshot_path)

                # --- STEP 4: RESET ---
                self.log("Odoo: Đang quay lại Pipeline...")
                self.driver.get(self.initial_url)
                time.sleep(5)
                self.clear_odoo_filters() # Kept as requested

                # --- NEW: MANUAL COUNT CHECK ---
                if self.queue_count <= 0:
                    self.log("Hệ thống: Bộ đếm thủ công đạt mức 0. Tất cả thẻ đã xử lý xong.")
                    self.stop_event.set()
                    continue

            except Exception as e:
                self.log(f"Lỗi chu kỳ: {str(e)}")
                try:
                    self.driver.switch_to.window(self.odoo_tab)
                    self.driver.get(self.initial_url)
                    self.clear_odoo_filters()
                except: pass
                time.sleep(5)

        # self.driver.quit()