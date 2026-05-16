import os
import time
import random
import subprocess
import pyperclip
import win32clipboard
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class FacebookScraper:
    def __init__(self, matrix, log_callback, pause_event, stop_event, initial_url, root):
        self.queue_count = 0
        self.matrix = matrix 
        self.log = log_callback
        self.pause_event = pause_event
        self.stop_event = stop_event
        self.initial_url = initial_url
        self.driver = None
        self.odoo_tab = None
        self.root = root
        

    def close_all_edge_instances(self):
        try:
            self.log("Hệ thống: Đang đóng Edge và thực hiện dọn dẹp tab...")
            
            # 1. Force kill processes to release file locks
            subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "msedgedriver.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)

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

    def initialize_driver(self):
        self.close_all_edge_instances()
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--remote-allow-origins=*")
        options.add_argument("--disable-restore-session-state")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument("--log-level=3")
        options.add_experimental_option("detach", True)
        
        # Using the Default Edge Profile
        profile_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Default")
        
        try:
            self.driver = webdriver.Edge(options=options)
            return True
        except Exception as e:
            self.log(f"Nghiêm trọng: Lỗi khởi tạo trình duyệt -> {str(e)}")
            return False

    def check_odoo_connection(self):
        try:
            lost_conn_xpath = "//span[contains(@class, 'o_notification_content') and contains(text(), 'Connection lost')]"
            notifications = self.driver.find_elements(By.XPATH, lost_conn_xpath)
            if notifications:
                self.log("Odoo: Phát hiện mất kết nối. Đang tải lại...")
                self.driver.refresh()
                time.sleep(10)
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
        time.sleep(10)

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
            time.sleep(1)
            
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
            time.sleep(5)
            return True
            
        except Exception as e:
            self.log(f"Nghiêm trọng: Bị kẹt tại bước Xác minh -> {str(e)}")
            # Take a screenshot if you have the capability to check why it's stuck
            return False

    def like_recent_post(self):
        """Scrolls the post into view and clicks the Like button if not already liked."""
        try:
            self.log("Facebook: Đang tìm kiếm bài viết để like...")
            
            # 1. STRATEGY: Match EXACT labels to completely filter out "Gỡ Thích" (Already Liked)
            like_xpath = "//div[(@aria-label='Thích' or @aria-label='Like') and @role='button']"
            like_buttons = self.driver.find_elements(By.XPATH, like_xpath)
            
            if like_buttons:
                target_button = like_buttons[0]
                
                # 2. Use JS to scroll the specific button into the center of the screen
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                    target_button
                )
                
                # 3. Brief pause to let the smooth scroll finish
                time.sleep(2)

                # 4. Execute click action since the selector only finds unliked states
                self.driver.execute_script("arguments[0].click();", target_button)
                self.log("Thành công: Đã cuộn tới bài viết và nhấn like.")
                time.sleep(random.uniform(1.5, 3.0))
                
            else:
                # If no unliked buttons are found, check if a "Gỡ Thích" button is visible instead
                already_liked_xpath = "//div[(@aria-label='Gỡ Thích' or @aria-label='Remove Like') and @role='button']"
                if self.driver.find_elements(By.XPATH, already_liked_xpath):
                    self.log("Trạng thái: Bài viết đã được thích từ trước (Gỡ Thích). Bỏ qua bước này.")
                else:
                    # If absolutely nothing is found, trigger a lazy load scroll
                    self.driver.execute_script("window.scrollBy(0, 500);")
                    self.log("Cảnh báo: Không tìm thấy nút tương tác nào. Đã cuộn xuống thêm.")
                
        except Exception as e:
            self.log(f"Lỗi Like: {str(e)}")

    def close_active_chats(self):
        """Finds and clicks the close 'X' button on any active chat windows."""
        self.log("Đang dọn dẹp các cửa sổ chat đang mở...")
        try:
            # Facebook often groups chat tabs using role='start' or a general container layout.
            # We look for the close button via common accessible aria-labels or SVG structures.
            close_buttons = self.driver.find_elements(
                "xpath", 
                "//div[@aria-label='Đóng đoạn chat' or @aria-label='Close chat' or @aria-label='Close']"
            )
            
            if not close_buttons:
                # Fallback: Find buttons inside the floating chat layout by looking for the small X icon
                close_buttons = self.driver.find_elements(
                    "xpath",
                    "//div[contains(@data-pagelet, 'ChatTab')]//div[@role='button']//i[contains(@class, 'x')]"
                )

            if close_buttons:
                self.log(f"Tìm thấy {len(close_buttons)} cửa sổ chat đang mở. Đang tiến hành đóng.")
                for btn in close_buttons:
                    try:
                        # Force click via JavaScript execution to prevent 'ElementClickInterceptedException'
                        self.driver.execute_script("arguments[0].click();", btn)
                        self.time.sleep(0.5) # Short grace time for animation closure
                    except Exception as e:
                        pass # Ignore if an individual button action fails or vanishes mid-loop
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
            time.sleep(1)
            msg_btn.click()
            self.log("Messenger: Đang mở cửa sổ chat...")
            
            # 2. Wait for the textbox
            input_selector = 'div[role="textbox"][aria-placeholder="Aa"], div[aria-label="Message"], div[aria-label="Tin nhắn"]'
            chat_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, input_selector))
            )
            
            # 3. Bulk Paste Logic
            chat_input.click()
            time.sleep(1)
            
            # Copy the whole message from your file to the clipboard
            pyperclip.copy(text)
            
            # Select all (to clear any residue) and Paste
            chat_input.send_keys(Keys.CONTROL, "a")
            chat_input.send_keys(Keys.BACKSPACE)
            chat_input.send_keys(Keys.CONTROL, "v")
            
            # Brief pause to let the UI register the paste before hitting Enter
            time.sleep(1.5)
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
            self.log("Odoo B2C: Đã dán ảnh. Đang chờ xử lý 6s...")
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
            time.sleep(4) 

            # 6. Re-find the Card to hit 'Qualified'
            # We target the card that has the specific record class
            self.log("Odoo B2C: Đang nhắm mục tiêu lại thẻ Kanban...")
            try:
                # Target the article directly. If there are multiple, we take the first one 
                # (which is usually the one we just edited in Odoo's Kanban)
                kanban_card = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article.o_kanban_record"))
                )

                # Scroll into view to ensure it's loaded in the DOM properly
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", kanban_card)
                time.sleep(1)

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
            time.sleep(2)
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
        
    def handle_odoo_logging(self, file_path):
        """Refocused logging using the specific composer textarea structure."""
        try:
            self.driver.switch_to.window(self.odoo_tab)
            
            # 1. Open Log Note
            log_tab_xpath = "//button[contains(@class, 'o-mail-Chatter-logNote') or contains(., 'Log note')]"
            log_tab = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, log_tab_xpath))
            )
            self.driver.execute_script("arguments[0].click();", log_tab)
            time.sleep(1)

            # 2. Upload file
            chatter_input = self.driver.find_element(By.CSS_SELECTOR, ".o-mail-Composer input.o_input_file")
            chatter_input.send_keys(file_path)
            self.log("Odoo: Đang tải lên ảnh chụp màn hình...")
            
            # # 3. Wait for the 'Attachment Card' to appear
            # # WebDriverWait(self.driver, 15).until(
            # #     EC.presence_of_element_located((By.CSS_SELECTOR, ".o-mail-AttachmentCard"))
            # # )
            # # self.log("Odoo: Attachment processed.")

            # 4. THE FIX: Re-click the specific input box and wait 5s
            # We target the textarea that IS NOT disabled (the real input)
            real_input_selector = "textarea.o-mail-Composer-input:not([disabled])"
            composer_textarea = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, real_input_selector))
            )
            
            self.log("Odoo: Đang định vị lại trình soạn thảo và chờ 5s...")
            composer_textarea.click()
            time.sleep(5) # Your requested wait time for stability

            # 5. Perform Ctrl + Enter
            self.log("Odoo: Đang gửi lệnh Ctrl + Enter...")
            actions = webdriver.ActionChains(self.driver)
            actions.key_down(Keys.CONTROL).send_keys(Keys.ENTER).key_up(Keys.CONTROL).perform()
            
            # 6. Fallback: If it's STILL there, click the physical Log button
            time.sleep(3)
            send_btns = self.driver.find_elements(By.XPATH, "//button[@aria-label='Log']")
            if send_btns and send_btns[0].is_displayed():
                self.log("Odoo: Phím tắt không chạy, đang nhấn nút Log thủ công...")
                self.driver.execute_script("arguments[0].click();", send_btns[0])

            # 7. Move to 'Qualified'
            time.sleep(4) 
            self.log("Odoo: Đang chuyển sang giai đoạn Qualified...")
            qualified_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-value='2' or contains(., 'Qualified')]"))
            )
            self.driver.execute_script("arguments[0].click();", qualified_btn)
            
            time.sleep(3)
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
        
    def run(self):
        if not self.initialize_driver(): return
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