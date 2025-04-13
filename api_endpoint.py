from flask import Flask, request, jsonify, send_file
import os
import sys
import json
import pandas as pd
from datetime import datetime
import traceback
import main  # Import your existing main.py module

app = Flask(__name__, static_folder='.')

# Global objects for LinkedIn session persistence
pipeline = None
db_ops = None
linkedin_scraper = None
session_is_valid = False
last_session_check = None

def initialize_services():
    """Initialize LinkedIn scraper and pipeline once and maintain session"""
    global pipeline, db_ops, linkedin_scraper, session_is_valid, last_session_check
    
    try:
        if pipeline is None or db_ops is None or linkedin_scraper is None:
            print("Initializing LinkedIn services...")
            pipeline = main.LinkedInOutreachPipeline()
            db_ops = main.DatabaseOps()
            linkedin_scraper = main.LinkedInScraper(pipeline.config)
            
            # Attempt to log in to LinkedIn
            print("Attempting to log in to LinkedIn...")
            linkedin_login_success = linkedin_scraper.login_to_linkedin()
            if linkedin_login_success:
                session_is_valid = True
                last_session_check = datetime.now()
                print("LinkedIn login successful!")
            else:
                print("Failed to login to LinkedIn. Check credentials in .env file.")
                session_is_valid = False
                return {"status": "error", "message": "LinkedIn login failed"}
            
            return {"status": "success"}
        else:
            # If services already initialized, verify session is still valid
            # and session was checked in the last 30 minutes
            current_time = datetime.now()
            if (not session_is_valid or 
                last_session_check is None or 
                (current_time - last_session_check).total_seconds() > 1800):  # 30 minutes
                
                print("Verifying LinkedIn session...")
                session_is_valid = linkedin_scraper.verify_session()
                last_session_check = current_time
                
                if not session_is_valid:
                    print("LinkedIn session expired. Attempting to login again...")
                    linkedin_login_success = linkedin_scraper.login_to_linkedin()
                    if linkedin_login_success:
                        session_is_valid = True
                        print("LinkedIn login successful!")
                    else:
                        print("Failed to login to LinkedIn. Check credentials in .env file.")
                        return {"status": "error", "message": "LinkedIn login failed"}
                else:
                    print("LinkedIn session is still valid.")
            
            return {"status": "success"}
            
    except Exception as e:
        error_msg = f"Error initializing services: {str(e)}"
        print(error_msg)
        traceback.print_exc()  # Print detailed stack trace for debugging
        session_is_valid = False
        return {"status": "error", "message": error_msg}

# Initialize the services when the application starts
print("Starting LinkedIn Tool API Server...")
init_result = initialize_services()
if init_result and init_result.get("status") == "error":
    print(f"WARNING: Services failed to initialize: {init_result.get('message')}")
    print("The application will try to initialize again when endpoints are called.")
else:
    print("LinkedIn Tool services initialized successfully!")

# Serve static files
@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/js/<path:path>')
def serve_js(path):
    return app.send_static_file(f'js/{path}')

@app.route('/assets/<path:path>')
def serve_assets(path):
    return app.send_static_file(f'assets/{path}')

# API Endpoints
@app.route('/api/process_profile', methods=['POST'])
def process_profile():
    """Process a single LinkedIn profile URL"""
    try:
        # Initialize if not already or verify session
        global pipeline, db_ops, linkedin_scraper, session_is_valid
        init_result = initialize_services()
        if init_result.get("status") == "error":
            return jsonify({"error": init_result.get("message")}), 500
        
        data = request.json
        linkedin_url = data.get('url')
        
        if not linkedin_url:
            return jsonify({"error": "LinkedIn URL is required"}), 400
        
        # Process the profile using the pipeline from main.py
        result = pipeline.process_single_profile_with_scraper(linkedin_url, linkedin_scraper)
        
        if not result:
            return jsonify({"error": "Failed to process profile"}), 500
        
        # Get message ID for reference
        message_id = None
        try:
            # Query the latest message for this URL
            messages = db_ops.get_messages_by_linkedin_url(linkedin_url)
            if messages:
                message_id = messages[0][0]  # Assuming the first column is the ID
        except Exception as e:
            print(f"Error fetching message ID: {str(e)}")
            # Continue even if we can't get the message ID
        
        # Add message_id to the response
        result['message_id'] = message_id
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error processing profile: {str(e)}")
        traceback.print_exc()  # Print detailed stack trace for debugging
        return jsonify({"error": str(e)}), 500

@app.route('/api/process_batch', methods=['POST'])
def process_batch():
    """Process multiple LinkedIn profile URLs"""
    try:
        # Initialize if not already
        init_result = initialize_services()
        if init_result.get("status") == "error":
            return jsonify({"error": init_result.get("message")}), 500
        
        data = request.json
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({"error": "At least one LinkedIn URL is required"}), 400
        
        if len(urls) > 5:
            return jsonify({"error": "Maximum 5 URLs allowed"}), 400
        
        results = []
        total = len(urls)
        
        for i, url in enumerate(urls):
            try:
                # Process each profile
                result = pipeline.process_single_profile_with_scraper(url, linkedin_scraper)
                
                if result:
                    # Get message ID for reference
                    message_id = None
                    try:
                        # Query the latest message for this URL
                        messages = db_ops.get_messages_by_linkedin_url(url)
                        if messages:
                            message_id = messages[0][0]  # Assuming the first column is the ID
                    except Exception as e:
                        print(f"Error fetching message ID: {str(e)}")
                    
                    # Add message_id to the result
                    result['message_id'] = message_id
                    results.append(result)
                    
                    print(f"Processed {i+1}/{total}: {url}")
                else:
                    print(f"Failed to process {i+1}/{total}: {url}")
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")
                # Continue with next URL even if one fails
        
        if not results:
            return jsonify({"error": "Failed to process any URLs"}), 500
            
        return jsonify(results)
        
    except Exception as e:
        print(f"Error processing batch: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/message_history', methods=['GET'])
def message_history():
    """Get message history from the database"""
    try:
        # Initialize if not already
        init_result = initialize_services()
        if init_result.get("status") == "error":
            return jsonify({"error": init_result.get("message")}), 500
        
        # Fetch messages from the database
        raw_messages = db_ops.get_all_messages()
        
        messages = []
        for msg in raw_messages:
            # Convert database rows to dictionaries
            # Adjust these indices based on your actual database schema
            message = {
                'id': msg[0],
                'full_name': msg[1],
                'linkedin_url': msg[2],
                'company_name': msg[3],
                'message_text': msg[4],
                'generated_date': msg[5],
                'sent': bool(msg[6]) if len(msg) > 6 else False
            }
            messages.append(message)
        
        return jsonify(messages)
        
    except Exception as e:
        print(f"Error fetching message history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/mark_sent', methods=['POST'])
def mark_sent():
    """Mark a message as sent"""
    try:
        # Initialize if not already
        init_result = initialize_services()
        if init_result.get("status") == "error":
            return jsonify({"error": init_result.get("message")}), 500
        
        data = request.json
        message_id = data.get('message_id')
        
        if not message_id:
            return jsonify({"error": "Message ID is required"}), 400
        
        # Update the database
        success = db_ops.mark_message_as_sent(message_id)
        
        if not success:
            return jsonify({"error": "Failed to mark message as sent"}), 500
            
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"Error marking message as sent: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    """Export message history as CSV"""
    try:
        # Initialize if not already
        init_result = initialize_services()
        if init_result.get("status") == "error":
            return jsonify({"error": init_result.get("message")}), 500
        
        # Fetch messages from the database
        raw_messages = db_ops.get_all_messages()
        
        messages = []
        for msg in raw_messages:
            # Convert database rows to dictionaries
            # Adjust these indices based on your actual database schema
            message = {
                'id': msg[0],
                'full_name': msg[1],
                'linkedin_url': msg[2],
                'company_name': msg[3],
                'message_text': msg[4],
                'generated_date': msg[5],
                'sent': bool(msg[6]) if len(msg) > 6 else False
            }
            messages.append(message)
        
        # Create a DataFrame
        df = pd.DataFrame(messages)
        
        # Generate a temporary CSV file
        csv_path = 'linkedin_messages.csv'
        df.to_csv(csv_path, index=False)
        
        # Send the file
        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name='linkedin_messages.csv'
        )
        
    except Exception as e:
        print(f"Error exporting CSV: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Enhanced DatabaseOps methods to support the new UI
def enhance_db_ops():
    """Add methods to DatabaseOps class if they don't exist"""
    # Check if the method exists, if not, add it
    if not hasattr(main.DatabaseOps, 'mark_message_as_sent'):
        def mark_message_as_sent(self, message_id):
            try:
                # Update the 'sent' column to 1 (True)
                query = "UPDATE messages SET sent = 1 WHERE id = ?"
                self.cursor.execute(query, (message_id,))
                self.conn.commit()
                return True
            except Exception as e:
                print(f"Error marking message as sent: {str(e)}")
                return False
        
        # Add the method to the class
        main.DatabaseOps.mark_message_as_sent = mark_message_as_sent
    
    # Make sure we have a method to get messages by LinkedIn URL
    if not hasattr(main.DatabaseOps, 'get_messages_by_linkedin_url'):
        def get_messages_by_linkedin_url(self, linkedin_url):
            try:
                query = "SELECT * FROM messages WHERE linkedin_url = ? ORDER BY generated_date DESC"
                self.cursor.execute(query, (linkedin_url,))
                return self.cursor.fetchall()
            except Exception as e:
                print(f"Error getting messages by LinkedIn URL: {str(e)}")
                return []
        
        # Add the method to the class
        main.DatabaseOps.get_messages_by_linkedin_url = get_messages_by_linkedin_url

# Apply enhancements to DatabaseOps
enhance_db_ops()

if __name__ == '__main__':
    # Create assets directory if it doesn't exist
    if not os.path.exists('assets'):
        os.makedirs('assets')
    
    # Start the Flask app
    app.run(debug=True, port=8000)