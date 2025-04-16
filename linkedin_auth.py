import os
import json
import time
import random
import logging
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

logger = logging.getLogger(__name__)

class LinkedInAuth:
    LINKEDIN_COOKIES_FILE = "linkedin_cookies.json"
    USER_DATA_DIR = "playwright_user_data" # Directory to store persistent context

    def __init__(self, email, password, user_agents):
        self.email = email
        self.password = password
        self.user_agents = user_agents
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._session_valid = False
        self._playwright_instance_managed_externally = False # Flag to check if playwright instance is managed outside

    def _start_playwright(self):
        """Starts the Playwright instance if not already started."""
        if self._playwright is None:
            try:
                self._playwright = sync_playwright().start()
                self._playwright_instance_managed_externally = False
                logger.info("Playwright instance started.")
            except Exception as e:
                logger.error(f"Failed to start Playwright: {e}")
                raise

    def _launch_browser(self, headless=True):
        """Launches the browser if not already launched."""
        self._start_playwright() # Ensure playwright is running
        if self._browser is None:
            try:
                # Ensure the user data directory exists
                if not os.path.exists(self.USER_DATA_DIR):
                    os.makedirs(self.USER_DATA_DIR)

                self._browser = self._playwright.chromium.launch_persistent_context(
                    self.USER_DATA_DIR,
                    headless=headless, # Set headless mode
                    user_agent=random.choice(self.user_agents),
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        # Add other relevant args if needed, similar to ChromeOptions
                    ],
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    # viewport={'width': 1920, 'height': 1080} # Optional: Set viewport
                )
                self._context = self._browser # Persistent context is the browser object itself
                # Wait for the initial page (if any) to load or create a new one
                if self._context.pages:
                    self._page = self._context.pages[0]
                else:
                    self._page = self._context.new_page()

                # Apply stealth techniques
                self._apply_stealth(self._page)

                logger.info(f"Persistent Playwright browser context launched (Headless: {headless}).")

            except PlaywrightError as e:
                logger.error(f"Error launching Playwright browser: {e}")
                self.close() # Clean up if launch fails
                raise
            except Exception as e:
                 logger.error(f"Unexpected error launching Playwright browser: {e}")
                 self.close()
                 raise

    def _apply_stealth(self, page):
        """Applies stealth techniques to the page."""
        try:
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                // Add more stealth techniques if needed
            """)
            logger.debug("Stealth script added to page.")
        except Exception as e:
            logger.warning(f"Could not apply stealth techniques: {e}")

    def get_page(self, headless=True):
        """
        Returns a Playwright page object with a potentially valid LinkedIn session.
        Launches browser and logs in only if necessary.
        """
        if self._page is None or self._page.is_closed():
            logger.info("Playwright page not available or closed. Initializing...")
            self._launch_browser(headless=True) # Launch if not already running
            if not self._session_valid:
                 self.ensure_logged_in() # Try to log in if session wasn't already valid
        elif not self._session_valid:
            logger.info("Playwright page exists, but session not validated. Checking login status.")
            self.ensure_logged_in() # Check login status if page exists but session isn't confirmed valid

        # Ensure page is returned even if login fails, caller should handle errors
        if self._page is None or self._page.is_closed():
             logger.error("Failed to get a valid Playwright page.")
             # Attempt to relaunch once more
             try:
                 self._launch_browser(headless=headless)
                 self.ensure_logged_in()
                 if self._page is None or self._page.is_closed():
                     raise RuntimeError("Could not establish Playwright page after retry.")
             except Exception as e:
                 logger.critical(f"Fatal error getting Playwright page: {e}")
                 raise RuntimeError(f"Fatal error getting Playwright page: {e}") from e

        return self._page

    def save_cookies(self):
        """Saves cookies from the current context."""
        if not self._context:
            logger.warning("No browser context available to save cookies from.")
            return
        try:
            cookies = self._context.cookies()
            # Filter out session-only cookies if necessary, Playwright handles expiry better
            # persistent_cookies = [c for c in cookies if c.get('expires', -1) != -1]
            with open(self.LINKEDIN_COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
            logger.info(f"LinkedIn cookies saved ({len(cookies)} cookies).")
        except PlaywrightError as e:
            logger.error(f"Playwright error saving cookies: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving cookies: {e}")

    def load_cookies(self):
        """Loads cookies into the current context."""
        if not self._context:
            logger.error("No browser context available to load cookies into.")
            return False
        try:
            if not os.path.exists(self.LINKEDIN_COOKIES_FILE):
                logger.info("No LinkedIn cookies file found. Proceeding without loading cookies.")
                return False

            with open(self.LINKEDIN_COOKIES_FILE, 'r') as f:
                cookies = json.load(f)

            if not cookies:
                logger.info("Empty cookies file. Proceeding without loading cookies.")
                return False

            # Clear existing cookies before loading? Optional, depends on strategy.
            # self._context.clear_cookies()

            self._context.add_cookies(cookies)
            logger.info(f"Loaded {len(cookies)} cookies into the browser context.")
            # Navigate to LinkedIn homepage to make cookies effective for the domain
            if self._page and not self._page.is_closed():
                 try:
                     logger.info("Navigating to LinkedIn homepage after loading cookies.")
                     self._page.goto("https://www.linkedin.com/", timeout=30000, wait_until="domcontentloaded")
                     time.sleep(2) # Short pause
                 except (PlaywrightTimeoutError, PlaywrightError) as e:
                     logger.warning(f"Timeout or error navigating to LinkedIn after loading cookies: {e}")
            return True
        except json.JSONDecodeError:
            logger.warning("LinkedIn cookies file is corrupted. Removing it.")
            os.remove(self.LINKEDIN_COOKIES_FILE)
            return False
        except PlaywrightError as e:
            logger.error(f"Playwright error loading cookies: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading cookies: {e}")
            return False

    def verify_session(self):
        """Verifies if the LinkedIn session is active using Playwright."""
        if not self._page or self._page.is_closed():
            logger.warning("Cannot verify session: Playwright page is not available.")
            self._session_valid = False
            return False

        logger.info("Verifying LinkedIn session...")
        try:
            # Navigate to a page that requires login (e.g., feed)
            self._page.goto("https://www.linkedin.com/feed/", timeout=45000, wait_until="domcontentloaded")
            time.sleep(random.uniform(3, 5)) # Wait for dynamic content

            # Check for elements indicating a logged-in state
            # Option 1: Look for the main navigation bar
            nav_selector = "#global-nav"
            try:
                self._page.wait_for_selector(nav_selector, state="visible", timeout=10000)
                logger.info("LinkedIn session is valid (found global nav).")
                self._session_valid = True
                return True
            except PlaywrightTimeoutError:
                logger.debug("Global nav not found.")
                pass # Continue checking other indicators

            # Option 2: Check for profile picture/icon in header
            profile_pic_selector = "img.global-nav__me-photo" # Adjust selector if needed
            try:
                self._page.wait_for_selector(profile_pic_selector, state="visible", timeout=5000)
                logger.info("LinkedIn session is valid (found profile picture).")
                self._session_valid = True
                return True
            except PlaywrightTimeoutError:
                 logger.debug("Profile picture not found.")
                 pass

            # Option 3: Check if URL redirected to login/authwall
            current_url = self._page.url
            if "login" in current_url or "authwall" in current_url:
                logger.info("LinkedIn session has expired (redirected to login/authwall).")
                self._session_valid = False
                return False

            # Fallback: If none of the positive indicators are found, assume not logged in
            logger.warning("Could not definitively confirm LinkedIn session status. Assuming invalid.")
            self._session_valid = False
            return False

        except PlaywrightTimeoutError:
            logger.error("Timeout while verifying LinkedIn session.")
            self._session_valid = False
            return False
        except PlaywrightError as e:
            logger.error(f"Playwright error verifying session: {e}")
            self._session_valid = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error verifying session: {e}")
            self._session_valid = False
            return False

    def login_with_credentials(self):
        """Logs into LinkedIn using email and password with Playwright."""
        if not self._page or self._page.is_closed():
            logger.error("Cannot login: Playwright page is not available.")
            return False

        logger.info("Attempting full login with credentials using Playwright...")
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                logger.info(f"Login attempt {attempt + 1}/{max_attempts}")
                self._page.goto("https://www.linkedin.com/login", timeout=90000, wait_until="domcontentloaded")
                time.sleep(random.uniform(3, 5))

                # Wait for login form elements
                username_selector = "#username"
                password_selector = "#password"
                submit_button_selector = "button[type='submit']"

                self._page.wait_for_selector(username_selector, state="visible", timeout=20000)
                logger.debug("Username field visible.")

                # Fill username
                self._page.locator(username_selector).fill(self.email)
                time.sleep(random.uniform(0.5, 1.5))

                # Fill password
                self._page.locator(password_selector).fill(self.password)
                time.sleep(random.uniform(0.5, 1.5))

                # Click submit
                self._page.locator(submit_button_selector).click()
                logger.info("Login form submitted.")

                # Wait for navigation to feed or main page (indication of successful login)
                # Increased timeout for potential challenges/slow loads
                self._page.wait_for_selector("#global-nav", state="visible", timeout=90000)
                logger.info("Successfully logged into LinkedIn with credentials (found global nav).")

                # Save context state (includes cookies, local storage etc.)
                # self.save_context_state() # Use this instead of just cookies if needed
                self.save_cookies() # Save cookies specifically
                self._session_valid = True
                return True

            except PlaywrightTimeoutError:
                logger.warning(f"Timeout during login attempt {attempt + 1}. Checking for challenges...")
                # Check for common challenge elements (e.g., CAPTCHA, phone verification)
                if self._page.locator("iframe[title*='captcha']").is_visible():
                     logger.error("CAPTCHA detected. Manual intervention likely required.")
                     # Consider adding manual input pause here if running non-headless
                     # input("Please solve the CAPTCHA manually and press Enter...")
                     # return self.verify_session() # Re-verify after manual step
                     return False # Fail automatically in headless mode
                elif "checkpoint/challenge" in self._page.url:
                     logger.error("Security challenge detected. Manual intervention likely required.")
                     return False
                elif attempt < max_attempts - 1:
                     logger.info("Retrying login...")
                     time.sleep(random.uniform(5, 10))
                else:
                     logger.error("Login failed after multiple attempts due to timeout or challenge.")
                     return False
            except PlaywrightError as login_error:
                logger.error(f"Playwright error during login process: {login_error}")
                if attempt < max_attempts - 1:
                    logger.info("Retrying login...")
                    time.sleep(random.uniform(5, 10))
                else:
                    return False
            except Exception as e:
                 logger.error(f"Unexpected error during login: {e}")
                 return False # Don't retry on unexpected errors

        logger.error("Failed to login to LinkedIn after all attempts.")
        return False

    def ensure_logged_in(self):
        """
        Ensures a valid LinkedIn session using the persistent Playwright context.
        Attempts login only if the session is invalid.
        """
        if self._session_valid:
            logger.info("Session already marked as valid.")
            return True

        if not self._page or self._page.is_closed():
            logger.warning("Playwright page not available. Cannot ensure login.")
            # Attempt to re-initialize page before giving up
            try:
                self.get_page() # This will try to launch/get page
                if not self._page or self._page.is_closed():
                     logger.error("Failed to re-initialize page for login check.")
                     return False
            except Exception as e:
                 logger.error(f"Error re-initializing page for login check: {e}")
                 return False


        # 1. Verify current session status directly
        logger.info("Checking current session status before attempting login...")
        if self.verify_session():
            logger.info("Session verified successfully.")
            self._session_valid = True
            return True
        else:
            logger.info("Session verification failed or timed out.")
            self._session_valid = False # Explicitly mark as invalid

        # 2. If verification fails, attempt login with credentials
        logger.info("Session is invalid or unverified. Attempting login with credentials...")
        if self.login_with_credentials():
            # Re-verify after login attempt
            time.sleep(2) # Short pause before re-verification
            if self.verify_session():
                logger.info("Login successful and session verified.")
                self._session_valid = True
                return True
            else:
                logger.error("Login appeared successful, but session verification failed afterwards.")
                self._session_valid = False
                return False
        else:
            logger.error("Failed to login to LinkedIn using credentials.")
            self._session_valid = False
            return False

    def close(self):
        """Closes the Playwright browser and context."""
        logger.info("Closing Playwright resources...")
        if self._browser:
            try:
                self._browser.close()
                logger.info("Playwright browser context closed.")
            except PlaywrightError as e:
                logger.error(f"Error closing Playwright browser: {e}")
            except Exception as e:
                logger.error(f"Unexpected error closing browser: {e}")
            finally:
                self._browser = None
                self._context = None
                self._page = None

        if self._playwright and not self._playwright_instance_managed_externally:
            try:
                self._playwright.stop()
                logger.info("Playwright instance stopped.")
            except Exception as e:
                logger.error(f"Error stopping Playwright: {e}")
            finally:
                self._playwright = None

        self._session_valid = False
        logger.info("Playwright resources cleanup complete.")

    # Optional: Method to save full context state (more than just cookies)
    # def save_context_state(self, path="playwright_state.json"):
    #     if not self._context:
    #         logger.warning("No context to save state from.")
    #         return
    #     try:
    #         state = self._context.storage_state(path=path)
    #         logger.info(f"Browser context state saved to {path}")
    #     except Exception as e:
    #         logger.error(f"Error saving context state: {e}")