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
                    headless=False,  # Always use visible browser for captchas
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
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                
                // Overwrite the permissions query
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => {
                    if (parameters.name === 'notifications') {
                        return Promise.resolve({state: Notification.permission});
                    }
                    return originalQuery(parameters);
                };
            """)
        except Exception as e:
            logger.warning(f"Could not apply stealth: {e}")

    def _setup_stealth_browser(self):
        """Enhanced stealth mode for Playwright to avoid detection"""
        # Create a more sophisticated stealth script
        stealth_script = """
        () => {
            // Pass WebDriver test
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
            
            // Pass Chrome test
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
            
            // Pass Permissions test
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            
            // Pass plugins length test
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [1, 2, 3, 4, 5];
                    plugins.refresh = () => {};
                    plugins.namedItem = () => null;
                    return plugins;
                },
            });
            
            // Pass languages test
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Overwrite the `plugins` property to use a custom getter
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    // Create a plugins-like object
                    const plugins = new Array(3);
                    plugins.namedItem = () => null;
                    plugins.refresh = () => {};
                    return plugins;
                },
            });
        }
        """
        
        # Apply the stealth script
        self.browser_context.add_init_script(stealth_script)

    
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

    def _detect_captcha(self):
        """Detect if a captcha or security challenge is present."""
        if not self._page or self._page.is_closed():
            return False
            
        try:
            # Check for common captcha indicators
            captcha_selectors = [
                "iframe[src*='recaptcha']",  # reCAPTCHA iframe
                "iframe[src*='captcha']",    # Generic captcha iframe
                "div.captcha-container",     # LinkedIn specific captcha container
                "div[data-id='captcha']",    # Another potential captcha indicator
                "input#captcha-challenge",   # Text input for captcha challenge
                "img.captcha",               # Captcha image
                "div.challenge-dialog",      # LinkedIn security challenge dialog
                "text=Security Verification",  # Security verification text
                "text=Security Challenge",     # Security challenge text
                "text=I'm not a robot",        # reCAPTCHA checkbox text
                "text=We need to verify it's you", # LinkedIn security check
                "div.artdeco-card__header:has-text('Let's do a quick security check')" # LinkedIn security check header
            ]
            
            for selector in captcha_selectors:
                try:
                    element_visible = self._page.locator(selector).is_visible(timeout=1000)
                    if element_visible:
                        logger.warning(f"Detected security challenge/captcha: {selector}")
                        return True
                except Exception:
                    pass
                    
            # Check for checkpoint challenge page in URL
            if "checkpoint/challenge" in self._page.url:
                logger.warning("Detected LinkedIn checkpoint challenge in URL")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error detecting captcha: {e}")
            return False

    def _handle_captcha(self, max_wait_time=300):
        """Handle captcha by waiting for user intervention."""
        try:
            # Ensure browser is visible for user interaction
            if self._browser and not self._page.is_closed():
                # Alert the user with a message in the browser
                self._page.evaluate("""() => {
                    const div = document.createElement('div');
                    div.id = 'captcha-alert';
                    div.style = 'position:fixed;top:0;left:0;width:100%;background-color:red;color:white;padding:20px;z-index:9999;text-align:center;font-size:18px;';
                    div.innerHTML = '<strong>SECURITY CHALLENGE DETECTED!</strong><br>Please solve the captcha manually, then the process will continue automatically.';
                    document.body.prepend(div);
                }""")
                
                logger.warning(f"Security challenge detected! Waiting up to {max_wait_time} seconds for user to solve it manually.")
                print(f"\n⚠️ SECURITY CHALLENGE DETECTED in LinkedIn login! ⚠️")
                print(f"Please look at the browser window and solve the captcha/security challenge.")
                print(f"The process will continue automatically once completed.")
                print(f"Waiting up to {max_wait_time} seconds for resolution...\n")
                
                # Wait for security challenge to disappear
                start_time = time.time()
                while time.time() - start_time < max_wait_time:
                    if not self._detect_captcha():
                        # Remove the alert message
                        try:
                            self._page.evaluate("""() => {
                                const alert = document.getElementById('captcha-alert');
                                if (alert) alert.remove();
                            }""")
                        except:
                            pass
                        
                        logger.info("Security challenge appears to be resolved!")
                        print("\n✅ Security challenge resolved! Continuing login process...\n")
                        return True
                    time.sleep(2)
                
                logger.error(f"Captcha not solved within {max_wait_time} seconds.")
                print("\n❌ Security challenge not solved within the time limit. Login failed.\n")
                return False
                
        except Exception as e:
            logger.error(f"Error during captcha handling: {e}")
            return False
            
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
                        
                        # Check for captcha after password submission
                        if self._detect_captcha():
                            if self._handle_captcha():
                                # Re-verify after captcha handling
                                if self._page.locator("#global-nav").is_visible(timeout=8000):
                                    self._session_valid = True
                                    self.save_cookies()
                                    return True
                            return False
                        
                        # Check if login succeeded after password submission
                        if self._page.locator("#global-nav").is_visible(timeout=8000):
                            self._session_valid = True
                            self.save_cookies()  # Save the refreshed cookies
                            return True
                except PlaywrightError:
                    # If interaction fails, continue to credential login
                    pass
            
            # Check for captcha/security challenge
            if self._detect_captcha():
                # We need to handle the captcha
                if self._handle_captcha():
                    # Re-verify after captcha handling
                    return self.verify_session()
                return False
            
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

            # Check for captcha before even attempting login
            if self._detect_captcha():
                if not self._handle_captcha():
                    return False
                # After captcha handled, reload the page
                self._page.goto("https://www.linkedin.com/login", timeout=30000)
                time.sleep(2)

            # Fill in credentials
            self._page.fill("#username", self.email)
            time.sleep(1)
            self._page.fill("#password", self.password)
            time.sleep(1)
            self._page.click("button[type='submit']")
            
            # Wait briefly to see if any challenges appear immediately after submit
            time.sleep(5)
            
            # Check for captcha or security challenge after initial submission
            if self._detect_captcha():
                if not self._handle_captcha():
                    return False
            
            # Wait for navigation to complete
            try:
                self._page.wait_for_selector("#global-nav", timeout=20000)
                self.save_cookies()
                self._session_valid = True
                return True
            except PlaywrightTimeoutError:
                # Check one more time for a late-appearing security challenge
                if "checkpoint/challenge" in self._page.url or self._detect_captcha():
                    logger.warning("Security challenge detected after login attempt")
                    if self._handle_captcha():
                        # After challenge is handled, verify we're logged in
                        if self._page.locator("#global-nav").is_visible(timeout=15000):
                            self._session_valid = True
                            self.save_cookies()
                            return True
                
                logger.error("Login failed, couldn't reach feed after login attempt")
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
                self._launch_browser(headless=False)  # Always use visible browser for captchas
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