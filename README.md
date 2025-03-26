# LinkedIn Hyper-Personalization

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)

This tool leverages web scraping and generative AI to process LinkedIn profiles, gather relevant information about individuals and their companies, and generate hyper-personalized outreach messages suitable for connection requests or initial contact. It features a Streamlit web interface for easy interaction.


## Overview

The primary goal of this project is to streamline the process of crafting personalized messages for LinkedIn outreach. Instead of manually researching profiles and writing messages, this tool automates:

1.  **LinkedIn Login:** Securely logs into LinkedIn using Selenium to access profile data.
2.  **Profile Scraping:** Extracts key information from a given LinkedIn profile URL (name, headline, summary, experience, education).
3.  **Company Research:** Identifies the individual's primary company and performs basic web research to find its website, recent news, and a description using web searches.
4.  **AI Summarization:** Uses AI to synthesize the gathered founder and company data into a concise summary.
5.  **AI Message Generation:** Leverages the AI and the generated summary to create a short, personalized outreach message highlighting specific details about the individual or their company.
6.  **Data Storage:** Saves processed founder data, company information, and generated messages into an SQLite database.
7.  **User Interface:** Provides a Streamlit web application to process single profiles, batch process multiple URLs, view historical messages, track sent status, and export data.

## ✨Features

*   **Streamlit Web Interface:** Easy-to-use UI for processing and viewing data.
*   **Secure LinkedIn Login:** Handles login using provided credentials and manages session cookies.
*   **Single Profile Processing:** Input a LinkedIn URL to get detailed info and a personalized message.
*   **Batch Processing:** Process up to 5 LinkedIn profile URLs simultaneously.
*   **Profile Data Extraction:** Fetches name, headline, location, summary, experience, and education details.
*   **Company Identification & Research:** Attempts to identify the primary company and find relevant public information.
*   **AI-Powered Summarization:** Generates context-rich summaries using AI.
*   **AI-Powered Message Generation:** Creates unique, context-aware outreach messages tailored to the individual.
*   **History Tracking:** View all previously generated messages in a dedicated tab.
*   **Sent Status Tracking:** Mark messages as 'sent' directly within the history tab (session-based).
*   **Data Persistence:** Stores results in an SQLite database (`linkedin_outreach.db`).
*   **CSV Export:** Download the history of generated messages, including their 'sent' status.
*   **Logging:** Records processing steps and potential errors in `linkedin_outreach.log`.

## 🎯Why Use This Tool?

- **Save Time**: Automate research that would take hours manually
- **Higher Response Rate**: Genuinely personalized messages get better results
- **Easy to Use**: Simple web interface requires no coding knowledge
- **Data Privacy**: All data stays on your local machine

## 🔧Tech Stack

*   **Backend:** Python 3
*   **Web Framework:** Streamlit
*   **Web Scraping:** Selenium, BeautifulSoup4, webdriver-manager
*   **AI:** Google Generative AI SDK (`google-generativeai`)
*   **HTTP Requests:** Requests
*   **Database:** SQLite3
*   **Configuration:** python-dotenv
*   **Data Handling:** Pandas

## 🚀 Setup and Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/dimension-drifter/Linkedin-HyperPersonalization.git
    cd Linkedin-HyperPersonalization
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *(If `requirements.txt` doesn't exist, create it from the imports or install manually):*
    ```bash
    pip install streamlit google-generativeai selenium beautifulsoup4 webdriver-manager requests python-dotenv pandas
    ```
4.  **Initialize Database (Automatic):**
    The SQLite database (`linkedin_outreach.db`) and necessary tables will be created automatically the first time `main.py` or `app.py` is run.

## 📊 Usage

1.  **Ensure your virtual environment is activated.**
2.  **Run the Streamlit application:**
    ```bash
    streamlit run app.py
    ```
3.  Open your web browser and navigate to the local URL provided by Streamlit (usually `http://localhost:8501`).
4.  The application will attempt to log into LinkedIn automatically upon startup. Monitor the console/terminal for login status.
5.  Use the tabs:
    *   **Single Profile:** Enter a LinkedIn profile URL and click "Process Profile".
    *   **Batch Processing:** Enter up to 5 LinkedIn profile URLs (one per line) and click "Process Batch". View results and generated messages below.
    *   **History:** View all previously generated messages, mark them as sent (this status is stored in your browser session), and download the data as a CSV file.

## How It Works

1.  **Login:** `LinkedInScraper` uses Selenium to log into LinkedIn, saving cookies for subsequent sessions.
2.  **Scraping:** For a given URL, `LinkedInScraper` navigates to the profile, scrolls to load content, and parses the HTML using BeautifulSoup to extract relevant data points.
3.  **Company Research:** `CompanyResearcher` takes the identified company name, searches the web (using DuckDuckGo via scraping and potentially free news API endpoints) to find a website, description snippets, and recent news headlines.
4.  **Summarization:** `MessageGenerator` sends the structured founder and company data to the Google Gemini API (`gemini-2.0-flash` model) with a detailed prompt to create a comprehensive summary.
5.  **Message Generation:** `MessageGenerator` uses the generated summary and another prompt to ask the Gemini API to craft a short, personalized message focusing on unique details. Character limits are enforced.
6.  **Storage:** `DatabaseOps` handles writing founder data, company details, and the generated message into the respective SQLite tables.
7.  **UI Interaction:** `app.py` uses Streamlit to create the user interface, handle inputs, call the `LinkedInOutreachPipeline` methods, and display results fetched from the database or live processing.

## 📷 Demo

![Demo Link](path/to/screenshot.png)
*Caption: Youtube Video demo of working project*

![Streamlit Interface](https://github.com/user-attachments/assets/bca8c543-2a99-4bc8-8abe-1d31843e1267)
*The main interface for processing LinkedIn profiles*

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs, feature requests, or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
