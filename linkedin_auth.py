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

# Set up logging
logger = logging.getLogger(__name__)

class LinkedInAuth:
    """
    Class to handle LinkedIn authentication, session management, and cookies
    """
    LINKEDIN_COOKIES_FILE = "linkedin_cookies.json"
    
    def __init__(self, email, password, user_agents):
        """
        Initialize the LinkedIn authentication manager
        
        Args:
            email (str): LinkedIn account email
            password (str): LinkedIn account password
            user_agents (list): List of user agent strings to use randomly
        """
        self.email = email
        self.password = password
        self.user_agents = user_agents
        self.driver = None
    
    def setup_selenium(self):
        """Set up Selenium WebDriver for LinkedIn with improved SSL handling"""
        chrome_options = Options()
        # chrome_options.add_argument("--headless=new")  # Use newer headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Enhanced SSL error handling
        chrome_options.add_argument("--ignore-certificate-errors")
        chrome_options.add_argument("--ignore-ssl-errors")
        chrome_options.add_argument("--allow-insecure-localhost")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        
        # Add Chrome's built-in cipher suite preference
        chrome_options.add_argument("--cipher-suite-blacklist=0x0088,0x0087,0x0039,0x0038,0x0044,0x0045,0x0066,0x0032,0x0033,0x0016,0x0013")
        
        # Fix for common certificate issues
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-features=NetworkService")
        
        # Make it harder for LinkedIn to detect automation
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Set up Chrome driver with service_args to avoid SSL issues
        service = Service(ChromeDriverManager().install())
        service.service_args = ['--verbose', '--log-path=chromedriver.log']
        
        try:
            self.driver = webdriver.Chrome(
                service=service,
                options=chrome_options
            )
            
            # Execute CDP commands to make automation less detectable
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                """
            })
            
            # Increase default page load timeout
            self.driver.set_page_load_timeout(60)
            
        except Exception as e:
            logger.error(f"Error setting up Chrome driver: {str(e)}")
            # Fallback options with even more SSL bypassing
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-features=IsolateOrigins")
            chrome_options.add_argument("--disable-site-isolation-trials")
            
            # Use a more compatible SSL configuration in fallback
            chrome_options.add_argument("--ssl-version-fallback-min=tls1")
            
            try:
                self.driver = webdriver.Chrome(
                    service=service,
                    options=chrome_options
                )
                logger.info("Using fallback Chrome options")
            except Exception as fallback_error:
                logger.critical(f"Fatal error creating Chrome driver: {str(fallback_error)}")
                raise
                
        return self.driver
    
    def save_cookies(self):
        """Save browser cookies to a file."""
        try:
            cookies = self.driver.get_cookies()
            with open(self.LINKEDIN_COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
            logger.info("LinkedIn cookies saved.")
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")

    def load_cookies(self):
        """Load browser cookies from a file with improved error handling."""
        try:
            # Check if cookie file exists
            if not os.path.exists(self.LINKEDIN_COOKIES_FILE):
                logger.info("No LinkedIn cookies file found. Will proceed with fresh login.")
                return False
                
            # Read cookie file
            with open(self.LINKEDIN_COOKIES_FILE, 'r') as f:
                cookies = json.load(f)
                
            if not cookies:
                logger.info("Empty cookies file. Will proceed with fresh login.")
                return False
            
            # Visit LinkedIn domain once before adding cookies
            logger.info("Visiting LinkedIn domain before adding cookies...")
            self.driver.get("https://www.linkedin.com")
            time.sleep(3)  # Allow more time for page to load completely
            
            # Add cookies one by one with better error handling
            cookies_added = 0
            
            for cookie in cookies:
                try:
                    # Remove problematic cookie attributes
                    for attr in ['expiry', 'sameSite']:
                        if attr in cookie:
                            del cookie[attr]
                    
                    # Ensure domain is set correctly (add domain if missing)
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

    def login(self):
        """Login to LinkedIn with improved cookie handling and detection avoidance."""
        if not self.email or not self.password:
            logger.warning("LinkedIn credentials not provided. Proceeding without login.")
            return False

        try:
            logger.info("Attempting LinkedIn login...")
            
            # Try using cookies first
            cookies_loaded = self.load_cookies()
            
            if cookies_loaded:
                # After adding cookies, refresh and navigate to feed
                logger.info("Cookies added, refreshing page...")
                self.driver.refresh()
                time.sleep(3)
                
                # Navigate to feed to check login status
                logger.info("Checking if we're logged in...")
                try:
                    self.driver.get("https://www.linkedin.com/feed/")
                    time.sleep(5)  # Allow more time to load
                except Exception as e:
                    logger.warning(f"Error navigating to feed: {str(e)}")
                    # Try an alternative URL
                    self.driver.get("https://www.linkedin.com/")
                    time.sleep(5)
                    
                # Check for login success indicators
                try:
                    # Check multiple indicators of successful login
                    login_indicators = [
                        (By.ID, "global-nav"),
                        (By.CSS_SELECTOR, "div.feed-identity-module"),
                        (By.CSS_SELECTOR, "li.global-nav__primary-item")
                    ]
                    
                    for indicator in login_indicators:
                        try:
                            WebDriverWait(self.driver, 3).until(EC.presence_of_element_located(indicator))
                            logger.info(f"Login successful! Found indicator: {indicator[1]}")
                            return True
                        except:
                            pass
                            
                    # If none of the indicators are found
                    logger.info("Could not confirm login with cookies, proceeding to credentials login")
                except:
                    logger.warning("Saved cookies might be invalid. Proceeding to full login.")
            
            # Full login with credentials
            logger.info("Attempting full login with credentials...")
            
            # Clear cookies and cache before trying credentials
            self.driver.delete_all_cookies()
            
            # Go to login page with a clean state and retry mechanism
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    logger.info(f"Login attempt {attempt+1}/{max_attempts}")
                    self.driver.get("https://www.linkedin.com/login")
                    time.sleep(5)  # Longer wait for page to load
                    break
                except Exception as e:
                    logger.warning(f"Error navigating to login page: {str(e)}")
                    if attempt < max_attempts - 1:
                        logger.info("Retrying navigation...")
                        time.sleep(3)
                    else:
                        logger.error("Failed to navigate to login page after multiple attempts")
                        return False
            
            # Wait for login form and enter credentials
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
                
                # Add a random delay to simulate human behavior
                time.sleep(random.uniform(5, 8))
                
                # Check for login success
                for _ in range(5):  # Try more times with longer delays
                    try:
                        WebDriverWait(self.driver, 8).until(
                            EC.presence_of_element_located((By.ID, "global-nav"))
                        )
                        logger.info("Successfully logged into LinkedIn with credentials")
                        self.save_cookies()  # Save cookies after successful login
                        return True
                    except:
                        time.sleep(3)  # Longer wait between retries
                        
                logger.warning("LinkedIn login might have failed. Limited access.")
                return False
                    
            except Exception as login_error:
                logger.error(f"Error during login process: {str(login_error)}")
                return False

        except Exception as e:
            logger.error(f"Error during LinkedIn login process: {str(e)}")
            return False
    
    def verify_session(self):
        """Verify if the current LinkedIn session is still valid"""
        try:
            logger.info("LinkedIn session verification in progress...")
            
            # Try to navigate to the feed page as a session verification
            try:
                self.driver.get("https://www.linkedin.com/feed/")
                time.sleep(5)  # Allow page to load
            except Exception as e:
                logger.warning(f"Error navigating to feed during session verification: {str(e)}")
                return False
                
            # Check for indicators of being logged in
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
            
            # Check if we're redirected to a login page
            if "login" in self.driver.current_url.lower():
                logger.info("LinkedIn session has expired (redirected to login)")
                return False
                
            logger.warning("Could not confirm LinkedIn session status")
            return False
            
        except Exception as e:
            logger.error(f"Error checking session validity: {str(e)}")
            return False
            
    def close(self):
        """Close the Selenium WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None