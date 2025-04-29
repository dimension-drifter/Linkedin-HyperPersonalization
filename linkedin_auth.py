import os
import json
import time
import random
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

logger = logging.getLogger(__name__)

class LinkedInAuth:
    LINKEDIN_COOKIES_FILE = "linkedin_cookies.json"
    USER_DATA_DIR = "playwright_user_data"

    def __init__(self, email, password, user_agents):
        self.email = email
        self.password = password
        self.user_agents = user_agents
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session_valid = False
        self._playwright_instance_managed_externally = False

    def _start_playwright(self):
        if self._playwright is None:
            try:
                self._playwright = sync_playwright().start()
                self._playwright_instance_managed_externally = False
            except Exception as e:
                logger.error(f"Failed to start Playwright: {e}")
                raise

    def _launch_browser(self, headless=True):
        self._start_playwright()
        if self._browser is None:
            try:
                if not os.path.exists(self.USER_DATA_DIR):
                    os.makedirs(self.USER_DATA_DIR)

                self._browser = self._playwright.chromium.launch_persistent_context(
                    self.USER_DATA_DIR,
                    headless=False,
                    user_agent=random.choice(self.user_agents),
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                    ignore_https_errors=True,
                    java_script_enabled=True,
                )
                self._context = self._browser
                if self._context.pages:
                    self._page = self._context.pages[0]
                else:
                    self._page = self._context.new_page()

                self._apply_stealth(self._page)

            except Exception as e:
                logger.error(f"Error launching browser: {e}")
                self.close()
                raise

    def _apply_stealth(self, page):
        try:
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            """)
        except Exception as e:
            logger.warning(f"Could not apply stealth: {e}")

    def get_page(self, headless=True):
        if self._page is None or self._page.is_closed():
            self._launch_browser(headless=headless)
            if not self._session_valid:
                self.ensure_logged_in()
        elif not self._session_valid:
            self.ensure_logged_in()

        return self._page

    def save_cookies(self):
        if not self._context:
            return
        try:
            cookies = self._context.cookies()
            with open(self.LINKEDIN_COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")

    def load_cookies(self):
        if not self._context:
            return False
        try:
            if not os.path.exists(self.LINKEDIN_COOKIES_FILE):
                return False

            with open(self.LINKEDIN_COOKIES_FILE, 'r') as f:
                cookies = json.load(f)

            if not cookies:
                return False

            # First clear existing cookies to avoid conflicts
            self._context.clear_cookies()
            
            # Then add the cookies from file
            self._context.add_cookies(cookies)
            
            # After loading cookies, navigate to LinkedIn to apply them
            if self._page and not self._page.is_closed():
                try:
                    self._page.goto("https://www.linkedin.com/", timeout=45000)
                    time.sleep(3)  # Give more time for cookies to apply
                    return True
                except PlaywrightError:
                    # If navigation fails, try once more with a fresh page
                    if not self._page.is_closed():
                        self._page.close()
                    self._page = self._context.new_page()
                    self._apply_stealth(self._page)
                    self._page.goto("https://www.linkedin.com/", timeout=45000)
                    time.sleep(3)
                    return True
            return True
        except json.JSONDecodeError:
            if os.path.exists(self.LINKEDIN_COOKIES_FILE):
                os.remove(self.LINKEDIN_COOKIES_FILE)
            return False
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            return False

    def verify_session(self):
        if not self._page or self._page.is_closed():
            return False

        try:
            # Go to feed page which requires login
            try:
                self._page.goto("https://www.linkedin.com/feed/", timeout=45000)
                time.sleep(3)  # Give more time for the page to load completely
            except PlaywrightError:
                # If navigation fails, don't immediately fail - check the current state
                pass
                
            # Check if we're logged in by looking for navigation bar
            if self._page.locator("#global-nav").is_visible(timeout=8000):
                self._session_valid = True
                return True
            
            # Check for Welcome Back + Password challenge page
            if (self._page.locator("h1:has-text('Welcome Back')").is_visible(timeout=3000) or 
                self._page.locator("input#password").is_visible(timeout=3000)):
                # Handle the password challenge automatically
                try:
                    if self._page.locator("input#password").is_visible():
                        self._page.fill("input#password", self.password)
                        time.sleep(1)
                        self._page.click("button[type='submit']")
                        time.sleep(5)  # Give more time for login to complete
                        
                        # Check if login succeeded after password submission
                        if self._page.locator("#global-nav").is_visible(timeout=8000):
                            self._session_valid = True
                            self.save_cookies()  # Save the refreshed cookies
                            return True
                except PlaywrightError:
                    # If interaction fails, continue to credential login
                    pass
            
            # Check for login page redirect
            if "login" in self._page.url or "authwall" in self._page.url:
                self._session_valid = False
                return False
                
            # Fallback check
            self._session_valid = False
            return False

        except Exception as e:
            logger.error(f"Error verifying session: {e}")
            self._session_valid = False
            return False

    def login_with_credentials(self):
        if not self._page or self._page.is_closed():
            return False

        try:
            self._page.goto("https://www.linkedin.com/login", timeout=30000)
            time.sleep(2)

            self._page.fill("#username", self.email)
            time.sleep(1)
            self._page.fill("#password", self.password)
            time.sleep(1)
            self._page.click("button[type='submit']")
            
            # Wait for navigation to complete
            try:
                self._page.wait_for_selector("#global-nav", timeout=20000)
                self.save_cookies()
                self._session_valid = True
                return True
            except PlaywrightTimeoutError:
                if "checkpoint/challenge" in self._page.url:
                    logger.error("Security challenge detected")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def ensure_logged_in(self):
        # First check if we're already logged in to avoid redundant attempts
        if self._session_valid and self._page and not self._page.is_closed():
            try:
                # Quick check if we're still on LinkedIn
                if "linkedin.com" in self._page.url:
                    return True
            except:
                # If page access fails, continue with login process
                pass
        
        # Make sure we have a page to work with
        if not self._page or self._page.is_closed():
            try:
                self._launch_browser(headless=False)
            except Exception as e:
                logger.error(f"Failed to launch browser: {e}")
                return False
        
        # Clear the session valid flag to ensure we go through verification
        self._session_valid = False
        
        # Step 1: Load cookies (but don't immediately verify - this avoids the race condition)
        cookies_loaded = self.load_cookies()
        if not cookies_loaded:
            logger.info("No cookies loaded or cookies file not found")
        
        # Step 2: Now verify session state 
        if self.verify_session():
            self._session_valid = True
            return True
        
        # Step 3: If verification failed, only now try credential login
        logger.info("Session verification failed. Attempting credential login...")
        if self.login_with_credentials():
            self._session_valid = True
            self.save_cookies()
            return True
        
        self._session_valid = False
        return False

    def close(self):
        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
            self._context = None
            self._page = None

        if self._playwright and not self._playwright_instance_managed_externally:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._session_valid = False