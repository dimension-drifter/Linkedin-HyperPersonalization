import os
import json
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)

class LinkedInAuth:
    LINKEDIN_COOKIES_FILE = "linkedin_cookies.json"

    def __init__(self, email, password, user_agents):
        self.email = email
        self.password = password
        self.user_agents = user_agents
        self.driver = None
        self._session_valid = False

    def setup_selenium(self):
        if self.driver:
            return self.driver
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--allow-insecure-localhost")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--cipher-suite-blacklist=0x0088,0x0087,0x0039,0x0038,0x0044,0x0045,0x0066,0x0032,0x0033,0x0016,0x0013")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-features=NetworkService")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        service = Service(ChromeDriverManager().install())
        service.service_args = ['--verbose', '--log-path=chromedriver.log']
        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                """
            })
            self.driver.set_page_load_timeout(60)
        except Exception as e:
            logger.error(f"Error setting up Chrome driver: {str(e)}")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-features=IsolateOrigins")
            chrome_options.add_argument("--disable-site-isolation-trials")
            chrome_options.add_argument("--ssl-version-fallback-min=tls1")
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logger.info("Using fallback Chrome options")
        return self.driver

    def save_cookies(self):
        try:
            cookies = self.driver.get_cookies()
            with open(self.LINKEDIN_COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
            logger.info("LinkedIn cookies saved.")
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")

    def load_cookies(self):
        try:
            if not os.path.exists(self.LINKEDIN_COOKIES_FILE):
                logger.info("No LinkedIn cookies file found. Will proceed with fresh login.")
                return False
            with open(self.LINKEDIN_COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
            if not cookies:
                logger.info("Empty cookies file. Will proceed with fresh login.")
                return False
            self.driver.get("https://www.linkedin.com")
            time.sleep(3)
            cookies_added = 0
            for cookie in cookies:
                try:
                    for attr in ['expiry', 'sameSite']:
                        if attr in cookie:
                            del cookie[attr]
                    if 'domain' not in cookie:
                        cookie['domain'] = '.linkedin.com'
                    self.driver.add_cookie(cookie)
                    cookies_added += 1
                except Exception as e:
                    logger.debug(f"Could not add cookie {cookie.get('name')}: {str(e)}")
                    continue
            logger.info(f"Added {cookies_added} cookies out of {len(cookies)}")
            return cookies_added > 0
        except json.JSONDecodeError:
            logger.warning("LinkedIn cookies file is corrupted. Removing it and performing fresh login.")
            os.remove(self.LINKEDIN_COOKIES_FILE)
            return False
        except Exception as e:
            logger.error(f"Error loading cookies: {str(e)}")
            return False

    def verify_session(self):
        try:
            logger.info("LinkedIn session verification in progress...")
            self.driver.get("https://www.linkedin.com/feed/")
            time.sleep(5)
            login_indicators = [
                (By.ID, "global-nav"),
                (By.CSS_SELECTOR, "div.feed-identity-module"),
                (By.CSS_SELECTOR, "li.global-nav__primary-item")
            ]
            for indicator in login_indicators:
                try:
                    element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located(indicator)
                    )
                    if element.is_displayed():
                        logger.info("LinkedIn session is valid")
                        return True
                except:
                    continue
            if "login" in self.driver.current_url.lower():
                logger.info("LinkedIn session has expired (redirected to login)")
                return False
            logger.warning("Could not confirm LinkedIn session status")
            return False
        except Exception as e:
            logger.error(f"Error checking session validity: {str(e)}")
            return False

    def login_with_credentials(self):
        logger.info("Attempting full login with credentials...")
        self.driver.delete_all_cookies()
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                logger.info(f"Login attempt {attempt+1}/{max_attempts}")
                self.driver.get("https://www.linkedin.com/login")
                time.sleep(5)
                break
            except Exception as e:
                logger.warning(f"Error navigating to login page: {str(e)}")
                if attempt < max_attempts - 1:
                    logger.info("Retrying navigation...")
                    time.sleep(3)
                else:
                    logger.error("Failed to navigate to login page after multiple attempts")
                    return False
        try:
            username_field = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.clear()
            time.sleep(1)
            username_field.send_keys(self.email)
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            time.sleep(1)
            password_field.send_keys(self.password)
            time.sleep(1)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(random.uniform(5, 8))
            for _ in range(5):
                try:
                    WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.ID, "global-nav"))
                    )
                    logger.info("Successfully logged into LinkedIn with credentials")
                    self.save_cookies()
                    return True
                except:
                    time.sleep(3)
            logger.warning("LinkedIn login might have failed. Limited access.")
            return False
        except Exception as login_error:
            logger.error(f"Error during login process: {str(login_error)}")
            return False

    def ensure_logged_in(self):
        """
        Ensure a valid LinkedIn session. Only logs in if session is invalid.
        """
        if self._session_valid:
            return True
        self.setup_selenium()
        # Try cookies first
        cookies_loaded = self.load_cookies()
        if cookies_loaded:
            self.driver.refresh()
            time.sleep(3)
            if self.verify_session():
                self._session_valid = True
                return True
            logger.info("Could not confirm login with cookies, proceeding to credentials login")
        # Credentials login if cookies failed
        if self.login_with_credentials():
            if self.verify_session():
                self._session_valid = True
                return True
        logger.error("Failed to login to LinkedIn after all attempts.")
        return False

    def get_driver(self):
        """
        Main entry point: returns a Selenium driver with a valid LinkedIn session.
        Only logs in if needed.
        """
        if not self.driver:
            self.setup_selenium()
        if not self._session_valid:
            self.ensure_logged_in()
        return self.driver

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self._session_valid = False