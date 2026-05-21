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

import core.facebook_handler as facebook_handler

class FacebookScraper:
    def __init__(self, matrix, log_callback, pause_event, stop_event, initial_url, root, browser="Edge", 
                 exe_path=None, profile_path=None, custom_delay=0, check_group_post=True, **kwargs):
        self.custom_delay = custom_delay
        self.queue_count = 0
        self.matrix = matrix
        
        # --- THÊM DÒNG NÀY ĐỂ LƯU TRẠNG THÁI CHECKBOX ---
        self.check_group_post_var = check_group_post 
        
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

        self.like_recent_post = lambda: facebook_handler.like_recent_post(self)
        self.close_active_chats = lambda: facebook_handler.close_active_chats(self)
        self.send_fb_message = lambda text: facebook_handler.send_fb_message(self, text)
        self.construct_random_message = lambda: facebook_handler.construct_random_message(self)
        

    
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
    
    def check_pause_and_stop(self):
        """Kiểm tra liên tục trạng thái dừng hoặc tạm dừng từ UI"""
        # 1. Nếu có tín hiệu DỪNG HẲN (Stop)
        if self.stop_event.is_set():
            raise Exception("Tiến trình bị dừng bởi người dùng.")

        # 2. Nếu có tín hiệu TẠM DỪNG (Pause)
        if self.pause_event.is_set():
            self.log("Hệ thống: Đang tạm dừng... Đang đợi lệnh Tiếp tục.")
            
            # Vòng lặp vô hạn này sẽ giữ luồng (thread) đứng yên tại chỗ
            while self.pause_event.is_set():
                time.sleep(0.5) # Nghỉ ngắn để không gây treo CPU
                
                # Trong lúc tạm dừng, nếu người dùng đổi ý bấm DỪNG HẲN
                if self.stop_event.is_set():
                    raise Exception("Tiến trình bị dừng bởi người dùng trong khi đang tạm dừng.")
                    
            self.log("Hệ thống: Đã tiếp tục chạy tiến trình!")

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
                group_link = None
                post_link = None
                
                # Identify site for logic branching
                is_demo_site = "yingbo_demo.sge.vn" in self.driver.current_url
                self.check_pause_and_stop()

                # --- STEP 1: GET FB LINK & GROUP/POST LINKS ---
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
                # Ép buộc vào Form View nếu là Demo site HOẶC nếu B2C chưa lấy được link FB
                if not fb_link or ("facebook.com" not in fb_link and "fb.com" not in fb_link):
                    self.log("Odoo: Đang điều hướng tới Form View...")
                    kanban_card = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "article.o_kanban_record"))
                    )
                    self.driver.execute_script("arguments[0].click();", kanban_card)
                    time.sleep(4)

                    # Lấy link cá nhân của Profile FB
                    try:
                        fb_input_xpath = "//input[@id='x_url_fb_profile_0']"
                        fb_input = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, fb_input_xpath))
                        )
                        fb_link = fb_input.get_attribute("value")
                    except Exception:
                        fb_link = None

                    # --- NEW: CÀO THÊM LINK GROUP VÀ LINK POST TỪ FORM VIEW ---
                    try:
                        group_el = self.driver.find_elements(By.CSS_SELECTOR, "div[name='x_group_link'] a")
                        if group_el:
                            group_link = group_el[0].get_attribute("href")
                    except:
                        pass

                    try:
                        post_el = self.driver.find_elements(By.CSS_SELECTOR, "div[name='x_group_post_link'] a")
                        if post_el:
                            post_link = post_el[0].get_attribute("href")
                    except:
                        pass

                self.check_pause_and_stop()

                # --- STEP 1.5: FACEBOOK GROUP & SPECIFIC POST (CONDITIONAL) ---
                # Chỉ chạy đoạn này nếu Checkbox trên giao diện đang được tích chọn
                # --- ĐÃ SỬA: Bỏ .get() vì self.check_group_post_var đã là True/False thuần túy ---
                if self.check_group_post_var:
                    
                    # 1. Xử lý Nhóm trước nếu có link
                    if group_link and ("facebook.com" in group_link or "fb.com" in group_link):
                        self.log(f"Facebook: Đang kiểm tra nhóm {group_link}")
                        self.driver.execute_script(f"window.open('{group_link}', '_blank');")
                        time.sleep(2)
                        group_tab = self.driver.window_handles[-1]
                        self.driver.switch_to.window(group_tab)
                        time.sleep(5)

                        join_xpath = "//div[@role='button'][contains(@aria-label, 'Tham gia') or contains(@aria-label, 'Join') or contains(., 'Tham gia') or contains(., 'Join')]"
                        join_buttons = self.driver.find_elements(By.XPATH, join_xpath)
                        
                        if join_buttons:
                            page_source = self.driver.page_source.lower()
                            is_private_or_restricted = "answer" in page_source or "câu hỏi" in page_source or "questions" in page_source
                            
                            if is_private_or_restricted:
                                self.log("Facebook: Nhóm yêu cầu câu hỏi hoặc phê duyệt phức tạp. Bỏ qua chu kỳ này.")
                                self.driver.close()
                                self.driver.switch_to.window(self.odoo_tab)
                                self.driver.get(self.initial_url)
                                time.sleep(5)
                                self.clear_odoo_filters()
                                continue
                            
                            try:
                                self.driver.execute_script("arguments[0].click();", join_buttons[0])
                                self.log("Facebook: Đã nhấn Tham gia nhóm.")
                                time.sleep(3)
                            except:
                                pass
                        else:
                            self.log("Facebook: Đã ở trong nhóm từ trước hoặc không tìm thấy nút Join công khai.")

                        self.driver.close()
                        self.driver.switch_to.window(self.odoo_tab)
                        self.check_pause_and_stop()

                    # 2. Xử lý Bài viết chỉ định (Like / Re-like) nếu có link
                    if post_link and ("facebook.com" in post_link or "fb.com" in post_link):
                        self.log(f"Facebook: Đang kiểm tra bài viết chỉ định {post_link}")
                        self.driver.execute_script(f"window.open('{post_link}', '_blank');")
                        time.sleep(2)
                        post_tab = self.driver.window_handles[-1]
                        self.driver.switch_to.window(post_tab)
                        time.sleep(5)

                        self.driver.execute_script("window.scrollBy(0, 300);")
                        time.sleep(2)

                        like_xpath = "//div[(@aria-label='Thích' or @aria-label='Like') and @role='button']"
                        already_liked_xpath = "//div[(@aria-label='Gỡ Thích' or @aria-label='Remove Like' or @aria-label='Unlike') and @role='button']"

                        liked_btn = self.driver.find_elements(By.XPATH, already_liked_xpath)
                        if liked_btn:
                            self.log("Facebook: Bài viết đã được Like trước đó. Tiến hành Re-like...")
                            self.driver.execute_script("arguments[0].click();", liked_btn[0])
                            time.sleep(2)
                            
                            unliked_btn = self.driver.find_elements(By.XPATH, like_xpath)
                            if unliked_btn:
                                self.driver.execute_script("arguments[0].click();", unliked_btn[0])
                                self.log("Facebook: Đã Re-like bài viết thành công.")
                        else:
                            unliked_btn = self.driver.find_elements(By.XPATH, like_xpath)
                            if unliked_btn:
                                self.driver.execute_script("arguments[0].click();", unliked_btn[0])
                                self.log("Facebook: Đã Like bài viết thành công.")
                            else:
                                self.log("Cảnh báo: Không định vị được nút Like của bài viết này.")

                        time.sleep(2)
                        self.driver.close()
                        self.driver.switch_to.window(self.odoo_tab)
                        self.check_pause_and_stop()
                else:
                    # Log thông báo nếu người dùng chủ động tắt tính năng này
                    self.log("Hệ thống: Bỏ qua bước kiểm tra Nhóm và Like bài viết theo cấu hình.")
                    
                # --- STEP 2: FACEBOOK ACTIONS (MESSAGE AND STUFF) ---
                if not fb_link or ("facebook.com" not in fb_link and "fb.com" not in fb_link):
                    self.log(f"Cảnh báo: Không có link FB cá nhân hợp lệ để nhắn tin. Bỏ qua.")
                    self.driver.get(self.initial_url)
                    time.sleep(5)
                    self.clear_odoo_filters()
                    continue

                self.driver.execute_script(f"window.open('{fb_link}', '_blank');")
                time.sleep(2)
                fb_tab = self.driver.window_handles[-1]
                self.driver.switch_to.window(fb_tab)
                
                self.log(f"Facebook: Đang truy cập profile để nhắn tin: {fb_link}")
                time.sleep(5) 

                self.close_active_chats() 
                time.sleep(1)

                self.like_recent_post()
                
                # Biến đổi text dựa trên cấu hình ma trận nội dung
                msg = self.construct_random_message()
                if msg:
                    self.send_fb_message(msg)
                    time.sleep(2)

                screenshot_path = self.capture_screenshot() 
                time.sleep(3)

                self.driver.close()
                self.driver.switch_to.window(self.odoo_tab)
                self.check_pause_and_stop()
                
                # --- STEP 3: ODOO LOGGING (FLIPPED LOGIC) ---
                if screenshot_path:
                    if is_demo_site:
                        self.log("Odoo: Trang demo -> Sử dụng Log Note chuẩn.")
                        self.handle_odoo_logging(screenshot_path)
                    else:
                        self.log("Odoo: Trang B2C -> Sử dụng dán Ghi chú nhanh.")
                        self.handle_b2c_quick_note(screenshot_path)

                self.check_pause_and_stop()
                # --- STEP 4: RESET ---
                self.log("Odoo: Đang quay lại Pipeline...")
                self.driver.get(self.initial_url)
                time.sleep(5)
                self.clear_odoo_filters()

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