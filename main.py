import os
from dotenv import load_dotenv
load_dotenv()
import requests
import json
import time
import re
import csv
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import google.generativeai as genai
import logging
import sqlite3
import random
from urllib.parse import quote_plus

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("linkedin_outreach.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize database
def init_database():
    conn = sqlite3.connect('linkedin_outreach.db')
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS founders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        linkedin_url TEXT UNIQUE,
        full_name TEXT,
        headline TEXT,
        summary TEXT,
        location TEXT,
        processed_date TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        founder_id INTEGER,
        name TEXT,
        title TEXT,
        description TEXT,
        website TEXT,
        FOREIGN KEY (founder_id) REFERENCES founders (id)
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        founder_id INTEGER,
        message_text TEXT,
        generated_date TEXT,
        was_sent INTEGER DEFAULT 0,
        FOREIGN KEY (founder_id) REFERENCES founders (id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Config setup
class Config:
    def __init__(self):
        # Load Gemini API key from environment variable
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not self.gemini_api_key:
            logger.error("GEMINI_API_KEY environment variable not set!")
            raise ValueError("GEMINI_API_KEY environment variable not set!")
        
        # LinkedIn credentials (for selenium scraping approach)
        self.linkedin_email = os.getenv("LINKEDIN_EMAIL")
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD")
        
        # Configure Gemini
        genai.configure(api_key=self.gemini_api_key)
        
        # User agent for requests
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
        ]

# LinkedIn data extraction class
class LinkedInScraper:
    def __init__(self, config):
        self.config = config
        self.setup_selenium()
        
    def setup_selenium(self):
        """Optimized Selenium setup for faster performance"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Critical speed optimizations
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-notifications")
        
        # Disable images and other resource loading (massive speedup)
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        prefs = {
            "profile.default_content_setting_values": {
                "images": 2,       # Block images
                "plugins": 2,      # Block plugins
                "popups": 2,       # Block popups
                "geolocation": 2,  # Block geolocation
                "notifications": 2 # Block notifications
            },
            "profile.managed_default_content_settings.javascript": 1  # Allow JavaScript
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Existing anti-detection code...
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(f"user-agent={random.choice(self.config.user_agents)}")
        
        # Set up Chrome driver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Execute CDP commands to make automation less detectable
        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
            """
        })
    
    LINKEDIN_COOKIES_FILE = "linkedin_cookies.json" # Define a file to store cookies

    def _save_cookies(self):
        """Save browser cookies to a file."""
        try:
            cookies = self.driver.get_cookies()
            with open(self.LINKEDIN_COOKIES_FILE, 'w') as f:
                json.dump(cookies, f)
            logger.info("LinkedIn cookies saved.")
        except Exception as e:
            logger.error(f"Error saving cookies: {e}")

    def _load_cookies(self):
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

    def login_to_linkedin(self):
        """Login to LinkedIn with improved cookie handling and detection avoidance."""
        if not self.config.linkedin_email or not self.config.linkedin_password:
            logger.warning("LinkedIn credentials not provided. Proceeding without login.")
            return False

        try:
            logger.info("Attempting LinkedIn login...")
            
            # Try using cookies first
            cookies_loaded = self._load_cookies()
            
            if cookies_loaded:
                # After adding cookies, refresh and navigate to feed
                logger.info("Cookies added, refreshing page...")
                self.driver.refresh()
                time.sleep(3)
                
                # Navigate to feed to check login status
                logger.info("Checking if we're logged in...")
                self.driver.get("https://www.linkedin.com/feed/")
                time.sleep(5)  # Allow more time to load
                
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
            self.driver.get("chrome://settings/clearBrowserData")
            time.sleep(2)
            
            # Go to login page with a clean state
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(3)
            
            # Wait for login form and enter credentials
            try:
                username_field = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                username_field.clear()
                username_field.send_keys(self.config.linkedin_email)
                
                password_field = self.driver.find_element(By.ID, "password")
                password_field.clear()
                password_field.send_keys(self.config.linkedin_password)
                
                self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                
                # Add a random delay to simulate human behavior
                time.sleep(random.uniform(3, 5))
                
                # Check for login success
                for _ in range(3):  # Try a few times with delays
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.ID, "global-nav"))
                        )
                        logger.info("Successfully logged into LinkedIn with credentials")
                        self._save_cookies()  # Save cookies after successful login
                        return True
                    except:
                        time.sleep(2)  # Wait and retry
                        
                logger.warning("LinkedIn login might have failed. Limited access.")
                return False
                
            except Exception as login_error:
                logger.error(f"Error during login process: {str(login_error)}")
                return False

        except Exception as e:
            logger.error(f"Error during LinkedIn login process: {str(e)}")
            return False
    
    def extract_profile_data(self, profile_url):
        """Extract data from a LinkedIn profile with dynamic waits"""
        logger.info(f"Extracting data from LinkedIn profile: {profile_url}")
        
        try:
            # First check cache
            cached_profile = self.get_cached_profile(profile_url)
            if cached_profile:
                logger.info("Using cached profile data")
                return cached_profile
            
            # Navigate to the profile
            self.driver.get(profile_url)
            
            # Wait for specific elements instead of fixed sleep
            try:
                # Wait for name to appear - a good indicator the profile has loaded
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 
                        "h1.text-heading-xlarge, h1.inline.t-24.t-black.t-normal.break-words"))
                )
            except:
                logger.warning("Timed out waiting for profile page to load")
                
            # Scroll through the page to load all content
            self._scroll_profile_page()
            
            # Get profile HTML
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract basic profile information
            profile_data = {}
            
            # Get full name - using existing implementation
            try:
                # Try multiple selector strategies to find the name
                name_selectors = [
                    "h1.text-heading-xlarge",
                    "h1.inline.t-24.t-black.t-normal.break-words", 
                    "h1.text-heading-xlarge.inline.t-24.t-black.t-normal.break-words",
                    "h1.pv-text-details__left-panel--name"
                ]
                
                name_found = False
                for selector in name_selectors:
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        name_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        profile_data['full_name'] = name_element.text.strip()
                        name_found = True
                        logger.info(f"Found name using selector: {selector}")
                        break
                    except Exception as selector_error:
                        logger.debug(f"Selector {selector} failed: {str(selector_error)}")
                
                if not name_found:
                    h1_elements = self.driver.find_elements(By.TAG_NAME, "h1")
                    if h1_elements:
                        profile_data['full_name'] = h1_elements[0].text.strip()
                        logger.info("Found name using generic h1 approach")
                    else:
                        profile_data['full_name'] = "Unknown"
                        logger.warning("Could not find name element on profile page")
            except Exception as name_error:
                logger.error(f"Error extracting name: {str(name_error)}")
                profile_data['full_name'] = "Unknown"
                
            # Get headline - multiple selector approach
            try:
                headline_selectors = [
                    "div.text-body-medium",
                    "div.pv-text-details__left-panel--subtitle",
                    "div.text-body-medium.break-words"
                ]
                
                for selector in headline_selectors:
                    try:
                        headline = self.driver.find_element(By.CSS_SELECTOR, selector)
                        profile_data['headline'] = headline.text.strip()
                        break
                    except:
                        continue
                        
                if 'headline' not in profile_data:
                    profile_data['headline'] = ""
            except:
                profile_data['headline'] = ""
                
            # Get location - multiple selector approach
            try:
                location_selectors = [
                    "span.text-body-small.inline.t-black--light.break-words",
                    "span.pv-text-details__left-panel--location",
                    "span.text-body-small.inline.break-words"
                ]
                
                for selector in location_selectors:
                    try:
                        location = self.driver.find_element(By.CSS_SELECTOR, selector)
                        profile_data['location'] = location.text.strip()
                        break
                    except:
                        continue
                        
                if 'location' not in profile_data:
                    profile_data['location'] = ""
            except:
                profile_data['location'] = ""
                
            # Get summary/about with improved extraction
            try:
                # Try to expand the about section if available
                try:
                    see_more_buttons = self.driver.find_elements(By.CSS_SELECTOR, "button.inline-show-more-text__button")
                    for button in see_more_buttons:
                        if "about" in button.get_attribute("innerHTML").lower():
                            button.click()
                            time.sleep(1)
                            break
                except:
                    pass
                    
                # Try multiple selector approaches for about section
                about_selectors = [
                    "div.display-flex.ph5.pv3",
                    "section.pv-about-section div.pv-shared-text-with-see-more",
                    "div#about + div div.display-flex"
                ]
                
                for selector in about_selectors:
                    try:
                        about_section = self.driver.find_element(By.CSS_SELECTOR, selector)
                        profile_data['summary'] = about_section.text.strip()
                        break
                    except:
                        continue
                    
                if 'summary' not in profile_data:
                    profile_data['summary'] = ""
            except:
                profile_data['summary'] = ""
                
            # Get experience section with enhanced extraction
            profile_data['experiences'] = []
            try:
                # First try to expand the experience section if needed
                try:
                    # Try clicking on the experience section to expand it
                    experience_sections = self.driver.find_elements(By.XPATH, "//section[contains(@class, 'experience-section')] | //section[@id='experience']")
                    if experience_sections:
                        experience_sections[0].click()
                        time.sleep(2)
                except:
                    pass
                
                # Try multiple selector approaches for experience items
                experience_selectors = [
                    "li.artdeco-list__item.pvs-list__item--line-separated",
                    "section#experience ul.pvs-list li.pvs-list__item--line-separated",
                    "div.pvs-entity"
                ]
                
                experience_elements = []
                for selector in experience_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            experience_elements = elements
                            logger.info(f"Found {len(elements)} experience elements using selector: {selector}")
                            break
                    except:
                        continue
                
                for element in experience_elements:
                    try:
                        # Try multiple ways to extract company and title
                        company_name = ""
                        title = ""
                        description = ""
                        company_url = ""
                        
                        # Check for company name and title in various formats
                        try:
                            # Format 1: Title is bold, company is normal text
                            title_element = element.find_element(By.CSS_SELECTOR, "span.t-16.t-bold, span.mr1.t-bold")
                            company_element = element.find_element(By.CSS_SELECTOR, "span.t-14.t-normal, span.t-normal")
                            
                            title = title_element.text.strip()
                            company_name = company_element.text.strip()
                        except:
                            try:
                                # Format 2: Look for h3 for title and p for company
                                title_element = element.find_element(By.CSS_SELECTOR, "h3")
                                company_element = element.find_element(By.CSS_SELECTOR, "p.pv-entity__secondary-title")
                                
                                title = title_element.text.strip()
                                company_name = company_element.text.strip()
                            except:
                                # Try other approaches
                                all_spans = element.find_elements(By.TAG_NAME, "span")
                                if len(all_spans) >= 2:
                                    title = all_spans[0].text.strip()
                                    company_name = all_spans[1].text.strip()
                        
                        # Try to get company URL if available
                        try:
                            links = element.find_elements(By.TAG_NAME, "a")
                            for link in links:
                                href = link.get_attribute("href")
                                if href and "company" in href:
                                    company_url = href
                                    break
                        except:
                            pass
                        
                        # Try to get description if available
                        try:
                            desc_elements = element.find_elements(By.CSS_SELECTOR, "div.inline-show-more-text")
                            if desc_elements:
                                description = desc_elements[0].text.strip()
                        except:
                            pass
                        
                        # Only add if we have at least a company or title
                        if company_name or title:
                            experience = {
                                'company': company_name,
                                'title': title,
                                'description': description,
                                'company_linkedin_url': company_url
                            }
                            profile_data['experiences'].append(experience)
                    except Exception as exp_error:
                        logger.debug(f"Error processing experience element: {str(exp_error)}")
                        continue
            except Exception as e:
                logger.warning(f"Error extracting experience data: {str(e)}")
            
            # Extract education if available
            profile_data['education'] = []
            try:
                # Try to find and click on the education section
                try:
                    education_sections = self.driver.find_elements(By.XPATH, "//section[contains(@class, 'education-section')] | //section[@id='education']")
                    if education_sections:
                        education_sections[0].click()
                        time.sleep(2)
                except:
                    pass
                
                education_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.education__list-item, li.pvs-list__item--line-separated")
                for element in education_elements:
                    try:
                        institution = ""
                        degree = ""
                        
                        # Try to find institution and degree
                        try:
                            institution_element = element.find_element(By.CSS_SELECTOR, "h3.pv-entity__school-name, span.t-16.t-bold")
                            institution = institution_element.text.strip()
                        except:
                            pass
                        
                        try:
                            degree_element = element.find_element(By.CSS_SELECTOR, "p.pv-entity__degree-name, span.t-14.t-normal")
                            degree = degree_element.text.strip()
                        except:
                            pass
                        
                        if institution:
                            education = {
                                'institution': institution,
                                'degree': degree
                            }
                            profile_data['education'].append(education)
                    except:
                        continue
            except:
                pass
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Error extracting LinkedIn profile data: {str(e)}")
            return None

    def _scroll_profile_page(self):
        """Optimized profile scrolling - much faster than before"""
        try:
            # Get page height
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Use fewer scroll steps (3 instead of 8)
            steps = 3
            for i in range(steps):
                # Scroll in bigger chunks
                self.driver.execute_script(f"window.scrollTo(0, {(i+1) * total_height / steps});")
                # Much shorter wait between scrolls
                time.sleep(0.3)
            
            # No need to scroll back to top - saves time
        except Exception as e:
            logger.debug(f"Error during page scrolling: {str(e)}")
    
    def close(self):
        """Close the Selenium WebDriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()

# Company research class using free APIs
class CompanyResearcher:
    def __init__(self, config):
        self.config = config
    
    def search_company_info(self, company_name, fast_mode=False):
        """Search for company information with speed optimizations"""
        logger.info(f"Researching company: {company_name}")
        
        # Set a short timeout
        timeout = 3  # seconds
        
        company_info = {
            'name': company_name,
            'website': self._find_company_website(company_name, timeout),
            'description': self._get_company_description(company_name, timeout),
            'news': []  # Skip news by default in fast mode
        }
        
        # Only get news in normal mode (not fast mode)
        if not fast_mode:
            company_info['news'] = self._get_news_articles(company_name, timeout)
        
        return company_info

    def _find_company_website(self, company_name, timeout=3):
        """Find company website with timeout"""
        try:
            encoded_query = quote_plus(f"{company_name} official website")
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            headers = {'User-Agent': random.choice(self.config.user_agents)}
            response = requests.get(url, headers=headers, timeout=timeout)
            # Rest of code...
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout finding website for {company_name}")
            return ""
        except Exception as e:
            logger.error(f"Error finding company website: {str(e)}")
            return ""

    def _get_news_articles(self, company_name, timeout=3):
        """Get news articles about the company using free News API"""
        try:
            # Using GDELT's free news search via Webhose
            encoded_query = quote_plus(company_name)
            url = f"https://webhose.io/filterWebContent?token=demo&format=json&sort=relevancy&q={encoded_query}"
            
            headers = {
                'User-Agent': random.choice(self.config.user_agents)
            }
            
            response = requests.get(url, headers=headers, timeout=timeout)
            articles = []
            
            if response.status_code == 200:
                data = response.json()
                for post in data.get('posts', [])[:3]:  # Get top 3 articles
                    articles.append({
                        'title': post.get('title', ''),
                        'link': post.get('url', '')
                    })
            
            return articles
        except Exception as e:
            logger.error(f"Error fetching news: {str(e)}")
            return []
    
    def _get_company_description(self, company_name, timeout=3):
        """Get company description from web search"""
        try:
            # Use DuckDuckGo to get a summary
            encoded_query = quote_plus(f"{company_name} about company")
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            headers = {
                'User-Agent': random.choice(self.config.user_agents)
            }
            
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                snippets = soup.find_all('a', {'class': 'result__snippet'})
                
                if snippets:
                    # Combine the first few snippets for a description
                    return " ".join([s.text for s in snippets[:2]])
            
            return ""
        except Exception as e:
            logger.error(f"Error getting company description: {str(e)}")
            return ""

# Message generation class using Gemini API
class MessageGenerator:
    def __init__(self, config):
        self.config = config
        self.generation_model = genai.GenerativeModel('gemini-2.0-flash')
    
    def summarize_company_data(self, founder_data, company_data):
        """Summarize all the data we have about the founder and company using Gemini"""
        try:
            # Create a comprehensive founder summary with all available data
            founder_summary = {
                'name': founder_data.get('full_name', ''),
                'headline': founder_data.get('headline', ''),
                'summary': founder_data.get('summary', ''),
                'location': founder_data.get('location', ''),
                'primary_company': founder_data.get('primary_company', {}).get('name', ''),
                'primary_title': founder_data.get('primary_company', {}).get('title', '')
            }
            
            # Include education if available
            if 'education' in founder_data and founder_data['education']:
                founder_summary['education'] = [
                    f"{edu.get('degree', '')} from {edu.get('institution', '')}"
                    for edu in founder_data['education']
                ]
            
            # Include all experience details
            if 'experiences' in founder_data and founder_data['experiences']:
                founder_summary['experiences'] = [
                    f"{exp.get('title', '')} at {exp.get('company', '')}" 
                    for exp in founder_data['experiences'][:3]  # Limit to top 3
                ]
            
            company_summary = {
                'name': company_data.get('name', ''),
                'description': company_data.get('description', ''),
                'website': company_data.get('website', '')
            }
            
            # Prepare news summaries
            news_summary = ""
            if company_data.get('news'):
                news_summary = "Recent news:\n"
                for article in company_data['news']:
                    news_summary += f"- {article['title']}\n"

            # New ultra-detailed prompt for Gemini Flash
            prompt = f"""
                **Deep Founder & Company Master Profile Summary for Ultra-Personalized Outreach**

                **Objective:** Using the comprehensive dataset provided, generate an in-depth and data-rich profile that captures every dimension of the founder and their company. The output must be used as the basis for crafting a hyper-personalized LinkedIn outreach message.

                **Input Data:**

                * **Founder Profile Data:** {json.dumps(founder_summary, indent=2)}
                  - Data includes full name, headline, detailed summary, location, educational background, top 3 significant experiences, awards and recognitions, and any unique personal attributes.
                * **Company Data:** {json.dumps(company_summary, indent=2)}
                  - Data includes company name, a full description, website URL, core product/service, industry positioning, competitive advantages, and any quantifiable business achievements.
                * **Supplementary Insights:** {news_summary}
                  - Contains recent news articles and relevant market signals, including social media sentiment and strategic partnerships.

                **Data Points to Emphasize:**
                1. **Founder’s Detailed Biography & Achievements:**
                   - Chronicle the founder’s career journey including key milestones, quantifiable successes (e.g., revenue growth, team leadership, technological breakthroughs), and personal awards.
                   - Highlight educational achievements, pivotal career shifts, and unique personal traits or interests.
                2. **Comprehensive Company Overview:**
                   - Clearly define the company’s core mission, value proposition, and the problem it solves.
                   - Include innovative aspects such as patent-pending technology, disruptive business model, or market positioning that sets it apart.
                   - Integrate any quantifiable metrics (e.g., funding raised, growth rates) and recent notable developments.
                3. **Synergistic Dynamics:**
                   - Identify unique intersections between the founder’s expertise and the company’s strategic direction.
                   - Detect subtle but significant details that would serve as conversation starters, such as niche industry insights or non-obvious achievements.
                4. **Data Enrichment:**
                   - Leverage every data element provided to ensure the summary is rich in context, factual details, and actionable insights.

                **Output Requirements:**
                - The summary must be highly detailed yet remain within a comprehensive 600-word limit.
                - It should be actionable, fact-based, and structured into clear segments explaining the founder’s journey and the company’s value proposition.
                - The tone must be professional, insightful, and tailored for immediately creating a personalized LinkedIn outreach message.

                **Generate the comprehensive, multi-dimensional founder and company profile summary now, ensuring maximum data enrichment for ultra-personalized outreach.**
                """

            response = self.generation_model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Error summarizing company data: {str(e)}")
            return f"Company: {company_data.get('name', '')}\nFounder: {founder_data.get('full_name', '')}"

    def generate_personalized_message(self, founder_data, company_summary):
        """Generate a personalized outreach message using Gemini"""
        try:
            founder_name = founder_data.get('full_name', '').split()[0]  # Get first name
            
            # Extract key details for personalization
            company_name = founder_data.get('primary_company', {}).get('name', '')
            if not company_name and 'experiences' in founder_data and founder_data['experiences']:
                company_name = founder_data['experiences'][0].get('company', '')
                
            # Extract potential conversation hooks
            hooks = []
            if founder_data.get('summary'):
                hooks.append("their company mission")
            
            if 'education' in founder_data and founder_data['education']:
                hooks.append("their educational background")
                
            if 'experiences' in founder_data and len(founder_data['experiences']) > 1:
                hooks.append("their career progression")
                
            hooks_str = ", ".join(hooks) if hooks else "their current work"
            
            prompt = f"""
           **// PROMPT START //**

                    **Persona:** Act as an expert Business Analyst and Market Researcher equipped with web browsing capabilities. Your task is to synthesize complex, multi-source data *combined with targeted live web research* into a comprehensive and insightful dossier about a founder and their company. The goal is to create the richest, most current, factual foundation possible for crafting hyper-personalized strategic communications, specifically LinkedIn outreach.

                    **Objective:** Generate ONE highly detailed, structured, and insightful "Founder & Company Dossier" by deeply analyzing and synthesizing the provided static data sources *AND* augmenting this with findings from live web research (including the official company website). This dossier must serve as the definitive internal reference document for understanding `{founder_name}` and their company, enabling the extraction of unique angles for ultra-personalized outreach.

                    **Input Data Variables (Static Base Data - DO NOT CHANGE THESE):**

                    1.  `founder_summary` (JSON): Contains detailed structured data about the founder.
                        ```json
                        {json.dumps(founder_summary, indent=2)}
                        ```
                    2.  `company_summary` (JSON): Contains detailed structured data about the company, **critically including fields like 'website URL' and 'company name'.**
                        ```json
                        {json.dumps(company_summary, indent=2)}
                        ```
                    3.  `news_summary` (Text): Contains summaries of *potentially* recent news, market signals, social sentiment, and partnerships related to the founder or company (treat as potentially outdated snapshot).
                        ```
                        {news_summary}
                        ```

                    **Core Task: Deep Synthesis Augmented by Live Web Research**

                    1.  **Initial Analysis:** First, thoroughly analyze the static `founder_summary`, `company_summary`, and `news_summary`.
                    2.  **Targeted Web Research (Perform Live):**
                        *   **Company Website:** Extract the 'website URL' from the `company_summary` JSON. **Browse the official company website.** Focus on key sections like 'About Us', 'Products/Services', 'Blog', 'Press/News', 'Careers', and 'Leadership/Team'. Look for mission statements, value propositions, recent announcements, product updates, case studies, and founder quotes/bios not present in the static data.
                        *   **General Web Search:** Perform web searches for:
                            *   Recent news articles about "[Company Name from company_summary]" (beyond what's in `news_summary`).
                            *   Recent interviews, articles, or blog posts by or about `{founder_name}`.
                            *   Verify funding information, key partnerships, or significant recent milestones mentioned in static data or discovered online.
                        *   *(Note: If web browsing fails or yields limited results, rely primarily on the provided static data but indicate where research was attempted.)*
                    3.  **Integrated Synthesis:** Synthesize findings from *both* the static input data *and* your live web research. Connect the dots, identify patterns, quantify achievements (using the most recent data found), and highlight nuances. Prioritize information confirmed by recent live web findings, but note significant discrepancies with the static data if found.

                    **Detailed Synthesis Instructions & Output Structure (Follow Rigorously, Integrating Web Findings):**

                    Generate the dossier using Markdown formatting with the following specific sections:

                    **`## 1. Founder Profile: {founder_name}`**
                        *   **Narrative Arc:** Synthesize the chronological career narrative using `founder_summary`. **Augment with any relevant details or perspectives found in recent interviews/articles from web research.**
                        *   **Quantifiable Achievements:** Extract/list metrics from `founder_summary`. **Update or add new metrics based on verified web research findings.** Infer scale if necessary.
                        *   **Expertise & Skills:** Summarize core expertise using `founder_summary`. **Refine or add context based on how their expertise is presented on the company website or in recent articles.**
                        *   **Unique Attributes:** Note traits/interests from `founder_summary`. **Add any publicly stated philosophies, recent quotes, or relevant personal updates found online.**
                        *   **Recent Signals:** Integrate relevant points from `news_summary` and **prioritize/supplement with more current findings from web searches about the founder.**

                    **`## 2. Company Profile: [Company Name from company_summary]`**
                        *   **Core Identity:** Articulate mission/vision/problem solved using `company_summary`. **Refine using the 'About Us' or mission statement directly from the browsed company website for the most current articulation.**
                        *   **Value Proposition & USP:** Detail product/service and USPs from `company_summary`. **Enhance with specific feature details, current product descriptions, or case study examples found on the website.** Note any evolution found online.
                        *   **Market Context:** Describe industry positioning using `company_summary`. **Add any new competitors identified or market context updates discovered via web research.**
                        *   **Traction & Milestones:** List achievements from `company_summary` and `news_summary`. **Verify and update with the latest funding rounds, partnerships, user numbers, or significant milestones announced on the company website's news/press section or found in recent reputable web sources.**
                        *   **Recent Developments:** Summarize key events from `news_summary`. **Replace or significantly augment with the most recent announcements, product launches, strategic shifts, or market sentiment gathered directly from the company website and web searches.**

                    **`## 3. Key Synergies & Strategic Insights`**
                        *   **Founder-Company Alignment:** Identify connections between the founder (Section 1, including web findings) and the company (Section 2, including web findings). **Focus on how recently discovered founder activities/statements align with current company direction found online.**
                        *   **Non-Obvious Observations:** Highlight subtle points derived from synthesizing *across all data sources (static + live web)*. **Look for discrepancies between older static data and newer web findings, potential pivots, or newly emphasized strategic themes.**
                        *   **Data Consistency & Recency Check:** Explicitly comment on the consistency between the static inputs and live web findings. Note key areas where web research provided significant updates or clarifications.

                    **`## 4. Potential Outreach Angles (Actionable Hooks - Based on Latest Info)`**
                        *   **Extract 3-5 Specific & Unique Hooks:** Based *primarily on the most current and insightful findings* from Sections 1, 2, and 3 (giving weight to web research findings), list distinct, non-generic conversation starters.
                            *   *Example Hook 1:* Recent blog post/announcement on the company website regarding [Specific Topic] and its connection to [Founder's Expertise].
                            *   *Example Hook 2:* A specific challenge/opportunity mentioned in a recent interview with `{founder_name}` found online.
                            *   *Example Hook 3:* The evolution of [Company Product/Service] as seen on the website compared to older descriptions, perhaps asking about the driving force.
                            *   *Example Hook 4:* A newly announced partnership/milestone and its implications for the company's mission.

                    **Quality & Formatting Requirements:**

                    *   **Depth & Recency:** Be comprehensive. Integrate information seamlessly from static inputs *and* live web research. Prioritize accuracy and recency.
                    *   **Conciseness:** Adhere strictly to a maximum **~600-word limit** (allow slight flexibility if crucial new web data warrants it, but remain focused). Use bullet points.
                    *   **Objectivity & Sourcing:** Base the summary on evidence. Briefly note if information comes specifically from recent web findings vs. static data where relevant (e.g., "Website states...", "Recent interview mentioned...").
                    *   **Structure:** Use the exact Markdown section headers provided.
                    *   **Actionability:** Ensure Section 4 provides concrete, current, specific hooks.
                    *   **Tone:** Maintain a professional, analytical, objective tone (Sections 1-3). Section 4 frames engagement points.

                    **Generate the comprehensive, research-augmented Founder & Company Dossier now, synthesizing the provided static data (`founder_summary`, `company_summary`, `news_summary`) AND incorporating findings from live web research according to all instructions.**

                    **// PROMPT END //**
            """
            
            response = self.generation_model.generate_content(prompt)
            message = response.text
            
            # Check character limit for LinkedIn first messages (500)
            if len(message) > 500:
                prompt = f"""
                The previous message was too long ({len(message)} chars). 
                Please rewrite it to be under 500 characters while keeping it personalized,
                mentioning something specific about {founder_name}'s work at {company_name}.
                """
                response = self.generation_model.generate_content(prompt)
                message = response.text
                
            return message
            
        except Exception as e:
            logger.error(f"Error generating personalized message: {str(e)}")
            return f"Hi {founder_data.get('full_name', '').split()[0]}, I'm an ML/AI engineer and noticed your work at {company_name or 'your company'}. Would love to connect and learn more about what you're building."

# Database operations class
class DatabaseOps:
    def __init__(self):
        self.db_path = 'linkedin_outreach.db'
    
    def save_founder_data(self, founder_data, profile_url):
        """Save founder data to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert founder data
            cursor.execute('''
            INSERT OR REPLACE INTO founders 
            (linkedin_url, full_name, headline, summary, location, processed_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                profile_url,
                founder_data.get('full_name', ''),
                founder_data.get('headline', ''),
                founder_data.get('summary', ''),
                founder_data.get('location', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            founder_id = cursor.lastrowid
            conn.commit()
            return founder_id
            
        except Exception as e:
            logger.error(f"Error saving founder data: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def save_company_data(self, founder_id, company_data):
        """Save company data to the database"""
        if not founder_id:
            return None
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert company data
            cursor.execute('''
            INSERT INTO companies
            (founder_id, name, description, website)
            VALUES (?, ?, ?, ?)
            ''', (
                founder_id,
                company_data.get('name', ''),
                company_data.get('description', ''),
                company_data.get('website', '')
            ))
            
            company_id = cursor.lastrowid
            conn.commit()
            return company_id
            
        except Exception as e:
            logger.error(f"Error saving company data: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def save_message(self, founder_id, message_text):
        """Save generated message to the database"""
        if not founder_id:
            return None
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert message
            cursor.execute('''
            INSERT INTO messages
            (founder_id, message_text, generated_date)
            VALUES (?, ?, ?)
            ''', (
                founder_id,
                message_text,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            message_id = cursor.lastrowid
            conn.commit()
            return message_id
            
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_all_messages(self):
        """Get all generated messages with founder information"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            SELECT f.full_name, f.linkedin_url, c.name as company_name, 
                   m.message_text, m.generated_date, m.was_sent
            FROM messages m
            JOIN founders f ON m.founder_id = f.id
            LEFT JOIN companies c ON f.id = c.founder_id
            ORDER BY m.generated_date DESC
            ''')
            
            results = [dict(row) for row in cursor.fetchall()]
            return results
            
        except Exception as e:
            logger.error(f"Error getting messages: {str(e)}")
            return []
        finally:
            conn.close()
    
    def export_messages_to_csv(self, filename='linkedin_messages.csv'):
        """Export all generated messages to CSV file"""
        messages = self.get_all_messages()
        
        if not messages:
            logger.warning("No messages to export")
            return False
            
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['full_name', 'company_name', 'linkedin_url', 
                             'message_text', 'generated_date', 'was_sent']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for message in messages:
                    writer.writerow(message)
                    
            logger.info(f"Successfully exported messages to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting messages to CSV: {str(e)}")
            return False

# Main pipeline class
class LinkedInOutreachPipeline:
    def __init__(self):
        # Initialize database
        init_database()
        
        # Load configuration
        self.config = Config()
        
        # Initialize components
        self.scraper = LinkedInScraper(self.config)
        self.researcher = CompanyResearcher(self.config)
        self.generator = MessageGenerator(self.config)
        self.db = DatabaseOps()
    
    def process_single_profile_with_scraper(self, profile_url, scraper_instance):
        """Process a single LinkedIn profile using a provided scraper instance."""
        try:
            # Extract LinkedIn profile data using the provided scraper instance
            founder_data = scraper_instance.extract_profile_data(profile_url)
            if not founder_data:
                logger.error("Failed to extract profile data")
                return None
            
            # Step 3: Extract company information with improved detection
            company_name = None
            company_title = None
            company_description = None
            
            # Check for founder positions in experience section
            if 'experiences' in founder_data and founder_data['experiences']:
                # Look for founder/CEO positions first - expanded list of keywords
                founder_positions = [
                    'founder', 'co-founder', 'cofounder', 'ceo', 'chief executive', 
                    'owner', 'president', 'managing director', 'director', 
                    'entrepreneur', 'proprietor'
                ]
                
                for exp in founder_data['experiences']:
                    title = exp.get('title', '').lower()
                    if any(position.lower() in title for position in founder_positions):
                        company_name = exp.get('company')
                        company_title = exp.get('title')
                        company_description = exp.get('description', '')
                        logger.info(f"Found founder position: {company_title} at {company_name}")
                        break
                        
                # If no founder position found, use the most recent company
                if not company_name and founder_data['experiences']:
                    company_name = founder_data['experiences'][0].get('company')
                    company_title = founder_data['experiences'][0].get('title')
                    company_description = founder_data['experiences'][0].get('description', '')
                    logger.info(f"Using most recent position: {company_title} at {company_name}")
            
            # Try to extract from headline if experiences not available
            if not company_name:
                headline = founder_data.get('headline', '')
                
                # Pattern matching for common headline formats
                company_patterns = [
                    r"(?:CEO|Founder|Co-Founder|Owner|Director)(?:\s+\&\s+)?(?:\w+\s+)?(?:at|of|@)\s+([^|,]+)",
                    r"(?:at|@)\s+([^|,]+)",
                    r"\|\s+([^|,]+)"
                ]
                
                for pattern in company_patterns:
                    match = re.search(pattern, headline, re.IGNORECASE)
                    if match:
                        company_name = match.group(1).strip()
                        logger.info(f"Extracted company from headline: {company_name}")
                        break
            
            # If still no company, check if company name appears in the summary
            if not company_name and founder_data.get('summary'):
                summary = founder_data.get('summary', '')
                company_patterns = [
                    r"(?:founded|started|co-founded|launched|created)\s+([A-Z][a-zA-Z0-9\s]+)(?:\.|,|\s+in)",
                    r"(?:CEO|Founder|Co-Founder|Owner) of\s+([A-Z][a-zA-Z0-9\s]+)(?:\.|,|\s+)"
                ]
                
                for pattern in company_patterns:
                    match = re.search(pattern, summary)
                    if match:
                        company_name = match.group(1).strip()
                        logger.info(f"Extracted company from summary: {company_name}")
                        break
            
            if not company_name:
                logger.warning("Could not identify company name")
                company_name = "their company"  # Better fallback than "Unknown Company"
            
            # Enhanced founder data with more details
            enhanced_founder_data = founder_data.copy()
            
            # Add more context based on available data
            if 'summary' not in enhanced_founder_data or not enhanced_founder_data['summary']:
                enhanced_founder_data['summary'] = "No summary available"
            
            # Add company context
            enhanced_founder_data['primary_company'] = {
                'name': company_name,
                'title': company_title,
                'description': company_description
            }
            
            # Step 4: Research company
            company_data = self.researcher.search_company_info(company_name)
            
            # Step 5: Save founder data to database
            founder_id = self.db.save_founder_data(enhanced_founder_data, profile_url)
            
            # Step 6: Save company data to database
            company_data['title'] = company_title  # Add title to company data
            self.db.save_company_data(founder_id, company_data)
            
            # Step 7: Summarize all data with enhanced information
            company_summary = self.generator.summarize_company_data(enhanced_founder_data, company_data)
            
            # Step 8: Generate personalized message with more context
            personalized_message = self.generator.generate_personalized_message(enhanced_founder_data, company_summary)
            
            # Step 9: Save message to database
            message_id = self.db.save_message(founder_id, personalized_message)
            
            # Step 10: Return the results
            return {
                'founder': enhanced_founder_data,
                'company': company_data,
                'summary': company_summary,
                'message': personalized_message
            }

        except Exception as e:
            logger.error(f"Error in pipeline: {str(e)}")
            return None
    
    def process_batch_from_csv(self, csv_file):
        """Process multiple LinkedIn profiles from a CSV file"""
        try:
            profiles = []
            # Read LinkedIn profile URLs from CSV
            with open(csv_file, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if 'linkedin_url' in row:
                        profiles.append(row['linkedin_url'])
                    elif 'url' in row:
                        profiles.append(row['url'])
            
            if not profiles:
                logger.error("No LinkedIn profile URLs found in CSV file")
                return False
                
            # Process each profile
            results = []
            for profile in profiles:
                logger.info(f"Processing profile: {profile}")
                result = self.process_single_profile_with_scraper(profile, self.scraper)
                if result:
                    results.append(result)
                time.sleep(random.uniform(5, 10))  # Random delay between profiles
            
            # Export all messages to CSV
            self.db.export_messages_to_csv()
            
            return len(results) > 0
            
        except Exception as e:
            logger.error(f"Error processing batch from CSV: {str(e)}")
            return False
        finally:
            # We don't close the scraper here as it might be reused in the app
            pass
    
    def cleanup(self):
        """Clean up resources"""
        self.scraper.close()

# Initialize database at module level for app access
init_database()