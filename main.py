import os
import argparse
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
        """Set up Selenium WebDriver for LinkedIn scraping"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument(f"user-agent={random.choice(self.config.user_agents)}")
        
        # Set up Chrome driver
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
    
    def login_to_linkedin(self):
        """Login to LinkedIn using provided credentials"""
        if not self.config.linkedin_email or not self.config.linkedin_password:
            logger.warning("LinkedIn credentials not provided. Some data may be limited.")
            return False
            
        try:
            logger.info("Logging into LinkedIn...")
            self.driver.get("https://www.linkedin.com/login")
            
            # Wait for the page to load and login elements to be visible
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # Enter credentials and login
            self.driver.find_element(By.ID, "username").send_keys(self.config.linkedin_email)
            self.driver.find_element(By.ID, "password").send_keys(self.config.linkedin_password)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            # Check if login was successful by waiting for feed page
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "global-nav"))
                )
                logger.info("Successfully logged into LinkedIn")
                return True
            except:
                logger.warning("LinkedIn login might have failed. Continuing with limited access.")
                return False
                
        except Exception as e:
            logger.error(f"Error logging into LinkedIn: {str(e)}")
            return False
    
    def extract_profile_data(self, profile_url):
        """Extract data from a LinkedIn profile"""
        logger.info(f"Extracting data from LinkedIn profile: {profile_url}")
        
        try:
            # Navigate to the profile
            self.driver.get(profile_url)
            time.sleep(random.uniform(2, 4))  # Random delay to avoid detection
            
            # Get profile HTML
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract basic profile information
            profile_data = {}
            
            # Get full name
            try:
                name_element = self.driver.find_element(By.CSS_SELECTOR, "h1.text-heading-xlarge")
                profile_data['full_name'] = name_element.text.strip()
            except:
                profile_data['full_name'] = "Unknown"
                
            # Get headline
            try:
                headline = self.driver.find_element(By.CSS_SELECTOR, "div.text-body-medium")
                profile_data['headline'] = headline.text.strip()
            except:
                profile_data['headline'] = ""
                
            # Get location
            try:
                location = self.driver.find_element(By.CSS_SELECTOR, "span.text-body-small.inline.t-black--light.break-words")
                profile_data['location'] = location.text.strip()
            except:
                profile_data['location'] = ""
                
            # Get summary/about
            try:
                see_more = self.driver.find_element(By.CSS_SELECTOR, "button.inline-show-more-text__button")
                see_more.click()
                about_section = self.driver.find_element(By.CSS_SELECTOR, "div.display-flex.ph5.pv3")
                profile_data['summary'] = about_section.text.strip()
            except:
                profile_data['summary'] = ""
                
            # Get experience section
            profile_data['experiences'] = []
            try:
                # First try to expand the experience section if needed
                try:
                    experience_section = self.driver.find_element(By.ID, "experience")
                    experience_section.click()
                    time.sleep(1)
                except:
                    pass
                
                experience_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.artdeco-list__item.pvs-list__item--line-separated")
                
                for element in experience_elements:
                    try:
                        company_element = element.find_element(By.CSS_SELECTOR, "span.t-14.t-normal")
                        title_element = element.find_element(By.CSS_SELECTOR, "span.t-16.t-bold")
                        
                        experience = {
                            'company': company_element.text.strip(),
                            'title': title_element.text.strip(),
                            'description': '',
                            'company_linkedin_url': ''
                        }
                        
                        # Try to get the company LinkedIn URL
                        try:
                            company_link = element.find_element(By.CSS_SELECTOR, "a.optional-action-target-wrapper")
                            experience['company_linkedin_url'] = company_link.get_attribute('href')
                        except:
                            pass
                            
                        profile_data['experiences'].append(experience)
                    except Exception as e:
                        continue
            except Exception as e:
                logger.warning(f"Error extracting experience data: {str(e)}")
            
            return profile_data
            
        except Exception as e:
            logger.error(f"Error extracting LinkedIn profile data: {str(e)}")
            return None
    
    def close(self):
        """Close the Selenium WebDriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()

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

# Message generation class using Gemini API
class MessageGenerator:
    def __init__(self, config):
        self.config = config
        self.generation_model = genai.GenerativeModel('gemini-1.5-pro')
    
    def summarize_company_data(self, founder_data, company_data):
        """Summarize all the data we have about the founder and company using Gemini"""
        try:
            founder_summary = {
                'name': founder_data.get('full_name', ''),
                'headline': founder_data.get('headline', ''),
                'summary': founder_data.get('summary', ''),
                'location': founder_data.get('location', '')
            }
            
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
            
            # Use Gemini to create a concise summary
            prompt = f"""
            Please create a concise summary (max 150 words) about this founder and their company:
            
            Founder: {json.dumps(founder_summary)}
            
            Company: {json.dumps(company_summary)}
            
            {news_summary}
            
            Focus on their current business, achievements, and any interesting points that would be relevant for a personalized outreach.
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
            
            prompt = f"""
            Create a personalized LinkedIn message to {founder_name}, based on this summary:
            
            {company_summary}
            
            Requirements for the message:
            1. Keep it short (under 300 characters) and conversational
            2. Mention a specific detail about their company or achievement
            3. Briefly introduce myself as an ML/AI engineer interested in their space
            4. End with a simple question to start a conversation
            5. Make it feel authentic and not sales-y
            6. Don't use generic phrases like "I came across your profile" or "I'm impressed with your work"
            
            The message should be ready to copy and paste directly to LinkedIn.
            """
            
            response = self.generation_model.generate_content(prompt)
            message = response.text
            
            # Check character limit for LinkedIn first messages (300)
            if len(message) > 300:
                prompt = f"""
                The previous message was too long. Please rewrite it to be under 300 characters while keeping it personalized and mentioning something specific about {founder_name}'s company.
                """
                response = self.generation_model.generate_content(prompt)
                message = response.text
                
            return message
            
        except Exception as e:
            logger.error(f"Error generating personalized message: {str(e)}")
            return f"Hi {founder_data.get('full_name', '').split()[0]}, I'm an ML/AI engineer and noticed your work at {company_summary.split()[0] if company_summary else 'your company'}. Would love to connect and learn more about what you're building."

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
    
    def process_single_profile(self, profile_url):
        """Process a single LinkedIn profile to generate a personalized message"""
        try:
            # Step 1: Attempt to login to LinkedIn (optional but helps get more data)
            self.scraper.login_to_linkedin()
            
            # Step 2: Extract LinkedIn profile data
            founder_data = self.scraper.extract_profile_data(profile_url)
            if not founder_data:
                logger.error("Failed to extract profile data")
                return None
                
            # Step 3: Extract company information
            company_name = None
            if 'experiences' in founder_data and founder_data['experiences']:
                # Look for founder/CEO positions first
                founder_positions = ['founder', 'co-founder', 'ceo', 'chief executive officer']
                
                for exp in founder_data['experiences']:
                    if any(position.lower() in exp.get('title', '').lower() for position in founder_positions):
                        company_name = exp.get('company')
                        break
                        
                # If no founder position found, use the most recent company
                if not company_name and founder_data['experiences']:
                    company_name = founder_data['experiences'][0].get('company')
            
            if not company_name:
                # Try to extract from headline if experiences not available
                headline = founder_data.get('headline', '')
                if 'at' in headline.lower():
                    company_name = headline.lower().split('at')[-1].strip()
            
            if not company_name:
                logger.warning("Could not identify company name")
                company_name = "Unknown Company"
            
            # Step 4: Research company
            company_data = self.researcher.search_company_info(company_name)
            
            # Step 5: Save founder data to database
            founder_id = self.db.save_founder_data(founder_data, profile_url)
            
            # Step 6: Save company data to database
            self.db.save_company_data(founder_id, company_data)
            
            # Step 7: Summarize all data
            company_summary = self.generator.summarize_company_data(founder_data, company_data)
            
            # Step 8: Generate personalized message
            personalized_message = self.generator.generate_personalized_message(founder_data, company_summary)
            
            # Step 9: Save message to database
            message_id = self.db.save_message(founder_id, personalized_message)
            
            # Step 10: Return the results
            return {
                'founder': founder_data,
                'company': company_data,
                'summary': company_summary,
                'message': personalized_message
            }
            
        except Exception as e:
            logger.error(f"Error in pipeline: {str(e)}")
            return None
        finally:
            # Ensure we close the browser
            self.scraper.close()
    
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
                result = self.process_single_profile(profile)
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
            # Ensure we close the browser
            self.scraper.close()
    
    def cleanup(self):
        """Clean up resources"""
        self.scraper.close()

def main():
    parser = argparse.ArgumentParser(description='LinkedIn Founder Outreach Pipeline')
    parser.add_argument('--profile', help='URL of the founder\'s LinkedIn profile')
    parser.add_argument('--batch', help='CSV file containing LinkedIn profile URLs')
    parser.add_argument('--export', action='store_true', help='Export all messages to CSV')
    args = parser.parse_args()
    
    pipeline = LinkedInOutreachPipeline()
    
    try:
        if args.profile:
            # Process a single profile
            result = pipeline.process_single_profile(args.profile)
            
            if result:
                print("\n" + "="*80)
                print("FOUNDER INFORMATION")
                print("="*80)
                print(f"Name: {result['founder'].get('full_name', '')}")
                print(f"Headline: {result['founder'].get('headline', '')}")
                print(f"Location: {result['founder'].get('location', '')}")
                
                print("\n" + "="*80)
                print("COMPANY SUMMARY")
                print("="*80)
                print(result['summary'])
                
                print("\n" + "="*80)
                print("PERSONALIZED LINKEDIN MESSAGE")
                print("="*80)
                print(result['message'])
                print("="*80)
                print(f"\nCharacter count: {len(result['message'])} (LinkedIn limit: 300 for first message)")
                
                # Save to file
                with open('linkedin_message.txt', 'w', encoding='utf-8') as f:
                    f.write(result['message'])
                
                print("\nMessage saved to linkedin_message.txt")
                
        elif args.batch:
            # Process multiple profiles from CSV
            success = pipeline.process_batch_from_csv(args.batch)
            if success:
                print("Batch processing completed. Results exported to linkedin_messages.csv")
            else:
                print("Error processing batch")
                
        elif args.export:
            # Export all messages to CSV
            success = pipeline.db.export_messages_to_csv()
            if success:
                print("Messages exported to linkedin_messages.csv")
            else:
                print("Error exporting messages")
                
        else:
            print("Please provide either --profile, --batch, or --export parameter")
            
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        
    finally:
        pipeline.cleanup()

if __name__ == "__main__":
    main()