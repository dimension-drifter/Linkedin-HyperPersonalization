import os
import json
import time
import random
import logging
import traceback
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
        """Starts the Playwright instance if not already started."""
        if self._playwright is None:
            try:
                logger.debug("Starting Playwright...")
                self._playwright = sync_playwright().start()
                self._playwright_instance_managed_externally = False
                logger.info("Playwright started successfully.")
            except Exception as e:
                logger.error(f"Failed to start Playwright: {e}", exc_info=True)
                raise

    def _launch_browser(self, headless=True):
        """Launches the browser and creates a context/page if they don't exist."""
        self._start_playwright()

        if self._browser is None or self._context is None:
            effective_headless = headless
            logger.info(f"Launching browser context (headless={effective_headless})...")
            try:
                if not os.path.exists(self.USER_DATA_DIR):
                    os.makedirs(self.USER_DATA_DIR)
                    logger.info(f"Created user data directory: {self.USER_DATA_DIR}")

                self._context = self._playwright.chromium.launch_persistent_context(
                    self.USER_DATA_DIR,
                    headless=effective_headless,
                    user_agent=random.choice(self.user_agents),
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-infobars",
                        "--window-size=1920,1080",
                    ],
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    viewport={'width': 1920, 'height': 1080},
                    slow_mo=random.uniform(50, 150)
                )
                self._browser = self._context
                logger.info("Browser context launched successfully.")

                if not self._context.pages:
                    logger.info("No initial page found, creating new page...")
                    self._page = self._context.new_page()
                else:
                    logger.info("Using existing page from context.")
                    self._page = self._context.pages[0]
                    if self._page.is_closed():
                         logger.warning("Existing page was closed, creating new page...")
                         self._page = self._context.new_page()

                self._apply_stealth(self._page)

            except Exception as e:
                logger.error(f"Error launching browser context: {e}", exc_info=True)
                self.close()
                raise
        elif self._page is None or self._page.is_closed():
             logger.info("Browser context exists, but page is missing or closed. Creating new page...")
             try:
                 self._page = self._context.new_page()
                 self._apply_stealth(self._page)
             except Exception as e:
                 logger.error(f"Error creating new page in existing context: {e}", exc_info=True)
                 self.close()
                 raise
        else:
            logger.debug("Browser, context, and page already exist.")

    def _apply_stealth(self, page):
        """Applies stealth techniques to the page."""
        if not page or page.is_closed():
            logger.warning("Cannot apply stealth, page is invalid.")
            return
        try:
            stealth_script = """
            () => {
                // General properties
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

                // Chrome specific properties
                if (navigator.userAgent.includes('Chrome')) {
                    window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };
                }

                // Permissions query override
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
                );

                // WebGL Vendor/Renderer spoofing
                try {
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) return 'Intel Open Source Technology Center';
                        if (parameter === 37446) return 'Mesa DRI Intel(R) Ivybridge Mobile ';
                        return getParameter(parameter);
                    };
                } catch (e) {}

                // Override Function.prototype.toString
                const originalToString = Function.prototype.toString;
                Function.prototype.toString = function() {
                    if (this === navigator.webdriver.get || this === navigator.languages.get) {
                        return 'function get() { [native code] }';
                    }
                    return originalToString.call(this);
                };
            }
            """
            page.add_init_script(stealth_script)
            logger.debug("Stealth script applied.")
        except Exception as e:
            logger.warning(f"Could not apply stealth script: {e}", exc_info=True)

    def save_cookies(self):
        """Saves cookies from the current context to a file."""
        if not self._context:
            logger.warning("Cannot save cookies, no browser context.")
            return
        try:
            cookies = self._context.cookies()
            valid_cookies = [
                cookie for cookie in cookies
                if isinstance(cookie.get('name'), str) and isinstance(cookie.get('value'), str) and
                   isinstance(cookie.get('domain'), str) and isinstance(cookie.get('path'), str)
            ]
            if not valid_cookies:
                logger.warning("No valid cookies found in context to save.")
                return

            with open(self.LINKEDIN_COOKIES_FILE, 'w') as f:
                json.dump(valid_cookies, f, indent=2)
            logger.info(f"Saved {len(valid_cookies)} cookies to {self.LINKEDIN_COOKIES_FILE}")
        except Exception as e:
            logger.error(f"Error saving cookies: {e}", exc_info=True)

    def load_cookies(self):
        """Loads cookies from the file into the current context."""
        if not self._context:
            logger.error("Cannot load cookies, no browser context.")
            return False
        if not os.path.exists(self.LINKEDIN_COOKIES_FILE):
            logger.info(f"Cookie file not found: {self.LINKEDIN_COOKIES_FILE}")
            return False

        try:
            with open(self.LINKEDIN_COOKIES_FILE, 'r') as f:
                cookies = json.load(f)

            if not cookies:
                logger.warning("Cookie file is empty.")
                return False

            logger.info(f"Loading {len(cookies)} cookies from file...")
            self._context.add_cookies(cookies)
            logger.info("Cookies added to context.")

            if self._page and not self._page.is_closed():
                logger.info("Navigating to LinkedIn homepage to apply loaded cookies...")
                try:
                    self._page.goto("https://www.linkedin.com/", timeout=60000, wait_until="networkidle")
                    time.sleep(random.uniform(2, 4))
                    logger.info(f"Current URL after loading cookies and navigating: {self._page.url}")
                    return True
                except Exception as e:
                    logger.error(f"Error navigating after loading cookies: {e}")
                    return True  # Still return True to allow verify_session to check
            else:
                logger.warning("No valid page to navigate after loading cookies.")
                return False

        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from cookie file. Deleting invalid file.")
            try:
                os.remove(self.LINKEDIN_COOKIES_FILE)
            except OSError as e:
                logger.error(f"Error deleting invalid cookie file: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading cookies: {e}", exc_info=True)
            return False

    def _handle_welcome_back_screen(self):
        """
        Specifically handles the 'Welcome Back' screen by clicking on the user profile.
        Returns True if successfully handled, False otherwise.
        """
        if not self._page or self._page.is_closed():
            return False
            
        try:
            # Check if we're on the Welcome Back screen
            welcome_header = self._page.locator("h1:has-text('Welcome Back')")
            if not welcome_header.is_visible(timeout=5000):
                return False  # Not on Welcome Back screen
                
            logger.info("Detected 'Welcome Back' screen. Attempting to click on profile.")
            
            # Try multiple selector strategies to find the profile button
            selectors = [
                # Try direct selector for the first card (most common case)
                ".cell", 
                # Try email-based selector
                f"div:has(text='{self.email}')",
                # Try first button in the list
                "button:first-of-type",
                # More generic selector for any profile card
                ".prefill-authentication-entity__info",
                # Try to find the button by aria-label
                "button[aria-label*='Sign in as']"
            ]
            
            for selector in selectors:
                try:
                    element = self._page.locator(selector).first
                    if element.is_visible(timeout=3000):
                        logger.info(f"Found profile element with selector: {selector}")
                        # Click with a longer timeout
                        element.click(timeout=10000)
                        logger.info("Clicked on profile card. Waiting for navigation...")
                        time.sleep(random.uniform(5, 8))  # Wait for the click to take effect
                        
                        # Check if we're still on Welcome Back screen
                        if not welcome_header.is_visible(timeout=2000):
                            logger.info("Successfully navigated away from Welcome Back screen.")
                            return True
                        else:
                            logger.warning("Still on Welcome Back screen after clicking.")
                            continue  # Try next selector
                except Exception as click_err:
                    logger.warning(f"Error clicking element with selector '{selector}': {click_err}")
                    continue  # Try next selector
                    
            # If we get here, none of the selectors worked
            logger.error("Failed to click profile on Welcome Back screen with all selectors.")
            
            # Last resort: try JavaScript click on the first profile card
            try:
                logger.info("Attempting JavaScript click on profile card...")
                self._page.evaluate("""
                    (() => {
                        // Try to find and click the first profile card
                        const cards = document.querySelectorAll('.cell, .prefill-authentication-entity__info');
                        if (cards && cards.length > 0) {
                            cards[0].click();
                            return true;
                        }
                        // Try to click any button that might be a profile
                        const buttons = document.querySelectorAll('button');
                        for (let btn of buttons) {
                            if (btn.offsetHeight > 0 && btn.offsetWidth > 0) {
                                btn.click();
                                return true;
                            }
                        }
                        return false;
                    })()
                """)
                time.sleep(random.uniform(5, 8))
                
                # Check if we're still on Welcome Back screen
                if not welcome_header.is_visible(timeout=2000):
                    logger.info("Successfully navigated away from Welcome Back screen using JavaScript.")
                    return True
            except Exception as js_err:
                logger.error(f"JavaScript click attempt failed: {js_err}")
                
            return False
            
        except Exception as e:
            logger.error(f"Error handling Welcome Back screen: {e}", exc_info=True)
            return False

    def _detect_captcha(self):
        """Detects if a captcha or security challenge is present on the current page."""
        if not self._page or self._page.is_closed():
            return False

        try:
            current_url = self._page.url
            if "checkpoint/challenge" in current_url or "captcha" in current_url:
                return True

            captcha_selectors = [
                "iframe[src*='recaptcha']",
                "iframe[title*='captcha']",
                "iframe[title*='challenge']",
                "div#captcha-internal",
                "input#captcha-input",
                ".challenge-form",
                "h1:has-text('Security Verification')",
                "h1:has-text('Let.s do a quick security check')",
                "h1:has-text('Let\\'s do a quick security check')",
                "button:has-text('Verify')",
                "#arkose-iframe",
            ]

            for selector in captcha_selectors:
                try:
                    if self._page.locator(selector).is_visible(timeout=1000):
                        return True
                except:
                    continue

            return False
        except Exception as e:
            logger.error(f"Error detecting captcha: {e}")
            return False

    def _handle_captcha(self, max_wait_time=300):
        """Waits for the user to manually solve a detected captcha/challenge."""
        if not self._page or self._page.is_closed():
            return False

        logger.warning(f"Security challenge detected! Waiting up to {max_wait_time} seconds for manual resolution.")
        print(f"\n⚠️ SECURITY CHALLENGE DETECTED! ⚠️")
        print(f"Please solve the challenge in the browser window.")
        print(f"Waiting up to {max_wait_time} seconds...\n")

        try:
            self._page.evaluate("""() => {
                let alertDiv = document.getElementById('captcha-alert-overlay');
                if (!alertDiv) {
                    alertDiv = document.createElement('div');
                    alertDiv.id = 'captcha-alert-overlay';
                    alertDiv.style = 'position:fixed; top:0; left:0; width:100%; padding:15px; background-color:rgba(255,0,0,0.8); color:white; z-index:10000; text-align:center; font-size:16px; font-weight:bold; border-bottom: 2px solid darkred;';
                    alertDiv.innerHTML = 'ACTION REQUIRED: Please solve the security challenge below. Waiting for completion...';
                    document.body.prepend(alertDiv);
                }
            }""")
        except Exception as e:
            logger.warning(f"Could not add visual alert to page: {e}")

        start_time = time.time()
        challenge_resolved = False
        while time.time() - start_time < max_wait_time:
            if not self._detect_captcha():
                logger.info("Security challenge appears to be resolved.")
                print("\n✅ Security challenge resolved! Continuing...\n")
                challenge_resolved = True
                break
            time.sleep(3)

        try:
            self._page.evaluate("""() => {
                const alertDiv = document.getElementById('captcha-alert-overlay');
                if (alertDiv) alertDiv.remove();
            }""")
        except Exception as e:
            pass

        if not challenge_resolved:
            logger.error(f"Captcha/Challenge not resolved within {max_wait_time} seconds.")
            print("\n❌ Security challenge timed out. Login/Verification failed.\n")
            return False

        time.sleep(random.uniform(2, 4))
        return True

    def _handle_password_prompt(self):
        """
        Handles password prompt page by entering password and submitting.
        Returns True if successful, False otherwise.
        """
        if not self._page or self._page.is_closed():
            return False
            
        try:
            password_field = self._page.locator("input#password[name='session_password']")
            if not password_field.is_visible(timeout=5000):
                return False  # No password prompt
                
            logger.info("Detected password prompt. Attempting to submit password...")
            
            # Fill password
            password_field.fill(self.password)
            time.sleep(random.uniform(0.5, 1.5))
            
            # Find and click submit button
            submit_button = self._page.locator("button[type='submit']:not([aria-label*='Dismiss'])").first
            if submit_button.is_visible(timeout=3000):
                submit_button.click()
                logger.info("Password submitted. Waiting for navigation...")
                time.sleep(random.uniform(5, 8))
                
                # Check if we still see password field (might indicate error)
                if password_field.is_visible(timeout=2000):
                    logger.error("Still on password prompt after submission. Likely error.")
                    return False
                    
                # Check for feed element to confirm success
                try:
                    if self._page.locator("#global-nav-search").is_visible(timeout=10000):
                        logger.info("Successfully logged in after submitting password.")
                        self.save_cookies()
                        self._session_valid = True
                        return True
                except:
                    pass
                    
                # Check for captcha
                if self._detect_captcha():
                    logger.warning("Captcha detected after submitting password.")
                    return False
                    
                # If we got here, we're not on password page anymore but not confirmed logged in
                logger.info("Password submitted successfully, but login status unclear.")
                return True  # Let verify_session determine final state
            else:
                logger.warning("Could not find submit button for password prompt.")
                return False
                
        except Exception as e:
            logger.error(f"Error handling password prompt: {e}", exc_info=True)
            return False

    def verify_session(self):
        """
        Verifies if the current session is logged in.
        Handles intermediate steps like "Welcome Back" and password prompts.
        Returns True if logged in, False otherwise.
        """
        if not self._page or self._page.is_closed():
            logger.error("Cannot verify session, page is invalid.")
            self._session_valid = False
            return False

        logger.info("Verifying LinkedIn session...")
        try:
            # Navigate to the feed or LinkedIn homepage
            logger.debug("Navigating to LinkedIn feed for verification...")
            try:
                self._page.goto("https://www.linkedin.com/feed/", timeout=60000, wait_until='networkidle')
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.warning(f"Error navigating to feed: {e}")
                # Continue with verification using current page state

            current_url = self._page.url
            logger.debug(f"Current URL for verification: {current_url}")

            # --- Handle intermediate screens ---
            
            # 1. Check and handle Welcome Back screen
            if "welcome-back" in current_url or "login?session_redirect" in current_url:
                logger.info("URL suggests Welcome Back screen.")
                if self._handle_welcome_back_screen():
                    # After handling Welcome Back, check if we need to handle password
                    if self._handle_password_prompt():
                        # Password handled successfully, should be logged in
                        logger.info("Handled Welcome Back and Password screens successfully.")
                        self._session_valid = True
                        return True
                    else:
                        # Check if we're now on feed despite password handling returning false
                        current_url = self._page.url
                        if "feed" in current_url:
                            logger.info("On feed after Welcome Back despite password handler reporting false.")
                            self._session_valid = True
                            return True
            
            # Direct check for Welcome Back screen by H1 text
            try:
                welcome_back = self._page.locator("h1:has-text('Welcome Back')").is_visible(timeout=5000)
                if welcome_back:
                    logger.info("Detected 'Welcome Back' screen by H1 text.")
                    if self._handle_welcome_back_screen():
                        # After Welcome Back, we might need password
                        self._handle_password_prompt()
                        # If we get to feed, we're successful
                        if "feed" in self._page.url or self._page.locator("#global-nav-search").is_visible(timeout=10000):
                            logger.info("Successfully logged in after handling Welcome Back screen.")
                            self._session_valid = True
                            return True
            except Exception as e:
                logger.warning(f"Error checking for Welcome Back screen: {e}")
            
            # 2. Handle Password Prompt if present
            if self._handle_password_prompt():
                logger.info("Successfully handled password prompt.")
                self._session_valid = True
                return True
                
            # 3. Check for captchas
            if self._detect_captcha():
                logger.warning("Captcha detected during session verification.")
                self._session_valid = False
                return False
                
            # --- Check for logged in state ---
            
            # 1. Check for definitive logged-in indicators
            try:
                if self._page.locator("#global-nav-search").is_visible(timeout=10000):
                    logger.info("Session verified: Global navigation search bar found.")
                    self._session_valid = True
                    return True
                if self._page.locator("img.global-nav__me-photo").is_visible(timeout=5000):
                    logger.info("Session verified: Profile picture found in navigation.")
                    self._session_valid = True
                    return True
                # Additional feed elements that indicate logged-in state
                if self._page.locator(".feed-shared-update-v2").is_visible(timeout=3000):
                    logger.info("Session verified: Feed posts found.")
                    self._session_valid = True
                    return True
            except Exception as e:
                logger.warning(f"Error checking for logged-in elements: {e}")
            
            # 2. Check for logged-out indicators
            current_url = self._page.url  # URL might have changed
            if "login" in current_url or "authwall" in current_url or "signup" in current_url:
                logger.info("Session invalid: Currently on login/authwall/signup page.")
                self._session_valid = False
                return False
                
            try:
                if self._page.locator("form.login__form").is_visible(timeout=1000):
                    logger.info("Session invalid: Login form detected.")
                    self._session_valid = False
                    return False
            except:
                pass

            # 3. If we got here without clear indicators, assume not logged in
            logger.warning("No clear logged-in indicators found. Assuming session is invalid.")
            self._session_valid = False
            return False

        except Exception as e:
            logger.error(f"Error during session verification: {e}", exc_info=True)
            self._session_valid = False
            return False

    def login_with_credentials(self):
        """Logs in using email and password."""
        if not self._page or self._page.is_closed():
            logger.error("Cannot login with credentials, page is invalid.")
            return False

        logger.info("Attempting login with credentials...")
        try:
            # Navigate to login page
            self._page.goto("https://www.linkedin.com/login", timeout=60000, wait_until="networkidle")
            time.sleep(random.uniform(2, 4))

            # Check for captcha before filling credentials
            if self._detect_captcha():
                logger.warning("Captcha detected on login page before entering credentials.")
                if not self._handle_captcha():
                    return False
                self._page.goto("https://www.linkedin.com/login", timeout=60000, wait_until="networkidle")
                time.sleep(random.uniform(2, 4))
                if self._detect_captcha():
                    logger.error("Captcha reappeared immediately. Aborting login.")
                    return False

            # Fill credentials
            logger.debug("Filling username and password...")
            self._page.fill("#username", self.email, timeout=10000)
            time.sleep(random.uniform(0.5, 1.5))
            self._page.fill("#password", self.password, timeout=10000)
            time.sleep(random.uniform(0.5, 1.5))

            # Click sign-in button
            signin_button = self._page.locator("button[type='submit'][data-litms-control-urn='login-submit']")
            if not signin_button.is_visible(timeout=5000):
                signin_button = self._page.locator("button:has-text('Sign in')")

            if not signin_button.is_visible(timeout=3000):
                logger.error("Could not find Sign in button.")
                return False

            signin_button.click(timeout=10000)
            logger.info("Credentials submitted. Waiting for login result...")
            time.sleep(random.uniform(3, 6))

            # Check for captcha after submission
            if self._detect_captcha():
                logger.warning("Captcha detected after login submission.")
                if not self._handle_captcha():
                    return False
                    
            # Handle Welcome Back if it appears
            if self._page.locator("h1:has-text('Welcome Back')").is_visible(timeout=3000):
                logger.info("Welcome Back screen appeared after credential login.")
                if not self._handle_welcome_back_screen():
                    logger.warning("Failed to handle Welcome Back screen after credential login.")
                    
            # Final verification
            logger.info("Verifying login success...")
            if self.verify_session():
                logger.info("Credential login successful!")
                self.save_cookies()
                self._session_valid = True
                return True
            else:
                logger.error("Login verification failed after credential submission.")
                self._session_valid = False
                return False

        except Exception as e:
            logger.error(f"Error during credential login: {e}", exc_info=True)
            self._session_valid = False
            return False

    def ensure_logged_in(self, run_headless=True):
        """
        Ensures the session is active. Tries cookies first, then credentials.
        Handles browser launch and captcha.
        """
        logger.info(f"Ensuring LinkedIn session is active (requested headless: {run_headless})...")
        
        # Determine if we need non-headless mode for login
        needs_non_headless = not os.path.exists(self.LINKEDIN_COOKIES_FILE)
        effective_headless = run_headless and not needs_non_headless
        
        try:
            # Launch browser with determined headless state
            self._launch_browser(headless=effective_headless)
            if not self._page or self._page.is_closed():
                logger.error("Failed to get a valid page after launch.")
                return False

            # Attempt to load cookies
            cookies_loaded = self.load_cookies()
            
            # First verification - might encounter Welcome Back
            if self.verify_session():
                logger.info("Session verified successfully.")
                return True
            
            # If verification failed with cookies in headless mode, try non-headless
            if cookies_loaded and effective_headless:
                logger.info("Cookie verification failed in headless mode. Trying non-headless...")
                self.close()
                self._launch_browser(headless=False)
                cookies_loaded = self.load_cookies()
                
                # Special handling for Welcome Back screen that might appear
                try:
                    if self._page.locator("h1:has-text('Welcome Back')").is_visible(timeout=5000):
                        logger.info("Welcome Back screen detected in non-headless mode.")
                        self._handle_welcome_back_screen()
                except Exception as e:
                    logger.warning(f"Error checking for Welcome Back screen: {e}")
                    
                if self.verify_session():
                    logger.info("Session verified in non-headless mode after cookies.")
                    
                    # If headless was requested, try switching back
                    if run_headless:
                        logger.info("Attempting to switch back to headless mode...")
                        self.save_cookies()  # Save the cookies from successful login
                        self.close()
                        self._launch_browser(headless=True)
                        self.load_cookies()
                        if self.verify_session():
                            logger.info("Successfully switched back to headless mode.")
                        else:
                            logger.warning("Failed to maintain session in headless mode.")
                            # Try one more time non-headless if needed
                            self.close()
                            self._launch_browser(headless=False)
                            self.load_cookies()
                    return True
            
            # If still not verified, try credential login (requires non-headless)
            if effective_headless:
                logger.info("Switching to non-headless for credential login...")
                self.close()
                self._launch_browser(headless=False)
            
            logger.info("Attempting credential login...")
            if self.login_with_credentials():
                logger.info("Credential login successful.")
                
                # Try to switch back to headless if originally requested
                if run_headless:
                    logger.info("Attempting to switch back to headless mode after credential login...")
                    self.save_cookies()
                    self.close()
                    self._launch_browser(headless=True)
                    self.load_cookies()
                    if self.verify_session():
                        logger.info("Successfully switched back to headless mode.")
                    else:
                        logger.warning("Failed to switch to headless. Reverting to non-headless.")
                        self.close()
                        self._launch_browser(headless=False)
                        self.load_cookies()
                        self.verify_session()
                
                return True
            else:
                logger.error("Credential login failed.")
                self._session_valid = False
                return False

        except Exception as e:
            logger.error(f"Critical error during login process: {e}", exc_info=True)
            self._session_valid = False
            self.close()
            return False

    def close(self):
        """Closes the browser and stops Playwright."""
        logger.info("Closing Playwright resources...")
        if self._context:
            try:
                self._context.close()
                logger.info("Browser context closed.")
            except Exception as e:
                logger.warning(f"Error closing browser context: {e}")
        
        self._browser = None
        self._context = None
        self._page = None

        if self._playwright and not self._playwright_instance_managed_externally:
            try:
                self._playwright.stop()
                logger.info("Playwright stopped.")
            except Exception as e:
                logger.warning(f"Error stopping Playwright: {e}")
            self._playwright = None

        self._session_valid = False
        logger.info("Playwright resources closed.")

    def get_page(self):
        """Returns the current page object, ensuring it's valid."""
        if self._page and not self._page.is_closed():
            return self._page
        
        logger.warning("get_page called but page is invalid. Attempting re-launch.")
        try:
            self._launch_browser(headless=False)
            return self._page
        except Exception:
             logger.error("Failed to re-establish page in get_page.")
             return None

    def get_context(self):
        """Returns the current browser context."""
        return self._context