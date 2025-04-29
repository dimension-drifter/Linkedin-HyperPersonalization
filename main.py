import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.getcwd(), '.env')
load_dotenv(dotenv_path=dotenv_path, verbose=True) # verbose=True adds more output
import requests
import json
import time
import re
import csv
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError # Import Playwright errors
import google.generativeai as genai
import logging
import sqlite3
import random
from urllib.parse import quote_plus
from linkedin_auth import LinkedInAuth # Keep this import
from message_generator import MessageGenerator # <-- ADD THIS IMPORT

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

        # LinkedIn credentials (for playwright scraping approach)
        self.linkedin_email = os.getenv("LINKEDIN_EMAIL")
        self.linkedin_password = os.getenv("LINKEDIN_PASSWORD")

        # Configure Gemini
        genai.configure(api_key=self.gemini_api_key)

        # User agent for requests and Playwright
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
            # Add more diverse and recent user agents
        ]

# LinkedIn data extraction class using Playwright
class LinkedInScraper:
    def __init__(self, config):
        self.config = config
        # Create LinkedIn auth instance (manages Playwright session)
        self.linkedin_auth = LinkedInAuth(
            email=config.linkedin_email,
            password=config.linkedin_password,
            user_agents=config.user_agents
        )
        self.page = None # Initialize page as None

    def _ensure_page(self):
        """Ensures the Playwright page is initialized and ready."""
        if self.page is None or self.page.is_closed():
            logger.info("Playwright page not initialized or closed. Getting page from auth module.")
            # Get the persistent page from LinkedInAuth
            # Set headless=False for debugging if needed
            self.page = self.linkedin_auth.get_page(headless=True)
            if self.page is None or self.page.is_closed():
                 raise RuntimeError("Failed to obtain a valid Playwright page.")
        return self.page

    def login_to_linkedin(self):
        """Login to LinkedIn using the auth module (which uses Playwright)."""
        try:
            self._ensure_page() # Make sure page exists
            return self.linkedin_auth.ensure_logged_in()
        except Exception as e:
            logger.error(f"Error during LinkedIn login process: {e}")
            return False

    def extract_profile_data(self, profile_url):
        """Extract data from a LinkedIn profile using Playwright."""
        logger.info(f"Extracting data from LinkedIn profile: {profile_url}")
        try:
            page = self._ensure_page() # Get the active page
        except RuntimeError as e:
             logger.error(f"Cannot extract profile data: {e}")
             return None

        max_retries = 3
        retry_delay = 5 # Longer initial delay for Playwright navigation

        for attempt in range(max_retries):
            try:
                logger.info(f"Navigating to profile URL (Attempt {attempt + 1}/{max_retries})...")
                # Use wait_until='domcontentloaded' or 'load' or 'networkidle'
                page.goto(profile_url, timeout=60000, wait_until="domcontentloaded")
                # Add a small wait after navigation for stability
                time.sleep(random.uniform(3, 6))
                logger.info("Navigation successful.")

                # Check if we landed on the correct profile page or got redirected/blocked
                current_url = page.url
                if "authwall" in current_url:
                    logger.error("Hit LinkedIn Authwall. Cannot scrape profile. Session might be invalid.")
                    # Try to re-validate session
                    if not self.verify_session():
                         logger.error("Session re-validation failed.")
                         # Optionally try a full re-login here if critical
                         # if self.login_to_linkedin():
                         #    page.goto(profile_url, timeout=60000, wait_until="domcontentloaded") # Retry nav
                         # else: return None
                         return None # Give up if re-validation fails
                    else: # If session is now valid, retry navigation
                         logger.info("Session re-validated. Retrying navigation...")
                         continue # Go to next attempt loop

                if "/in/" not in current_url and profile_url.split('?')[0] not in current_url:
                     logger.warning(f"Potential redirect detected. Expected profile, got: {current_url}")
                     # Could be a valid but different profile URL (e.g., public view)
                     # Or could be an error page. Add checks if needed.

                # Basic check for profile content existence
                try:
                    page.wait_for_selector("h1", timeout=10000) # Wait for the main name header
                except PlaywrightTimeoutError:
                    logger.warning("Profile content (h1) not found quickly. Page might be empty or blocked.")
                    # Consider retrying navigation or failing
                    if attempt < max_retries - 1:
                        logger.info("Retrying navigation due to missing content...")
                        time.sleep(retry_delay)
                        retry_delay += 3
                        continue
                    else:
                        logger.error("Failed to find profile content after retries.")
                        return None

                break # Exit retry loop if navigation and basic check succeed

            except PlaywrightTimeoutError as e:
                logger.warning(f"Timeout navigating to profile (Attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5 # Exponential backoff
                else:
                    logger.error(f"Failed to load profile after {max_retries} attempts due to timeout.")
                    return None
            except PlaywrightError as e:
                 logger.error(f"Playwright error during navigation (Attempt {attempt + 1}/{max_retries}): {e}")
                 if attempt < max_retries - 1:
                     time.sleep(retry_delay)
                     retry_delay += 3
                 else:
                     logger.error(f"Failed to load profile after {max_retries} attempts due to Playwright error.")
                     return None
            except Exception as e:
                 logger.error(f"Unexpected error during navigation (Attempt {attempt + 1}/{max_retries}): {e}")
                 # Stop retrying on unexpected errors
                 return None

        try:
            logger.info("Scrolling profile page to load dynamic content...")
            self._scroll_profile_page(page)

            # --- Data Extraction using Playwright Locators ---
            profile_data = {}

            # Helper function to safely get text content
            def get_text(locator):
                try:
                    return locator.text_content(timeout=5000).strip()
                except (PlaywrightTimeoutError, PlaywrightError, AttributeError):
                    return ""
                except Exception as e:
                    logger.debug(f"Minor error getting text: {e}")
                    return ""

            # Get full name - Try multiple selectors
            name_selectors = [
                "h1.text-heading-xlarge",
                "h1.inline.t-24.t-black.t-normal.break-words",
                "h1.text-heading-xlarge.inline.t-24.t-black.t-normal.break-words",
                "h1.pv-text-details__left-panel--name",
                ".pv-top-card-section__name", # Older selector
                "section.pv-top-card h1" # General top card h1
            ]
            name_found = False
            for selector in name_selectors:
                locator = page.locator(selector).first # Use first() in case multiple match
                if locator.is_visible(timeout=1000): # Quick check for visibility
                    profile_data['full_name'] = get_text(locator)
                    if profile_data['full_name']:
                        logger.info(f"Found name using selector: {selector}")
                        name_found = True
                        break
            if not name_found:
                 logger.warning("Could not find name element using primary selectors.")
                 profile_data['full_name'] = "Unknown"


            # Get headline
            headline_selectors = [
                "div.text-body-medium.break-words", # Common selector
                ".pv-top-card-section__headline", # Older selector
                "div.pv-text-details__left-panel--headline", # Another possibility
                "section.pv-top-card div.text-body-medium"
            ]
            headline_found = False
            for selector in headline_selectors:
                 locator = page.locator(selector).first
                 if locator.is_visible(timeout=1000):
                     profile_data['headline'] = get_text(locator)
                     if profile_data['headline']:
                         headline_found = True
                         break
            if not headline_found: profile_data['headline'] = ""


            # Get location
            location_selectors = [
                "span.text-body-small.inline.t-black--light.break-words", # Common
                ".pv-top-card-section__location", # Older
                "span.pv-text-details__left-panel--location",
                "section.pv-top-card span.text-body-small"
            ]
            location_found = False
            for selector in location_selectors:
                 locator = page.locator(selector).first
                 if locator.is_visible(timeout=1000):
                     profile_data['location'] = get_text(locator)
                     # Simple validation: location usually contains a comma or country name
                     if profile_data['location'] and (',' in profile_data['location'] or len(profile_data['location']) > 3):
                         location_found = True
                         break
            if not location_found: profile_data['location'] = ""


            # Get summary/about
            profile_data['summary'] = ""
            try:
                # Find the "About" section first
                about_section_locator = page.locator("section:has(h2:text-is('About'))", has_text="About").first
                if about_section_locator.is_visible(timeout=5000):
                    # Try to click "see more" within the about section
                    see_more_button = about_section_locator.locator("button:has-text('see more')")
                    if see_more_button.is_visible(timeout=1000):
                        try:
                            see_more_button.click(timeout=5000)
                            time.sleep(0.5) # Wait for expansion
                            logger.info("Clicked 'see more' in About section.")
                        except (PlaywrightTimeoutError, PlaywrightError) as e:
                            logger.warning(f"Could not click 'see more' in About: {e}")

                    # Extract text from the main content area of the about section
                    # This selector might need adjustment based on LinkedIn's structure
                    about_text_locator = about_section_locator.locator("div.display-flex.ph5 > .inline-show-more-text > span[aria-hidden='true'], div.pv-shared-text-with-see-more > div > span").first
                    profile_data['summary'] = get_text(about_text_locator)
                    if not profile_data['summary']: # Fallback if specific span not found
                         profile_data['summary'] = get_text(about_section_locator) # Get all text in section
                         # Clean up the summary if needed (remove "About", "see more", etc.)
                         profile_data['summary'] = profile_data['summary'].replace("About\n", "").replace("\nsee more", "").strip()

                else:
                     logger.info("About section not found.")

            except (PlaywrightTimeoutError, PlaywrightError) as e:
                logger.warning(f"Error extracting About section: {e}")
            except Exception as e:
                 logger.warning(f"Unexpected error extracting About section: {e}")


            # Get experience section
            profile_data['experiences'] = []
            try:
                logger.info("Extracting Experience section...")
                # Locate the experience section container
                # Use :has() pseudo-class for robustness
                experience_section_locator = page.locator("section:has(h2:text-is('Experience'))", has_text="Experience").first

                if experience_section_locator.is_visible(timeout=10000):
                    # Find individual experience items within the section
                    # Common structure: ul > li containing experience details
                    experience_items = experience_section_locator.locator("ul > li.pvs-list__paged-list-item, ul > li.artdeco-list__item") # Adjust if structure changes

                    item_count = experience_items.count()
                    logger.info(f"Found {item_count} potential experience items.")

                    for i in range(item_count):
                        item = experience_items.nth(i)
                        experience = {}

                        # Extract Title (often the most prominent text)
                        # Look for spans with specific classes or the first strong/bold text
                        title_locator = item.locator("span.mr1.t-bold > span[aria-hidden='true'], span.t-bold > span[aria-hidden='true'], h3 > span[aria-hidden='true']").first
                        experience['title'] = get_text(title_locator)

                        # Extract Company Name (often follows title or is linked)
                        # Look for secondary text, often with 't-normal' or linked
                        company_locator = item.locator("span.t-14.t-normal > span[aria-hidden='true'], p.pv-entity__secondary-title > span[aria-hidden='true']").first
                        experience['company'] = get_text(company_locator)

                        # If company name is missing, sometimes it's part of a multi-role entry
                        if not experience['company'] and experience['title']:
                             # Check if the title contains " at " or similar separator
                             if " at " in experience['title']:
                                 parts = experience['title'].split(" at ", 1)
                                 experience['title'] = parts[0].strip()
                                 experience['company'] = parts[1].strip()

                        # Extract Description (if available)
                        desc_locator = item.locator("div.inline-show-more-text > span[aria-hidden='true'], div.pv-entity__description > span[aria-hidden='true']").first
                        experience['description'] = get_text(desc_locator)
                        # Click 'see more' for description if present
                        desc_see_more = item.locator("button.inline-show-more-text__button:has-text('see more')")
                        if desc_see_more.is_visible(timeout=500):
                            try:
                                desc_see_more.click(timeout=3000)
                                time.sleep(0.3)
                                experience['description'] = get_text(desc_locator) # Re-extract after click
                            except (PlaywrightTimeoutError, PlaywrightError): pass # Ignore if click fails


                        # Extract Company LinkedIn URL (if linked)
                        company_link_locator = item.locator("a[href*='/company/']").first
                        experience['company_linkedin_url'] = ""
                        if company_link_locator.is_visible(timeout=500):
                            try:
                                href = company_link_locator.get_attribute('href', timeout=1000)
                                if href: experience['company_linkedin_url'] = "https://www.linkedin.com" + href.split('?')[0] # Clean URL
                            except (PlaywrightTimeoutError, PlaywrightError): pass


                        # Only add if we have a title or company
                        if experience.get('title') or experience.get('company'):
                            profile_data['experiences'].append(experience)
                            # logger.debug(f"Extracted Experience: {experience}")
                        else:
                             logger.debug(f"Skipping empty experience item {i}.")

                else:
                    logger.warning("Experience section not found or not visible.")

            except (PlaywrightTimeoutError, PlaywrightError) as e:
                logger.warning(f"Error processing Experience section: {e}")
            except Exception as e:
                 logger.warning(f"Unexpected error processing Experience section: {e}")


            # Get education section (similar logic to experience)
            profile_data['education'] = []
            try:
                logger.info("Extracting Education section...")
                education_section_locator = page.locator("section:has(h2:text-is('Education'))", has_text="Education").first

                if education_section_locator.is_visible(timeout=5000):
                    education_items = education_section_locator.locator("ul > li.pvs-list__paged-list-item, ul > li.artdeco-list__item")
                    item_count = education_items.count()
                    logger.info(f"Found {item_count} potential education items.")

                    for i in range(item_count):
                        item = education_items.nth(i)
                        education = {}

                        # Institution Name
                        inst_locator = item.locator("span.mr1.t-bold > span[aria-hidden='true'], span.t-bold > span[aria-hidden='true'], h3 > span[aria-hidden='true']").first
                        education['institution'] = get_text(inst_locator)

                        # Degree/Field of Study
                        degree_locator = item.locator("span.t-14.t-normal > span[aria-hidden='true'], p > span[aria-hidden='true']").first # Check structure
                        education['degree'] = get_text(degree_locator)

                        if education.get('institution'):
                            profile_data['education'].append(education)
                            # logger.debug(f"Extracted Education: {education}")
                        else:
                             logger.debug(f"Skipping empty education item {i}.")
                else:
                    logger.warning("Education section not found or not visible.")

            except (PlaywrightTimeoutError, PlaywrightError) as e:
                logger.warning(f"Error processing Education section: {e}")
            except Exception as e:
                 logger.warning(f"Unexpected error processing Education section: {e}")


            logger.info(f"Finished extracting data for {profile_data.get('full_name', profile_url)}")
            return profile_data

        except Exception as e:
            logger.error(f"Critical error during Playwright profile data extraction: {str(e)}")
            # Capture screenshot on critical failure for debugging
            try:
                 if page and not page.is_closed():
                     screenshot_path = f"error_screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
                     page.screenshot(path=screenshot_path, full_page=True)
                     logger.info(f"Error screenshot saved to: {screenshot_path}")
            except Exception as se:
                 logger.error(f"Could not save error screenshot: {se}")
            return None

    def _scroll_profile_page(self, page):
        """Helper method to scroll through the profile page using Playwright."""
        logger.debug("Scrolling page...")
        try:
            total_height = page.evaluate("document.body.scrollHeight")
            scroll_increment = 700 # Pixels to scroll each time
            current_scroll = 0
            max_scrolls = 20 # Safety limit
            scroll_count = 0

            while current_scroll < total_height and scroll_count < max_scrolls:
                current_scroll += scroll_increment
                page.evaluate(f"window.scrollTo(0, {current_scroll});")
                time.sleep(random.uniform(0.6, 1.2)) # Wait for content load
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == total_height: # Stop if height doesn't change
                    # Scroll a bit more just in case
                    page.evaluate(f"window.scrollTo(0, {new_height});")
                    time.sleep(0.5)
                    break
                total_height = new_height
                scroll_count += 1

            # Scroll back to top
            page.evaluate("window.scrollTo(0, 0);")
            time.sleep(0.5)
            logger.debug(f"Scrolling complete after {scroll_count} scrolls.")
        except (PlaywrightError, PlaywrightTimeoutError) as e:
            logger.warning(f"Error during page scrolling: {str(e)}")
        except Exception as e:
             logger.warning(f"Unexpected error during page scrolling: {str(e)}")

    def close(self):
        """Close the Playwright browser via the auth module."""
        logger.info("Closing LinkedInScraper and associated Playwright resources.")
        self.linkedin_auth.close()
        self.page = None # Reset page state

    def verify_session(self):
        """Verify LinkedIn session using the auth module."""
        try:
            # Ensure page exists before verifying. If it doesn't, verification will fail.
            self._ensure_page()
            return self.linkedin_auth.verify_session()
        except Exception as e:
            logger.error(f"Error ensuring page for session verification: {e}")
            return False

# Company research class using free APIs
class CompanyResearcher:
    def __init__(self, config):
        self.config = config
    
    def search_company_info(self, company_name):
        """Search for company information using free APIs and web scraping"""
        logger.info(f"Researching company: {company_name}")
        company_info = {
            'name': company_name,
            'website': self._find_company_website(company_name),
            'news': self._get_news_articles(company_name),
            'description': self._get_company_description(company_name)
        }
        return company_info
    
    def _find_company_website(self, company_name):
        """Find company website using DuckDuckGo search"""
        try:
            # Encode company name for URL
            encoded_query = quote_plus(f"{company_name} official website")
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            headers = {
                'User-Agent': random.choice(self.config.user_agents)
            }
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                results = soup.find_all('a', {'class': 'result__url'})
                
                # Filter out common non-company websites
                excluded_domains = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com', 
                                   'crunchbase.com', 'bloomberg.com', 'wikipedia.org']
                
                for result in results:
                    link = result.get('href', '')
                    # Check if this is likely the company website (not social media, etc)
                    if not any(domain in link for domain in excluded_domains):
                        return link
            
            return ""
        except Exception as e:
            logger.error(f"Error finding company website: {str(e)}")
            return ""
    
    def _get_news_articles(self, company_name):
        """Get news articles about the company using free News API"""
        try:
            # Using GDELT's free news search via Webhose
            encoded_query = quote_plus(company_name)
            url = f"https://webhose.io/filterWebContent?token=demo&format=json&sort=relevancy&q={encoded_query}"
            
            headers = {
                'User-Agent': random.choice(self.config.user_agents)
            }
            
            response = requests.get(url, headers=headers)
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
    
    def _get_company_description(self, company_name):
        """Get company description from web search"""
        try:
            # Use DuckDuckGo to get a summary
            encoded_query = quote_plus(f"{company_name} about company")
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            headers = {
                'User-Agent': random.choice(self.config.user_agents)
            }
            
            response = requests.get(url, headers=headers)
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

# Database operations class
class DatabaseOps:
    def __init__(self):
        self.db_path = 'linkedin_outreach.db'
        # Ensure connection/cursor are handled per method or managed carefully

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Return rows as dict-like objects
        return conn

    def save_founder_data(self, founder_data, profile_url):
        """Save founder data to the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT OR REPLACE INTO founders
            (linkedin_url, full_name, headline, summary, location, processed_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                profile_url,
                founder_data.get('full_name', ''),
                founder_data.get('headline', ''),
                # Ensure summary is stored correctly, might be long
                founder_data.get('summary', '')[:10000], # Truncate if necessary
                founder_data.get('location', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            founder_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Saved founder data for ID: {founder_id}")
            return founder_id
        except sqlite3.Error as e:
            logger.error(f"Database error saving founder data: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def save_company_data(self, founder_id, company_data):
        """Save company data to the database"""
        if not founder_id: return None
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Check if company exists for this founder
            cursor.execute("SELECT id FROM companies WHERE founder_id = ?", (founder_id,))
            existing = cursor.fetchone()
            
            if existing:
                # If exists, update
                cursor.execute('''
                UPDATE companies
                SET name = ?, title = ?, description = ?, website = ?
                WHERE founder_id = ?
                ''', (
                    company_data.get('name', ''),
                    company_data.get('title', ''),
                    company_data.get('description', '')[:5000],
                    company_data.get('website', ''),
                    founder_id
                ))
                company_id = existing['id']
            else:
                # If not, insert new
                cursor.execute('''
                INSERT INTO companies
                (founder_id, name, title, description, website)
                VALUES (?, ?, ?, ?, ?)
                ''', (
                    founder_id,
                    company_data.get('name', ''),
                    company_data.get('title', ''),
                    company_data.get('description', '')[:5000],
                    company_data.get('website', '')
                ))
                company_id = cursor.lastrowid
                
            conn.commit()
            logger.info(f"Saved/Updated company data for founder ID: {founder_id}")
            return company_id
        except sqlite3.Error as e:
            logger.error(f"Database error saving company data: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def save_message(self, founder_id, message_text):
        """Save generated message to the database"""
        if not founder_id: return None
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO messages
            (founder_id, message_text, generated_date, was_sent)
            VALUES (?, ?, ?, 0)
            ''', (
                founder_id,
                message_text,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            message_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Saved message ID: {message_id} for founder ID: {founder_id}")
            return message_id
        except sqlite3.Error as e:
            logger.error(f"Database error saving message: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_all_messages(self):
        """Get all generated messages with founder and company information"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Ensure the JOIN logic correctly links messages, founders, and their primary company
            cursor.execute('''
            SELECT
                m.id as message_id, -- Alias message ID clearly
                f.full_name,
                f.linkedin_url,
                COALESCE(c.name, 'N/A') as company_name, -- Handle cases where company might be missing
                m.message_text,
                m.generated_date,
                m.was_sent
            FROM messages m
            JOIN founders f ON m.founder_id = f.id
            LEFT JOIN companies c ON f.id = c.founder_id -- Use LEFT JOIN in case company data is absent
            ORDER BY m.generated_date DESC
            ''')
            results = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Retrieved {len(results)} messages from database.")
            return results
        except sqlite3.Error as e:
            logger.error(f"Database error getting all messages: {str(e)}")
            return []
        finally:
            conn.close()

    def mark_message_as_sent(self, message_id):
        """Mark a message as sent in the database"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE messages SET was_sent = 1 WHERE id = ?", (message_id,))
            updated_rows = cursor.rowcount
            conn.commit()
            if updated_rows > 0:
                logger.info(f"Marked message ID {message_id} as sent.")
                return True
            else:
                logger.warning(f"Message ID {message_id} not found for marking as sent.")
                return False
        except sqlite3.Error as e:
            logger.error(f"Database error marking message as sent: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_messages_by_linkedin_url(self, linkedin_url):
        """Get messages for a specific LinkedIn URL"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT m.id, m.message_text, m.generated_date, m.was_sent
            FROM messages m
            JOIN founders f ON m.founder_id = f.id
            WHERE f.linkedin_url = ?
            ORDER BY m.generated_date DESC
            ''', (linkedin_url,))
            results = cursor.fetchall() # Returns list of Row objects
            logger.info(f"Found {len(results)} messages for URL: {linkedin_url}")
            # Convert Row objects to standard tuples or dicts if needed by caller
            return [tuple(row) for row in results] # Example: return list of tuples
        except sqlite3.Error as e:
            logger.error(f"Database error getting messages by URL: {str(e)}")
            return []
        finally:
            conn.close()

    # Add export_messages_to_csv and delete_profile if they are not already in the class
    def export_messages_to_csv(self, filename='linkedin_messages.csv'):
        """Export all generated messages to CSV file"""
        messages = self.get_all_messages() # This now returns dicts with 'message_id'

        if not messages:
            logger.warning("No messages to export")
            return False

        try:
            # Adjust fieldnames based on the keys returned by get_all_messages
            fieldnames = ['message_id', 'full_name', 'company_name', 'linkedin_url',
                          'message_text', 'generated_date', 'was_sent']
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore') # Ignore extra fields if any
                writer.writeheader()
                for message_dict in messages:
                     # Ensure boolean 'was_sent' is handled correctly for CSV
                     message_dict['was_sent'] = bool(message_dict.get('was_sent', 0))
                     writer.writerow(message_dict)

            logger.info(f"Successfully exported {len(messages)} messages to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error exporting messages to CSV: {str(e)}")
            return False

    def delete_profile(self, message_id):
        """Delete a profile and its associated message(s) from the database"""
        # This logic seems okay, ensure it handles potential errors gracefully
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT founder_id FROM messages WHERE id = ?", (message_id,))
            result = cursor.fetchone()
            if not result:
                logger.warning(f"Message ID {message_id} not found for deletion.")
                return False
            founder_id = result['founder_id']

            # Start transaction
            conn.execute("BEGIN TRANSACTION;")

            # Delete the specific message
            cursor.execute("DELETE FROM messages WHERE id = ?", (message_id,))
            logger.info(f"Deleted message ID {message_id}.")

            # Check if other messages exist for this founder
            cursor.execute("SELECT COUNT(*) FROM messages WHERE founder_id = ?", (founder_id,))
            count_result = cursor.fetchone()
            remaining_messages = count_result[0] if count_result else 0

            # If no messages remain, delete founder and company data
            if remaining_messages == 0:
                logger.info(f"No remaining messages for founder ID {founder_id}. Deleting founder and company data.")
                cursor.execute("DELETE FROM companies WHERE founder_id = ?", (founder_id,))
                cursor.execute("DELETE FROM founders WHERE id = ?", (founder_id,))
            else:
                 logger.info(f"{remaining_messages} messages still exist for founder ID {founder_id}.")

            conn.commit()
            logger.info(f"Deletion process completed for message ID {message_id}.")
            return True

        except sqlite3.Error as e:
            logger.error(f"Database error deleting profile data for message ID {message_id}: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

# Main pipeline class
class LinkedInOutreachPipeline:
    def __init__(self, scraper, researcher, generator, db_ops):
        """
        Initializes the pipeline with pre-configured components.

        Args:
            scraper: An instance of LinkedInScraper.
            researcher: An instance of CompanyResearcher.
            generator: An instance of MessageGenerator.
            db_ops: An instance of DatabaseOps.
        """
        # Store the passed instances instead of creating new ones
        self.config = scraper.config # Assume scraper has config, or pass config separately
        self.scraper = scraper # Store if needed by other methods
        self.researcher = researcher
        self.generator = generator
        self.db = db_ops
        logger.info("LinkedInOutreachPipeline initialized with provided components.")

    def process_single_profile_with_scraper(self, profile_url, scraper_instance):
        """Process a single LinkedIn profile using the provided Playwright scraper instance."""
        if not scraper_instance:
             logger.error("Scraper instance is not provided.")
             return None
        try:
            # Step 1: Extract LinkedIn profile data using Playwright
            founder_data = scraper_instance.extract_profile_data(profile_url)
            if not founder_data:
                logger.error(f"Failed to extract profile data for {profile_url}")
                return None # Return None to indicate failure

            # Step 2: Extract company information (logic remains similar)
            company_name = None
            company_title = None
            company_description = None

            if 'experiences' in founder_data and founder_data['experiences']:
                founder_keywords = ['founder', 'co-founder', 'cofounder', 'ceo', 'chief executive', 'owner', 'president', 'managing director', 'director', 'entrepreneur', 'proprietor']
                found_primary = False
                for exp in founder_data['experiences']:
                    title_lower = exp.get('title', '').lower()
                    if any(keyword in title_lower for keyword in founder_keywords):
                        company_name = exp.get('company')
                        company_title = exp.get('title')
                        company_description = exp.get('description', '')
                        logger.info(f"Identified primary company (founder role): {company_title} at {company_name}")
                        found_primary = True
                        break
                if not found_primary: # Fallback to most recent if no founder role found
                    exp = founder_data['experiences'][0]
                    company_name = exp.get('company')
                    company_title = exp.get('title')
                    company_description = exp.get('description', '')
                    logger.info(f"Using most recent company: {company_title} at {company_name}")

            # Fallbacks using headline/summary (logic seems okay, keep it)
            if not company_name:
                 headline = founder_data.get('headline', '')
                 # ... (rest of headline/summary parsing logic) ...
                 if not company_name:
                      logger.warning(f"Could not identify company name for {profile_url}. Using fallback.")
                      company_name = "their company" # Fallback

            # Step 3: Enhance founder data
            enhanced_founder_data = founder_data.copy()
            enhanced_founder_data['primary_company'] = {
                'name': company_name,
                'title': company_title,
                'description': company_description
            }

            # Step 4: Research company
            company_data = self.researcher.search_company_info(company_name)
            company_data['title'] = company_title # Add title to company data for saving

            # Step 5 & 6: Save data to database
            founder_id = self.db.save_founder_data(enhanced_founder_data, profile_url)
            if founder_id:
                self.db.save_company_data(founder_id, company_data)
            else:
                 logger.error(f"Failed to save founder data for {profile_url}, cannot proceed.")
                 return None # Indicate failure

            # Step 7: Summarize data
            company_summary = self.generator.summarize_company_data(enhanced_founder_data, company_data)

            # Step 8: Generate message
            personalized_message = self.generator.generate_personalized_message(enhanced_founder_data, company_summary)

            # Step 9: Save message
            message_id = self.db.save_message(founder_id, personalized_message)

            # Step 10: Return results including message_id
            return {
                'founder': enhanced_founder_data,
                'company': company_data,
                'summary': company_summary,
                'message': personalized_message,
                'message_id': message_id, # Include message_id in the return
                'linkedin_url': profile_url, # Ensure URL is in the result
                'full_name': enhanced_founder_data.get('full_name'),
                'company_name': company_name,
            }

        except Exception as e:
            logger.exception(f"Error in pipeline processing {profile_url}: {str(e)}") # Use logger.exception for stack trace
            return None # Indicate failure

    # process_batch_from_csv needs to be adapted to use the persistent scraper instance
    def process_batch_from_csv(self, csv_file, scraper_instance):
        """Process multiple LinkedIn profiles from a CSV file using the provided scraper."""
        if not scraper_instance:
             logger.error("Scraper instance is required for batch processing.")
             return False
        try:
            profiles = []
            with open(csv_file, 'r', encoding='utf-8') as file: # Specify encoding
                reader = csv.DictReader(file)
                for row in reader:
                    url = row.get('linkedin_url') or row.get('url')
                    if url:
                        profiles.append(url)

            if not profiles:
                logger.error("No LinkedIn profile URLs found in CSV file")
                return False

            results_count = 0
            total_profiles = len(profiles)
            logger.info(f"Starting batch processing for {total_profiles} profiles...")

            for i, profile_url in enumerate(profiles):
                logger.info(f"Processing profile {i+1}/{total_profiles}: {profile_url}")
                result = self.process_single_profile_with_scraper(profile_url, scraper_instance)
                if result:
                    results_count += 1
                    logger.info(f"Successfully processed: {profile_url}")
                else:
                    logger.warning(f"Failed to process: {profile_url}")
                # Add delay between requests
                time.sleep(random.uniform(8, 15)) # Increased delay for Playwright

            logger.info(f"Batch processing finished. Successfully processed {results_count}/{total_profiles} profiles.")
            # Optionally export results after batch processing
            # self.db.export_messages_to_csv()

            return results_count > 0

        except FileNotFoundError:
             logger.error(f"CSV file not found: {csv_file}")
             return False
        except Exception as e:
            logger.exception(f"Error processing batch from CSV '{csv_file}': {str(e)}")
            return False

    def cleanup(self):
        """Clean up resources (delegated to scraper instance)."""
        # The cleanup should be called on the specific scraper instance used by the app
        logger.warning("Pipeline cleanup called, but resource management (scraper close) should happen at the application level.")
        # If a scraper instance was stored here (not recommended for persistence):
        # if hasattr(self, 'scraper') and self.scraper:
        #     self.scraper.close()


# Initialize database at module level
init_database()

# Function to get components (used by API endpoint)
# This should NOT create new instances every time if persistence is desired.
# The API endpoint will manage the single instances.
# def get_pipeline_and_scraper():
#     """
#     DEPRECATED for persistent session. Instances should be created once in the API endpoint.
#     """
#     # pipeline = LinkedInOutreachPipeline() # Creates new config, researcher, generator, db ops
#     # db_ops = pipeline.db # Use the one from the pipeline
#     # scraper = LinkedInScraper(pipeline.config) # Creates new auth and playwright instance
#     # return pipeline, db_ops, scraper
#     raise DeprecationWarning("Use singleton instances managed by the API endpoint for persistence.")