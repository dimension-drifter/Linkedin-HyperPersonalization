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
# Remove BeautifulSoup import if no longer needed after refactor
# from bs4 import BeautifulSoup
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
    try:
        conn.execute("BEGIN TRANSACTION;") # Start transaction for atomic changes

        # Create founders table if not exists
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

        # Create companies table if not exists
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

        # Create messages table if not exists (initially without message_type if altering)
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

        # Check if 'message_type' column exists in 'messages' table
        cursor.execute("PRAGMA table_info(messages);")
        columns = [info[1] for info in cursor.fetchall()] # Get column names

        if 'message_type' not in columns:
            logger.info("Adding 'message_type' column to existing 'messages' table.")
            # Add the column if it doesn't exist
            cursor.execute("ALTER TABLE messages ADD COLUMN message_type TEXT;")
            logger.info("'message_type' column added successfully.")
        else:
            logger.debug("'message_type' column already exists in 'messages' table.")

        # Now it's safe to create the index
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_type ON messages (founder_id, message_type);")

        # Add new resume_data table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS resume_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            resume_content TEXT,
            file_name TEXT,
            upload_date TEXT,
            is_active INTEGER DEFAULT 1
        )
        ''')

        conn.commit() # Commit the transaction
        logger.info("Database initialization/update complete.")

    except sqlite3.Error as e:
        logger.error(f"Database initialization/update failed: {e}")
        conn.rollback() # Rollback changes on error
    finally:
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
        try:
            genai.configure(api_key=self.gemini_api_key)
            # Use a model that supports vision input (Gemini 1.5 Flash/Pro are good choices)
            self.vision_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini Vision Model configured.")
        except Exception as e:
            logger.error(f"Failed to configure Gemini or initialize vision model: {e}")
            raise RuntimeError(f"Failed to initialize Gemini: {e}") from e


        # User agent for requests and Playwright
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
            # Add more diverse and recent user agents
        ]

# LinkedIn data extraction class using Playwright and Vision AI
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
        # Ensure the vision model is initialized from config
        if not hasattr(config, 'vision_model'):
             logger.error("Vision model not found in config during LinkedInScraper initialization.")
             raise ValueError("Gemini vision model is required for LinkedInScraper.")
        self.vision_model = config.vision_model


    def _ensure_page(self):
        """Ensures the Playwright page is initialized and ready."""
        # Reuse the existing page from the auth instance if available and open
        if self.linkedin_auth._page and not self.linkedin_auth._page.is_closed():
            self.page = self.linkedin_auth._page
            logger.debug("Reusing existing Playwright page from LinkedInAuth.")
            return self.page

        # If not available or closed, try to get/create it via auth module
        logger.info("Playwright page not available or closed. Ensuring login and getting page via auth module.")
        if self.linkedin_auth.ensure_logged_in():
            # ensure_logged_in should set up self.linkedin_auth._page
            if self.linkedin_auth._page and not self.linkedin_auth._page.is_closed():
                self.page = self.linkedin_auth._page
                logger.info("Obtained valid Playwright page after ensuring login.")
                return self.page
            else:
                raise RuntimeError("Failed to obtain a valid Playwright page after login attempt.")
        else:
            raise RuntimeError("Failed to log in to LinkedIn, cannot obtain page.")


    def login_to_linkedin(self):
        """Login to LinkedIn using the auth module (which uses Playwright)."""
        try:
            # Ensure login state via the auth module
            return self.linkedin_auth.ensure_logged_in()
        except Exception as e:
            logger.error(f"Error during LinkedIn login process: {e}")
            return False

    def extract_profile_data(self, profile_url):
        """
        Extract data from a LinkedIn profile using Playwright and Vision API analysis.
        """
        logger.info(f"Extracting data from LinkedIn profile via Screenshot+Vision: {profile_url}")
        
        try:
            page = self._ensure_page()
        except RuntimeError:
            logger.error("Cannot access Playwright page")
            return None

        try:
            # Increased timeouts and better waiting strategy
            logger.info(f"Navigating to profile URL...")
            page.goto(profile_url, wait_until="networkidle", timeout=60000)  # Increased timeout to 60s
            
            # Wait for key profile elements to appear
            try:
                # Wait for either the profile section or any error message
                page.wait_for_selector("section.artdeco-card, .error-container", timeout=15000)
            except:
                # If selector timing out, try proceeding anyway
                pass
                
            # Scroll to ensure content loads
            self._scroll_profile_page(page)
            
            # Take screenshot
            screenshot_path = f"temp_profile_screenshot_{datetime.now():%Y%m%d%H%M%S}.png"
            page.screenshot(path=screenshot_path, full_page=True)
            
            # Extract data from screenshot using Gemini Vision
            profile_data = self._extract_data_from_screenshot(screenshot_path)
            
            # Clean up screenshot
            try:
                os.remove(screenshot_path)
            except:
                pass
                
            if not profile_data:
                return None
                
            profile_data['linkedin_url'] = profile_url
            return profile_data
            
        except Exception as e:
            logger.error(f"Error extracting profile data: {str(e)}")
            return None

    def _extract_data_from_screenshot(self, image_path):
        """
        Uses Gemini Vision API to extract structured profile data from a screenshot.
        """
        logger.info(f"Sending screenshot {image_path} to Gemini Vision for analysis...")
        try:
            # Prepare the image input for Gemini
            profile_image = {
                'mime_type': 'image/png',
                'data': self._read_image_bytes(image_path)
            }

            # Construct the prompt for Gemini
            prompt = """
            Analyze the provided LinkedIn profile screenshot and extract the following information in JSON format:
            - full_name: The full name of the person.
            - headline: The professional headline below the name.
            - location: The geographical location.
            - summary: The text content of the "About" section (if present).
            - experiences: A list of recent work experiences, including:
                - title: Job title.
                - company: Company name.
                - description: (Optional) A brief description if visible.
            - education: A list of educational institutions attended, including:
                - institution: Name of the school/university.
                - degree: Degree or field of study (if visible).

            Focus on extracting the text accurately as it appears in the image. If a section (like 'About' or 'Education') is not clearly visible or present, return an empty string or empty list for that field. Structure the output strictly as a JSON object.

            Example JSON structure:
            {
              "full_name": "Jane Doe",
              "headline": "Software Engineer at Tech Corp | AI Enthusiast",
              "location": "San Francisco Bay Area",
              "summary": "Experienced software engineer passionate about building scalable systems...",
              "experiences": [
                { "title": "Software Engineer", "company": "Tech Corp", "description": "Developed features for..." },
                { "title": "Intern", "company": "Startup Inc", "description": null }
              ],
              "education": [
                { "institution": "State University", "degree": "B.S. Computer Science" },
                { "institution": "Community College", "degree": "Associate's Degree" }
              ]
            }
            """

            # Make the API call
            response = self.vision_model.generate_content([prompt, profile_image])

            # Process the response
            if response and hasattr(response, 'text'):
                extracted_text = response.text.strip()
                logger.debug(f"Raw response from Gemini Vision:\n{extracted_text}")

                # Attempt to parse the JSON response
                try:
                    # Clean potential markdown code block fences
                    if extracted_text.startswith("```json"):
                        extracted_text = extracted_text[7:]
                    if extracted_text.endswith("```"):
                        extracted_text = extracted_text[:-3]
                    extracted_text = extracted_text.strip()

                    profile_data = json.loads(extracted_text)
                    logger.info("Successfully parsed JSON data from Gemini Vision response.")

                    # Basic validation (check if essential keys exist)
                    if not profile_data.get('full_name'):
                         logger.warning("Extracted data missing 'full_name'. Quality may be low.")
                         # Optionally add default values or handle as error
                         profile_data.setdefault('full_name', 'Unknown')
                    profile_data.setdefault('headline', '')
                    profile_data.setdefault('location', '')
                    profile_data.setdefault('summary', '')
                    profile_data.setdefault('experiences', [])
                    profile_data.setdefault('education', [])


                    return profile_data
                except json.JSONDecodeError as json_err:
                    logger.error(f"Failed to parse JSON from Gemini Vision response: {json_err}")
                    logger.error(f"Received text: {extracted_text}")
                    return None
            else:
                logger.error("Received no valid text response from Gemini Vision API.")
                return None

        except genai.types.generation_types.BlockedPromptException as bpe:
             logger.error(f"Gemini API call blocked: {bpe}")
             return None
        except Exception as e:
            logger.error(f"Error during Gemini Vision API call or processing: {str(e)}", exc_info=True)
            return None

    def _read_image_bytes(self, image_path):
        """Reads an image file and returns its byte content."""
        try:
            with open(image_path, "rb") as image_file:
                return image_file.read()
        except FileNotFoundError:
            logger.error(f"Screenshot file not found at path: {image_path}")
            raise
        except Exception as e:
            logger.error(f"Error reading image file {image_path}: {e}")
            raise

    # REMOVE OLD SELECTOR/BS4 BASED EXTRACTION METHODS
    # def _try_playwright_selectors(self, page): ...
    # def _extract_with_beautiful_soup(self, html_content, existing_data=None): ...

    def _scroll_profile_page(self, page):
        """Helper method to scroll through the profile page using Playwright."""
        logger.debug("Scrolling page to load content...")
        try:
            total_height = page.evaluate("document.body.scrollHeight")
            scroll_increment = 700 # Pixels to scroll each time
            current_scroll = 0
            max_scrolls = 25 # Increase max scrolls slightly for potentially longer pages
            scroll_count = 0
            no_change_count = 0
            prev_height = 0

            while scroll_count < max_scrolls:
                # Scroll down
                page.evaluate(f"window.scrollBy(0, {scroll_increment});")
                # Wait for scroll and potential content loading
                time.sleep(random.uniform(0.8, 1.5)) # Slightly longer pauses

                # Check new height
                current_scroll = page.evaluate("window.pageYOffset")
                new_height = page.evaluate("document.body.scrollHeight")

                # Break if we've reached the bottom or height hasn't changed for a few scrolls
                if current_scroll + page.evaluate("window.innerHeight") >= new_height:
                    logger.debug("Reached bottom of the page.")
                    break
                if new_height == prev_height:
                    no_change_count += 1
                    if no_change_count >= 3: # Stop if height doesn't change for 3 consecutive scrolls
                        logger.debug("Page height stable, assuming end of scrollable content.")
                        break
                else:
                    no_change_count = 0 # Reset counter if height changes

                prev_height = new_height
                scroll_count += 1

            # Scroll back to top smoothly
            page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' });")
            time.sleep(1.0) # Wait for scroll to top
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
            # Session verification relies on the auth module's logic
            return self.linkedin_auth.verify_session()
        except Exception as e:
            logger.error(f"Error during session verification call: {e}")
            return False

    # REMOVE _find_element_with_retry if no longer used
    # def _find_element_with_retry(self, page, selectors, timeout_ms=10000): ...

# ... (rest of the classes: CompanyResearcher, DatabaseOps, LinkedInOutreachPipeline remain largely the same) ...
# Ensure LinkedInOutreachPipeline uses the updated scraper correctly

# Company research class using free APIs
class CompanyResearcher:
    def __init__(self, config):
        self.config = config

    def search_company_info(self, company_name):
        """Search for company information using free APIs and web scraping"""
        # --- This method remains the same ---
        logger.info(f"Researching company: {company_name}")
        company_info = {
            'name': company_name,
            'website': self._find_company_website(company_name),
            'news': self._get_news_articles(company_name),
            'description': self._get_company_description(company_name)
        }
        return company_info

    def _find_company_website(self, company_name):
        # --- This method remains the same ---
        try:
            encoded_query = quote_plus(f"{company_name} official website")
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            headers = {'User-Agent': random.choice(self.config.user_agents)}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser') # Need BS4 here
                results = soup.find_all('a', {'class': 'result__url'})
                excluded_domains = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
                                   'crunchbase.com', 'bloomberg.com', 'wikipedia.org', 'youtube.com', 'google.com']
                for result in results:
                    link = result.get('href', '')
                    if link and not any(domain in link for domain in excluded_domains) and link.startswith('http'):
                        # Basic validation: looks like a plausible domain
                        if '.' in link.split('/')[2]: # Check if domain part has a dot
                             logger.info(f"Found potential website: {link}")
                             return link
            return ""
        except Exception as e:
            logger.error(f"Error finding company website for '{company_name}': {str(e)}")
            return ""

    def _get_news_articles(self, company_name):
        # --- This method remains the same ---
        # Consider using a more reliable/official news API if possible
        try:
            # Using a placeholder - replace with a real news API if available
            logger.warning("Using placeholder news search. Consider integrating a proper News API.")
            # Example using DuckDuckGo for news search (less reliable than dedicated API)
            encoded_query = quote_plus(f"{company_name} news")
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            headers = {'User-Agent': random.choice(self.config.user_agents)}
            response = requests.get(url, headers=headers, timeout=10)
            articles = []
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser') # Need BS4 here
                results = soup.find_all('div', class_='result')
                for result in results[:3]: # Get top 3 results
                    title_tag = result.find('a', class_='result__a')
                    link_tag = result.find('a', class_='result__url')
                    if title_tag and link_tag:
                        title = title_tag.get_text(strip=True)
                        link = link_tag.get('href', '')
                        if title and link:
                            articles.append({'title': title, 'link': link})
            return articles
        except Exception as e:
            logger.error(f"Error fetching news for '{company_name}': {str(e)}")
            return []

    def _get_company_description(self, company_name):
        # --- This method remains the same ---
        try:
            encoded_query = quote_plus(f"what is {company_name}")
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            headers = {'User-Agent': random.choice(self.config.user_agents)}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser') # Need BS4 here
                # Look for abstract/snippet text
                snippets = soup.find_all('a', class_='result__snippet')
                if snippets:
                    description = snippets[0].get_text(strip=True)
                    logger.info(f"Found description snippet for {company_name}")
                    return description
                else:
                    # Fallback: Look for definition if available
                    definition = soup.find('div', class_='result--definition')
                    if definition:
                         desc_text = definition.get_text(strip=True)
                         logger.info(f"Found definition for {company_name}")
                         return desc_text

            return ""
        except Exception as e:
            logger.error(f"Error getting company description for '{company_name}': {str(e)}")
            return ""


# Database operations class
class DatabaseOps:
    # --- This class remains the same ---
    def __init__(self):
        self.db_path = 'linkedin_outreach.db'

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_founder_data(self, founder_data, profile_url):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Ensure founder_data is valid
            if not founder_data or not isinstance(founder_data, dict):
                logger.error(f"Invalid founder_data provided for {profile_url}")
                return None
                
            # Ensure summary is handled correctly (might be long)
            summary_text = founder_data.get('summary', '')
            # Handle None explicitly - this is what's causing the error
            if summary_text is None:
                summary_text = ''
            elif isinstance(summary_text, list): # Handle if Gemini returns summary as list
                summary_text = " ".join(summary_text)

            cursor.execute('''
            INSERT OR REPLACE INTO founders
            (linkedin_url, full_name, headline, summary, location, processed_date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                profile_url,
                founder_data.get('full_name', 'Unknown'), # Use default if missing
                founder_data.get('headline', ''),
                summary_text[:10000] if summary_text else '', # Safe slicing
                founder_data.get('location', ''),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            founder_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Saved founder data for ID: {founder_id} (URL: {profile_url})")
            return founder_id
        except sqlite3.Error as e:
            logger.error(f"Database error saving founder data for {profile_url}: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def save_company_data(self, founder_id, company_data):
        if not founder_id: return None
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Ensure description is handled correctly
            description_text = company_data.get('description', '')
            if isinstance(description_text, list):
                description_text = " ".join(description_text)

            cursor.execute("SELECT id FROM companies WHERE founder_id = ?", (founder_id,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute('''
                UPDATE companies SET name = ?, title = ?, description = ?, website = ? WHERE founder_id = ?
                ''', (
                    company_data.get('name', ''), company_data.get('title', ''),
                    description_text[:5000], company_data.get('website', ''), founder_id
                ))
                company_id = existing['id']
            else:
                cursor.execute('''
                INSERT INTO companies (founder_id, name, title, description, website) VALUES (?, ?, ?, ?, ?)
                ''', (
                    founder_id, company_data.get('name', ''), company_data.get('title', ''),
                    description_text[:5000], company_data.get('website', '')
                ))
                company_id = cursor.lastrowid

            conn.commit()
            logger.info(f"Saved/Updated company data for founder ID: {founder_id}")
            return company_id
        except sqlite3.Error as e:
            logger.error(f"Database error saving company data for founder ID {founder_id}: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def save_message(self, founder_id, message_text, message_type): # Added message_type
        if not founder_id: return None
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            INSERT INTO messages (founder_id, message_text, message_type, generated_date, was_sent) VALUES (?, ?, ?, ?, 0)
            ''', (founder_id, message_text, message_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))) # Added message_type
            message_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Saved {message_type} message ID: {message_id} for founder ID: {founder_id}")
            return message_id
        except sqlite3.Error as e:
            logger.error(f"Database error saving {message_type} message for founder ID {founder_id}: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_all_messages(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
            SELECT m.id as message_id, f.full_name, f.linkedin_url,
                   COALESCE(c.name, 'N/A') as company_name,
                   m.message_type, m.message_text, m.generated_date, m.was_sent -- Added message_type
            FROM messages m
            JOIN founders f ON m.founder_id = f.id
            LEFT JOIN companies c ON f.id = c.founder_id
            ORDER BY m.generated_date DESC
            ''')
            results = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Retrieved {len(results)} messages from database.")
            # Add sent boolean conversion
            for msg in results:
                 msg['sent'] = bool(msg.get('was_sent', 0))
                 msg.setdefault('message_id', None) # Ensure message_id is present
            return results
        except sqlite3.Error as e:
            logger.error(f"Database error getting all messages: {str(e)}")
            return []
        finally:
            conn.close()

    # Mark sent might need adjustment depending on which message type it applies to.
    # Assuming it applies to the connection request for now.
    def mark_message_as_sent(self, message_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Optionally, you could verify it's a 'connection' type message first
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
            logger.error(f"Database error marking message ID {message_id} as sent: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # Export might need adjustment to include message_type
    def export_messages_to_csv(self, filename='linkedin_messages.csv'):
        messages = self.get_all_messages()
        if not messages:
            logger.warning("No messages to export")
            return False
        try:
            # Add message_type to fieldnames
            fieldnames = ['message_id', 'full_name', 'company_name', 'linkedin_url',
                          'message_type', 'message_text', 'generated_date', 'was_sent']
            import csv
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
                writer.writeheader()
                for message_dict in messages:
                     # Ensure boolean conversion happens correctly
                     message_dict['was_sent'] = bool(message_dict.get('was_sent', 0))
                     writer.writerow(message_dict)
            logger.info(f"Successfully exported {len(messages)} messages to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error exporting messages to CSV: {str(e)}")
            return False

    # Delete profile needs to delete *all* message types for that founder
    def delete_profile(self, message_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Find the founder_id associated with *any* message ID passed
            cursor.execute("SELECT founder_id FROM messages WHERE id = ?", (message_id,))
            result = cursor.fetchone()
            if not result:
                logger.warning(f"Message ID {message_id} not found for deletion.")
                return False
            founder_id = result['founder_id']

            conn.execute("BEGIN TRANSACTION;")
            # Delete ALL messages associated with this founder_id
            cursor.execute("DELETE FROM messages WHERE founder_id = ?", (founder_id,))
            deleted_messages_count = cursor.rowcount
            logger.info(f"Deleted {deleted_messages_count} messages for founder ID {founder_id}.")

            # Delete company and founder data since all messages are gone
            cursor.execute("DELETE FROM companies WHERE founder_id = ?", (founder_id,))
            cursor.execute("DELETE FROM founders WHERE id = ?", (founder_id,))
            logger.info(f"Deleted founder and company data for founder ID {founder_id}.")

            conn.commit()
            logger.info(f"Deletion process completed for founder ID {founder_id} (triggered by message ID {message_id}).")
            return True
        except sqlite3.Error as e:
            logger.error(f"Database error deleting profile data for founder ID {founder_id}: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def save_resume_data(self, resume_data, file_name):
        """
        Save parsed resume data to the database.
        
        Args:
            resume_data: Dictionary containing parsed resume data
            file_name: Original filename of the resume
            
        Returns:
            resume_id if successful, None otherwise
        """
        if not resume_data:
            logger.error("Cannot save empty resume data")
            return None
            
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # First, deactivate any existing active resumes (we only keep one active at a time for simplicity)
            cursor.execute("UPDATE resume_data SET is_active = 0 WHERE user_id = 1 AND is_active = 1")
            
            # Now save the new resume data
            cursor.execute('''
            INSERT INTO resume_data (user_id, resume_content, file_name, upload_date, is_active)
            VALUES (?, ?, ?, ?, 1)
            ''', (
                1,  # Default user_id
                json.dumps(resume_data),
                file_name,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            resume_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Saved resume data with ID: {resume_id}")
            return resume_id
        except sqlite3.Error as e:
            logger.error(f"Database error saving resume data: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def get_active_resume_data(self):
        """
        Retrieve the currently active resume data.
        
        Returns:
            Dictionary containing resume data if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT resume_content FROM resume_data WHERE user_id = 1 AND is_active = 1 ORDER BY id DESC LIMIT 1")
            result = cursor.fetchone()
            
            if result and result['resume_content']:
                try:
                    resume_data = json.loads(result['resume_content'])
                    return resume_data
                except json.JSONDecodeError:
                    logger.error("Failed to parse stored resume data")
                    return None
            else:
                logger.info("No active resume data found")
                return None
        except sqlite3.Error as e:
            logger.error(f"Database error retrieving resume data: {str(e)}")
            return None
        finally:
            conn.close()


# Main pipeline class
class LinkedInOutreachPipeline:
    def __init__(self, scraper, researcher, generator, db_ops):
        """
        Initializes the pipeline with pre-configured components.
        """
        self.config = scraper.config # Get config from scraper
        self.scraper = scraper
        self.researcher = researcher
        self.generator = generator
        self.db = db_ops
        logger.info("LinkedInOutreachPipeline initialized with provided components.")

    # Modified to accept requested_message_type and only save that type
    def process_single_profile_with_scraper(self, profile_url, scraper_instance, user_tech_stack="", requested_message_type=None): # Added requested_message_type
        if not scraper_instance:
             logger.error("Scraper instance is not provided.")
             return None
        if not requested_message_type:
             logger.error("requested_message_type is required for processing.")
             # Default to connection if not provided? Or raise error? Let's default for now.
             # requested_message_type = 'connection'
             # Better to return error if it's expected from API call
             return None

        try:
            # Step 1: Extract LinkedIn profile data
            founder_data = scraper_instance.extract_profile_data(profile_url)
            if not founder_data:
                logger.error(f"Failed to extract founder data for {profile_url}")
                return None # Stop processing if profile extraction fails

            # Step 2: Identify primary company
            company_name = None
            company_title = None
            company_description = None # Placeholder, might be filled by vision model
            if 'experiences' in founder_data and founder_data['experiences']:
                # Prioritize current company if possible, otherwise take the first one
                current_exp = next((exp for exp in founder_data['experiences'] if 'present' in exp.get('duration', '').lower()), None)
                if current_exp:
                    company_name = current_exp.get('company')
                    company_title = current_exp.get('title')
                    company_description = current_exp.get('description')
                elif founder_data['experiences']:
                    first_exp = founder_data['experiences'][0]
                    company_name = first_exp.get('company')
                    company_title = first_exp.get('title')
                    company_description = first_exp.get('description')

            if not company_name:
                 logger.warning(f"Could not determine primary company for {profile_url}. Using placeholder.")
                 company_name = "their company" # Fallback

            # Step 3: Enhance founder data
            enhanced_founder_data = founder_data.copy()
            enhanced_founder_data['primary_company'] = {
                'name': company_name, 'title': company_title, 'description': company_description
            }

            # Step 4: Research company (only if name is not a placeholder)
            company_research_data = {'name': company_name, 'title': company_title}
            if company_name != "their company":
                 company_research_data.update(self.researcher.search_company_info(company_name))
                 company_research_data['title'] = company_title # Ensure title is preserved

            # Step 5 & 6: Save data to database
            founder_id = self.db.save_founder_data(enhanced_founder_data, profile_url)
            if founder_id:
                self.db.save_company_data(founder_id, company_research_data)
            else:
                 logger.error(f"Failed to save founder data, cannot proceed for {profile_url}")
                 return None # Stop if founder can't be saved

            # Get resume data if available
            resume_data = None
            if hasattr(self.db, 'get_active_resume_data'):
                resume_data = self.db.get_active_resume_data()

            # Step 7: Summarize data
            company_summary = self.generator.summarize_company_data(enhanced_founder_data, company_research_data)

            # Step 8: Generate ONLY the requested message type
            generated_message_text = None
            generated_message_id = None

            if requested_message_type == 'connection':
                generated_message_text = self.generator.generate_connection_request(
                    enhanced_founder_data, company_summary, resume_data
                )
            elif requested_message_type == 'job_inquiry':
                generated_message_text = self.generator.generate_job_inquiry(
                    enhanced_founder_data, company_summary, user_tech_stack, resume_data
                )
            else:
                logger.error(f"Invalid requested_message_type: {requested_message_type}")
                return None # Stop if type is invalid

            if not generated_message_text:
                 logger.error(f"Failed to generate {requested_message_type} message for {profile_url}")
                 # Return partial data or None? Let's return None for consistency
                 return None

            # Step 9: Save ONLY the generated message
            generated_message_id = self.db.save_message(founder_id, generated_message_text, requested_message_type)

            # Step 10: Return results including only the generated message and its ID
            return {
                # 'founder': enhanced_founder_data, # Not needed by frontend directly
                # 'company': company_research_data, # Not needed by frontend directly
                # 'summary': company_summary, # Not needed by frontend directly
                'message_text': generated_message_text,         # Renamed for clarity in API response
                'message_id': generated_message_id,             # Renamed for clarity in API response
                'message_type': requested_message_type,         # Include the type generated
                'linkedin_url': profile_url,
                'full_name': enhanced_founder_data.get('full_name'),
                'company_name': company_name,
                'used_resume_data': resume_data is not None
            }

        except Exception as e:
            logger.exception(f"Error in pipeline processing {profile_url}: {str(e)}")
            return None

    # Batch processing needs to decide WHICH message type to generate for each profile
    # Option 1: Generate only connection requests for batch.
    # Option 2: Add UI choice for batch message type.
    # Let's go with Option 1 for simplicity now.
    def process_batch_from_csv(self, csv_file, scraper_instance, user_tech_stack=""):
        if not scraper_instance:
             logger.error("Scraper instance is required for batch processing.")
             return False
        try:
            # ... (reading CSV remains the same) ...
            profiles = []
            import csv
            from bs4 import BeautifulSoup # Ensure BS4 is available
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    url = row.get('linkedin_url') or row.get('url')
                    if url and url.startswith("http"):
                        profiles.append(url.strip())
                    else:
                        logger.warning(f"Skipping invalid or missing URL in CSV row: {row}")
            if not profiles: return False

            results_count = 0
            total_profiles = len(profiles)
            logger.info(f"Starting batch processing for {total_profiles} profiles...")

            for i, profile_url in enumerate(profiles):
                logger.info(f"Processing profile {i+1}/{total_profiles}: {profile_url}")
                # Call process_single_profile_with_scraper, explicitly requesting 'connection' type for batch
                result = self.process_single_profile_with_scraper(
                    profile_url,
                    scraper_instance,
                    user_tech_stack,
                    requested_message_type='connection' # <<< Hardcode to connection for batch
                )
                if result:
                    # Adapt the result structure if needed for batch display
                    # The result now only contains the connection message details
                    batch_result_data = {
                        "full_name": result.get("full_name"),
                        "company_name": result.get("company_name"),
                        "linkedin_url": result.get("linkedin_url"),
                        "connection_message": { # Structure expected by current batch card JS (needs adjustment)
                            "text": result.get("message_text"),
                            "id": result.get("message_id")
                        },
                        "job_inquiry_message": { # Add empty placeholder if card expects it
                            "text": None,
                            "id": None
                        },
                        "message_id": result.get("message_id") # Primary ID for card actions
                    }
                    # Append batch_result_data to a list to be returned by the API
                    # (This function currently returns boolean, needs change if called by API)
                    results_count += 1
                    logger.info(f"Successfully processed batch item: {profile_url}")
                else:
                    logger.warning(f"Failed to process batch item: {profile_url}")

                # Add delay
                delay = random.uniform(10, 20)
                logger.info(f"Waiting {delay:.1f}s before next profile...")
                time.sleep(delay)
            # ... (rest of batch logic) ...
            # This function needs to return the list of results if called by the API
            # For now, it's designed for direct script execution, returning boolean.
            return results_count > 0 # Keep boolean return for direct script use case

        except FileNotFoundError:
             logger.error(f"CSV file not found: {csv_file}")
             return False
        except Exception as e:
            logger.exception(f"Error processing batch from CSV '{csv_file}': {str(e)}")
            return False

    def cleanup(self):
        """Clean up resources (delegated to scraper instance)."""
        logger.warning("Pipeline cleanup called, resource management should happen at the application level.")


# Initialize database at module level
init_database()

# Import BeautifulSoup globally as it's needed by CompanyResearcher
from bs4 import BeautifulSoup

# --- Main execution block (if running this file directly) ---
if __name__ == '__main__':
    logger.info("Running main.py directly (for testing purposes).")

    # --- Example Usage (for testing the new scraper) ---
    try:
        config = Config()
        scraper = LinkedInScraper(config)
        researcher = CompanyResearcher(config)
        generator = MessageGenerator(config) # Assumes MessageGenerator is correctly imported
        db_ops = DatabaseOps()

        pipeline = LinkedInOutreachPipeline(scraper, researcher, generator, db_ops)

        # --- Test Single Profile ---
        test_profile_url = "https://www.linkedin.com/in/williamhgates/" # Example public profile
        logger.info(f"--- Testing single profile: {test_profile_url} ---")
        # Need to pass the scraper instance AND message type
        result = pipeline.process_single_profile_with_scraper(
            test_profile_url,
            scraper,
            requested_message_type='connection' # Test with 'connection'
        )

        if result:
            logger.info("--- Single Profile Result ---")
            logger.info(f"Name: {result.get('full_name')}")
            logger.info(f"Company: {result.get('company_name')}")
            logger.info(f"Message Type: {result.get('message_type')}")
            logger.info(f"Message ID: {result.get('message_id')}")
            logger.info(f"Generated Message:\n{result.get('message_text')}")
        else:
            logger.error(f"Failed to process single profile {test_profile_url}")

        # --- Test Batch Processing (Optional) ---
        # Create a dummy CSV file 'test_profiles.csv' with a 'linkedin_url' column
        # logger.info("--- Testing batch processing ---")
        # pipeline.process_batch_from_csv('test_profiles.csv', scraper)

    except Exception as e:
        logger.exception(f"Error during main execution test: {e}")
    finally:
        # Ensure cleanup happens even if run directly
        if 'scraper' in locals() and scraper:
            scraper.close()
        logger.info("--- Main execution finished ---")