# auto_submit.py - Auto URL Submitter for GitHub Actions (Chromium-Compatible)
import os
import sys
import logging
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# ============ CONFIGURATION ============
PANEL_URL = "https://personal-fast-index.info/panel20/panel.php"
USERNAME = os.getenv("PANEL_USER", "")
PASSWORD = os.getenv("PANEL_PASS", "")
URLS_FILE = "pdf_urls.txt"
MAX_RETRIES = 3
HEADLESS = True  # Always True for GitHub Actions

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("automation.log"),
        logging.StreamHandler()
    ]
)

class FastURLSubmitter:
    def __init__(self):
        self.driver = None
        self.wait = None

        return []


    def setup_driver(self):
        """Configure Chrome/Chromium for headless CI environment"""
        options = Options()
        
        # Essential flags for GitHub Actions / CI
        options.add_argument('--headless=new')  # New headless mode (Chrome 109+)
        options.add_argument('--no-sandbox')  # Required for Docker/CI
        options.add_argument('--disable-dev-shm-usage')  # Prevent /dev/shm issues
        options.add_argument('--disable-gpu')  # Disable GPU acceleration
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-blink-features=AutomationControlled')  # Anti-detection
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Performance: disable images, CSS, notifications
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # 🔑 CRITICAL: Point to Chromium binary on Ubuntu/GitHub Actions
        # GitHub Actions ubuntu-latest uses 'chromium', not 'google-chrome'
        chromium_paths = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable"
        ]
        for path in chromium_paths:
            if os.path.exists(path):
                options.binary_location = path
                logging.info(f"🎯 Using browser binary: {path}")
                break
        else:
            logging.warning("⚠️ Chromium binary not found in expected paths")
        
        # 🔑 CRITICAL: Use system chromedriver (pre-installed in GitHub Actions)
        # Instead of webdriver_manager which can cause version mismatches
        driver_paths = [
            "/usr/bin/chromedriver",
            "/usr/local/bin/chromedriver",
            "/snap/bin/chromedriver"
        ]
        driver_path = None
        for path in driver_paths:
            if os.path.exists(path):
                driver_path = path
                logging.info(f"🎯 Using chromedriver: {path}")
                break
        
        if driver_path:
            service = Service(executable_path=driver_path)
        else:
            # Fallback: let Selenium find it in PATH
            service = Service()
        
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 12)
        logging.info("✅ WebDriver initialized")

    def login(self):
        try:
            logging.info(f"🔐 Logging into {PANEL_URL}")
            self.driver.get(PANEL_URL)
            
            # Wait for login form
            username_field = self.wait.until(
                EC.presence_of_element_located((By.NAME, "login"))
            )
            password_field = self.driver.find_element(By.NAME, "password")
            
            # Fill credentials
            username_field.send_keys(USERNAME)
            password_field.send_keys(PASSWORD)
            password_field.submit()
            
            # Wait for successful login (look for the links textarea)
            self.wait.until(EC.presence_of_element_located((By.NAME, "links")))
            logging.info("✅ Login successful")
            return True
            
        except Exception as e:
            logging.error(f"❌ Login failed: {e}")
            # Save screenshot for debugging (optional)
            try:
                self.driver.save_screenshot("login_error.png")
                logging.info("📸 Screenshot saved: login_error.png")
            except:
                pass
            return False

    def submit_single_url(self, url):
        try:
            textarea = self.wait.until(
                EC.presence_of_element_located((By.NAME, "links"))
            )
            textarea.clear()
            textarea.send_keys(url)
            
            submit_btn = self.driver.find_element(
                By.XPATH, "//button[text()='Import Links']"
            )
            submit_btn.click()
            
            # Wait briefly for submission to process
            time.sleep(2)
            return True
            
        except Exception as e:
            logging.error(f"❌ Submission failed for {url}: {e}")
            return False

    def process_pending_urls(self, urls):
        pending = [u for u in urls if u not in self.submitted]
        
        if not pending:
            logging.info("🎉 No pending URLs. All done!")
            return True
            
        logging.info(f"📦 Processing {len(pending)}/{len(urls)} pending URLs")
        
        if not self.login():
            return False
            
        for i, url in enumerate(pending, 1):
            logging.info(f"🔄 [{i}/{len(pending)}] Submitting: {url[:60]}...")
            
            success = False
            for attempt in range(MAX_RETRIES):
                if self.submit_single_url(url):
                    self.save_submitted(url)
                    logging.info(f"✅ Success: {url}")
                    success = True
                    break
                else:
                    logging.warning(f"⚠️ Attempt {attempt+1}/{MAX_RETRIES} failed")
                    time.sleep(3)
            
            if not success:
                logging.error(f"❌ Failed after {MAX_RETRIES} attempts: {url}")
            
            # Polite delay between submissions
            if i < len(pending):
                time.sleep(1.5)
                
        return True

    def close(self):
        if self.driver:
            time.sleep(1)
            self.driver.quit()
            logging.info("🔚 WebDriver closed")

def main():
    # Validate credentials
    if not USERNAME or not PASSWORD:
        logging.error("❌ PANEL_USER or PANEL_PASS not set! Check GitHub Secrets.")
        sys.exit(1)
    
    # Validate URLs file
    if not os.path.exists(URLS_FILE):
        logging.error(f"❌ {URLS_FILE} not found")
        sys.exit(1)
    
    # Load and filter URLs
    with open(URLS_FILE, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip().startswith('http')]
    
    if not urls:
        logging.error("❌ No valid URLs found in file")
        sys.exit(1)
    
    logging.info(f"🚀 Starting automation | Total URLs: {len(urls)}")
    
    submitter = FastURLSubmitter()
    try:
        submitter.setup_driver()
        success = submitter.process_pending_urls(urls)
        sys.exit(0 if success else 1)
    finally:
        submitter.close()
    
    logging.info("✨ Cycle complete")

if __name__ == "__main__":
    main()
