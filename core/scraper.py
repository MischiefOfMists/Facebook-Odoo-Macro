import os
import time
import random
import subprocess
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class FacebookScraper:
    def __init__(self, matrix, log_callback, pause_event, stop_event, initial_url):
        self.matrix = matrix 
        self.log = log_callback
        self.pause_event = pause_event
        self.stop_event = stop_event
        self.initial_url = initial_url
        self.driver = None
        self.odoo_tab = None

    def close_all_edge_instances(self):
        try:
            self.log("System: Closing all Edge instances to prevent conflicts...")
            subprocess.run(["taskkill", "/F", "/IM", "msedge.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["taskkill", "/F", "/IM", "msedgedriver.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
        except Exception:
            pass

    def initialize_driver(self):
        self.close_all_edge_instances()
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--remote-allow-origins=*")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument("--log-level=3")
        options.add_experimental_option("detach", True)
        
        profile_path = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Default")
        
        try:
            self.driver = webdriver.Edge(options=options)
            return True
        except Exception as e:
            self.log(f"Critical: Browser Init Error -> {str(e)}")
            return False

    def check_odoo_connection(self):
        """Checks for the 'Connection lost' notification and refreshes if found."""
        try:
            lost_conn_xpath = "//span[contains(@class, 'o_notification_content') and contains(text(), 'Connection lost')]"
            notifications = self.driver.find_elements(By.XPATH, lost_conn_xpath)
            if notifications:
                self.log("Odoo: Connection lost detected. Refreshing...")
                self.driver.refresh()
                time.sleep(10)
                return True
            return False
        except Exception:
            return False

    def verify_initial_access(self):
        """Verify Cloudflare and Odoo Interactivity. Returns True if OK."""
        self.log(f"Odoo: Opening {self.initial_url}")
        self.driver.get(self.initial_url)
        time.sleep(10)

        # 1. Cloudflare Detection
        is_cf = (
            "Just a moment" in self.driver.title or 
            "Cloudflare" in self.driver.title or
            "challenges.cloudflare.com" in self.driver.current_url
        )
        if is_cf or self.driver.find_elements(By.CSS_SELECTOR, "div#turnstile-wrapper, #cf-challenge"):
            self.log("Critical: Cloudflare Turnstile detected. Manual intervention required.")
            return False

        # 2. Interactivity Check (Quick Note Test)
        self.log("Odoo: Testing interactivity (Quick Note check)...")
        try:
            quick_note_btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.oe_kanban_action[data-tooltip="Quick note"]'))
            )
            self.driver.execute_script("arguments[0].click();", quick_note_btn)
            
            # Verify panel opened (checking for the Website field container)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[name='x_website']"))
            )
            self.log("Odoo: Connection and interactivity verified.")
            
            # Reset to main view
            self.driver.get(self.initial_url)
            time.sleep(5)
            return True
        except Exception:
            self.log("Critical: Odoo interactive check failed. Stopping process.")
            return False

    def run(self):
        if not self.initialize_driver(): return
        
        # Initial Verification phase
        if not self.verify_initial_access():
            self.log("System: Stopping process due to connection issues.")
            self.driver.quit()
            return

        self.odoo_tab = self.driver.current_window_handle

        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(1)
                continue

            try:
                # --- STEP 1: GRAB LINK FROM ODOO ---
                self.driver.switch_to.window(self.odoo_tab)
                self.check_odoo_connection()
                
                self.log("Odoo: Locating first Kanban card...")
                quick_note_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.oe_kanban_action[data-tooltip="Quick note"]'))
                )
                self.driver.execute_script("arguments[0].click();", quick_note_btn)
                time.sleep(3)

                # Find the link inside the Website (B2B) widget
                fb_link_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[name='x_website'] a"))
                )
                fb_link = fb_link_element.get_attribute("href")
                
                if not fb_link or ("facebook.com" not in fb_link and "fb.com" not in fb_link):
                    self.log(f"Warning: Invalid link '{fb_link}'. Resetting...")
                    self.driver.get(self.initial_url)
                    time.sleep(5)
                    continue

                self.log(f"Odoo: Target found -> {fb_link}")

                # --- STEP 2: OPEN NEW TAB WITH DIRECT LINK ---
                self.driver.execute_script(f"window.open('{fb_link}', '_blank');")
                time.sleep(2)
                fb_tab = self.driver.window_handles[-1]
                self.driver.switch_to.window(fb_tab)
                
                self.log("Facebook: Navigating to profile...")
                time.sleep(5) # Wait for profile to load

                # --- STEP 3: MESSAGE LOGIC ---
                # Inside your run(self) loop:
                msg = self.construct_random_message()

                if msg:
                    self.log(f"Action: Sending message...")
                    self.send_fb_message(msg)
                else:
                    self.log("Action: Skipping message send due to empty content error.")
                    # You might want to 'continue' the loop here to try the next one

                # --- STEP 4: CLEANUP ---
                self.driver.close() # Close the Facebook tab
                self.driver.switch_to.window(self.odoo_tab)
                self.driver.get(self.initial_url) # Reset Odoo view
                time.sleep(5)

            except Exception as e:
                self.log(f"Cycle Error: {str(e)}")
                self.driver.switch_to.window(self.odoo_tab)
                self.driver.get(self.initial_url)
                time.sleep(5)

        self.driver.quit()

    def send_fb_message(self, text):
        """Targets the specific Messenger chatbox and avoids post comments."""
        try:
            # 1. Click the 'Message' button to ensure the chat window is active
            msg_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@aria-label='Message'] | //div[@aria-label='Nhắn tin']"))
            )
            msg_btn.click()
            self.log("Messenger: Chat window activated.")
            time.sleep(3)

            # 2. Locate the Messenger-specific textbox using the 'Aa' placeholder
            # This distinguishes it from the 'Viết bình luận...' comment box
            chat_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="textbox"][aria-placeholder="Aa"]'))
            )
            
            # 3. Focus and Send
            chat_input.click()
            time.sleep(1)
            
            # Type and Enter
            chat_input.send_keys(text)
            time.sleep(1)
            chat_input.send_keys(Keys.ENTER)
            
            self.log(f"Success: Message sent to Messenger.")
            time.sleep(2) 
            
        except Exception as e:
            self.log(f"Messenger Error: Could not isolate chatbox. -> {str(e)}")

    def construct_random_message(self):
        """
        Picks 1 random text from the 9 files. 
        Returns an error/log if a file or the selected text is empty.
        """
        # 1. Flatten the 3x3 matrix into a single list of 9 items
        all_texts = [content for row in self.matrix for content in row]
        
        if not all_texts:
            self.log("Error: The message matrix is completely empty.")
            return None

        # 2. Pick one random file content
        chosen_content = random.choice(all_texts)
        
        # Check if the chosen file content is just whitespace or empty
        if not chosen_content or not chosen_content.strip():
            self.log("Error: The selected message file is empty.")
            return None
        
        # 3. Pick one random non-empty line from that specific file
        lines = [l.strip() for l in chosen_content.split('\n') if l.strip()]
        
        if not lines:
            self.log("Error: The selected file contains no valid lines of text.")
            return None
            
        return random.choice(lines)