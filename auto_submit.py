# auto_submit.py - Auto URL Submitter for GitHub Actions (Chromium-Compatible)

import os
import sys
import logging
import time
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
HEADLESS = True

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

    def setup_driver(self):

        options = Options()

        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')

        options.add_argument(
            '--user-agent=Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }

        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option(
            "excludeSwitches",
            ["enable-automation"]
        )

        options.add_experimental_option(
            "useAutomationExtension",
            False
        )

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
            service = Service()

        self.driver = webdriver.Chrome(
            service=service,
            options=options
        )

        self.wait = WebDriverWait(self.driver, 12)

        logging.info("✅ WebDriver initialized")

    def login(self):

        try:

            logging.info(f"🔐 Logging into {PANEL_URL}")

            self.driver.get(PANEL_URL)

            username_field = self.wait.until(
                EC.presence_of_element_located(
                    (By.NAME, "login")
                )
            )

            password_field = self.driver.find_element(
                By.NAME,
                "password"
            )

            username_field.send_keys(USERNAME)
            password_field.send_keys(PASSWORD)

            password_field.submit()

            self.wait.until(
                EC.presence_of_element_located(
                    (By.NAME, "links")
                )
            )

            logging.info("✅ Login successful")

            return True

        except Exception as e:

            logging.error(f"❌ Login failed: {e}")

            try:
                self.driver.save_screenshot("login_error.png")
                logging.info("📸 Screenshot saved")
            except:
                pass

            return False

    def submit_single_url(self, url):

        try:

            textarea = self.wait.until(
                EC.presence_of_element_located(
                    (By.NAME, "links")
                )
            )

            textarea.clear()
            textarea.send_keys(url)

            submit_btn = self.driver.find_element(
                By.XPATH,
                "//button[text()='Import Links']"
            )

            submit_btn.click()

            time.sleep(2)

            return True

        except Exception as e:

            logging.error(
                f"❌ Submission failed for {url}: {e}"
            )

            return False

    def process_pending_urls(self, urls):

        logging.info(
            f"📦 Processing ALL {len(urls)} URLs"
        )

        if not self.login():
            return False

        for i, url in enumerate(urls, 1):

            logging.info(
                f"🔄 [{i}/{len(urls)}] Submitting: "
                f"{url[:60]}..."
            )

            success = False

            for attempt in range(MAX_RETRIES):

                if self.submit_single_url(url):

                    logging.info(f"✅ Success: {url}")

                    success = True
                    break

                else:

                    logging.warning(
                        f"⚠️ Attempt "
                        f"{attempt+1}/{MAX_RETRIES} failed"
                    )

                    time.sleep(3)

            if not success:

                logging.error(
                    f"❌ Failed after "
                    f"{MAX_RETRIES} attempts: {url}"
                )

            if i < len(urls):
                time.sleep(1.5)

        return True

    def close(self):

        if self.driver:

            time.sleep(1)

            self.driver.quit()

            logging.info("🔚 WebDriver closed")


def main():

    if not USERNAME or not PASSWORD:

        logging.error(
            "❌ PANEL_USER or PANEL_PASS not set!"
        )

        sys.exit(1)

    if not os.path.exists(URLS_FILE):

        logging.error(
            f"❌ {URLS_FILE} not found"
        )

        sys.exit(1)

    with open(
        URLS_FILE,
        'r',
        encoding='utf-8'
    ) as f:

        urls = [
            line.strip()
            for line in f
            if line.strip().startswith('http')
        ]

    if not urls:

        logging.error(
            "❌ No valid URLs found in file"
        )

        sys.exit(1)

    logging.info(
        f"🚀 Starting automation | "
        f"Total URLs: {len(urls)}"
    )

    submitter = FastURLSubmitter()

    try:

        submitter.setup_driver()

        success = submitter.process_pending_urls(urls)

        sys.exit(0 if success else 1)

    finally:

        submitter.close()


if __name__ == "__main__":
    main()
