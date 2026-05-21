import time
import random
import pyperclip
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver

def like_recent_post(scraper):
    """Scrolls down to find and click an unliked post if the initial ones are already liked."""
    try:
        scraper.log("Facebook: Đang tìm kiếm bài viết để like...")
        
        like_xpath = "//div[(@aria-label='Thích' or @aria-label='Like') and @role='button']"
        already_liked_xpath = "//div[(@aria-label='Gỡ Thích' or @aria-label='Remove Like') and @role='button']"
        
        # Set a threshold so it doesn't infinite loop on profiles with no content
        max_scroll_attempts = 3
        
        for attempt in range(max_scroll_attempts):
            # Always re-scan the DOM for unliked buttons after a scroll
            like_buttons = scraper.driver.find_elements(By.XPATH, like_xpath)
            
            if like_buttons:
                target_button = like_buttons[0]
                
                # 1. Smooth scroll to the discovered unliked post node
                scraper.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                    target_button
                )
                # Use your dynamic random buffer to look human while scrolling
                time.sleep(random.uniform(2.0, 4.5))

                # 2. Click the unliked button
                scraper.driver.execute_script("arguments[0].click();", target_button)
                scraper.log(f"Thành công: Đã tìm thấy bài viết chưa tương tác và nhấn like (Lần thử {attempt + 1}).")
                time.sleep(random.uniform(1.5, 3.0))
                return  # Target acquired and processed. Drop out of function cleanly!
            
            # If we get here, no UNLIKED buttons were seen. Let's see if we hit an already liked one.
            has_already_liked = len(scraper.driver.find_elements(By.XPATH, already_liked_xpath)) > 0
            
            if has_already_liked:
                scraper.log(f"Trạng thái: Bài viết hiện tại đã liked. Đang cuộn xuống tìm bài tiếp theo (Vòng {attempt + 1}/{max_scroll_attempts})...")
            else:
                scraper.log(f"Cảnh báo: Không phát hiện bài viết. Đang cuộn tải thêm dữ liệu (Vòng {attempt + 1}/{max_scroll_attempts})...")
            
            # 3. Physically scroll down by 750 pixels to trigger Facebook's lazy loading
            scraper.driver.execute_script("window.scrollBy(0, 750);")
            
            # CRUCIAL: Give Facebook's React engine time to fetch and render new HTML nodes
            time.sleep(random.uniform(3.0, 4.5))
            
        scraper.log("Kết quả: Đã thử cuộn qua many bài viết nhưng tất cả đều đã được thích từ trước. Bỏ qua.")
            
    except Exception as e:
        scraper.log(f"Lỗi Like: {str(e)}")


def close_active_chats(scraper):
    """Finds and clicks the close 'X' button on any active chat windows."""
    scraper.log("Đang dọn dẹp các cửa sổ chat đang mở...")
    try:
        # Khởi tạo danh sách chứa các nút tìm được
        close_buttons = []

        # TẦNG 1: Quét Xpath đặc trị dựa trên HTML thực tế của Facebook (Bắt theo data thuộc tính và SVG path)
        spec_buttons = scraper.driver.find_elements(
            By.XPATH, 
            "//div[@role='button'][@aria-label='Đóng đoạn chat' or @aria-label='Close chat'][@data-prevent_chattab_focus='1']"
        )
        if spec_buttons:
            close_buttons.extend(spec_buttons)

        # TẦNG 2: Fallback bằng cách định vị thẻ path vẽ dấu X đặc trưng của nút đóng FB nếu Class cha thay đổi
        if not close_buttons:
            path_buttons = scraper.driver.find_elements(
                By.XPATH,
                "//div[@role='button'] [./* [local-name()='svg'] /* [local-name()='path' and contains(@d, 'M13.457 3.957')]]"
            )
            if path_buttons:
                close_buttons.extend(path_buttons)

        # TẦNG 3: Giữ lại các bộ quét cũ diện rộng của bro để dự phòng khi FB cập nhật layout ở luồng khác
        if not close_buttons:
            old_buttons = scraper.driver.find_elements(
                By.XPATH, 
                "//div[@aria-label='Đóng đoạn chat' or @aria-label='Close chat' or @aria-label='Close']"
            )
            if old_buttons:
                close_buttons.extend(old_buttons)

        # TIẾN HÀNH XỬ LÝ CLICK ĐỒNG BỘ CHO ĐA TRÌNH DUYỆT (EDGE & LIBREWOLF)
        if close_buttons:
            # Loại bỏ trùng lặp nếu các tầng quét trùng element
            close_buttons = list(set(close_buttons))
            
            scraper.log(f"Tìm thấy {len(close_buttons)} cửa sổ chat đang mở. Đang tiến hành đóng.")
            for btn in close_buttons:
                try:
                    # Ép kích hoạt trực tiếp từ gốc JavaScript để cả Edge và LibreWolf đều click xuyên qua lớp div shadow.
                    scraper.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1) # Delay nhẹ để trình duyệt kịp giải phóng DOM cũ
                except Exception:
                    pass # Bỏ qua nếu element biến mất trong quá trình vòng lặp quét
        else:
            scraper.log("Không phát hiện cửa sổ chat nào đang mở.")
            
    except Exception as e:
        scraper.log(f"Cảnh báo trong quá trình dọn dẹp chat: {str(e)}")


def send_fb_message(scraper, text):
    """Targets Messenger with a single bulk paste for speed and reliability."""
    try:
        # --- XỬ LÝ CUSTOM DELAY ---
        if hasattr(scraper, 'custom_delay') and scraper.custom_delay >= 0:
            actual_delay = scraper.custom_delay
            if actual_delay < 5:
                scraper.log(f"Hệ thống: Cấu hình delay ({actual_delay}s) dưới mức an toàn. Tự động tăng lên mức tối thiểu 5 giây...")
                actual_delay = 5
            else:
                scraper.log(f"Hệ thống: Tạm dừng {actual_delay} giây theo cấu hình trước khi gửi tin nhắn...")
            
            time.sleep(actual_delay)
        # -----------------------------

        # 1. Locate and Scroll to Message Button
        msg_btn_xpath = "//div[@aria-label='Message'] | //div[@aria-label='Nhắn tin'] | //div[@role='button'][contains(., 'Message')]"
        msg_btn = WebDriverWait(scraper.driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, msg_btn_xpath))
        )
        
        scraper.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", msg_btn)
        time.sleep(random.uniform(3, 5))
        msg_btn.click()
        scraper.log("Messenger: Đang mở cửa sổ chat...")
        
        # 2. Wait for the textbox
        input_selector = 'div[role="textbox"][aria-placeholder="Aa"], div[aria-label="Message"], div[aria-label="Tin nhắn"]'
        chat_input = WebDriverWait(scraper.driver, 15).until(
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
        
        scraper.log("Thành công: Đã dán và gửi tin nhắn.")
        time.sleep(3) 
    except Exception as e:
        scraper.log(f"Lỗi Messenger: {str(e)}")
        try:
            webdriver.ActionChains(scraper.driver).send_keys(Keys.ENTER).perform()
        except: 
            pass


def construct_random_message(scraper):
    """Picks 1 random line from 1 of the 9 files. Returns None on empty content."""
    all_texts = [content for row in scraper.matrix for content in row]
    
    if not all_texts:
        scraper.log("Lỗi: Ma trận tin nhắn hoàn toàn trống.")
        return None

    chosen_content = random.choice(all_texts)
    
    if not chosen_content or not chosen_content.strip():
        scraper.log("Lỗi: Ô/file tin nhắn được chọn bị trống.")
        return None
    
    lines = [l.strip() for l in chosen_content.split('\n') if l.strip()]
    
    if not lines:
        scraper.log("Lỗi: File được chọn không chứa dòng hợp lệ nào.")
        return None
        
    return chosen_content.strip()