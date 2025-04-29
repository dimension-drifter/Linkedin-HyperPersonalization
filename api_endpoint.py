from flask import Flask, request, jsonify, send_file
import os
import sys
import json
import pandas as pd
from datetime import datetime
import traceback
import logging # Use logging
import atexit # To ensure cleanup on exit
# import nest_asyncio # Import nest_asyncio
import time # Import time for delay example if needed
import random # Import random for delay example if needed

# # Apply nest_asyncio - Call it once, early in the script execution
# nest_asyncio.apply()
# print("nest_asyncio applied.") # Optional: confirmation message

# Import necessary classes from main
from main import LinkedInOutreachPipeline, DatabaseOps, Config, LinkedInScraper, CompanyResearcher
from message_generator import MessageGenerator # <-- ADD THIS IMPORT

# LinkedInAuth is now primarily managed within LinkedInScraper
# from linkedin_auth import LinkedInAuth # No longer need direct import here

app = Flask(__name__, static_folder='.')
logger = logging.getLogger(__name__) # Use logger

# --- Global Singleton Instances for Persistence ---
# Initialize these to None. They will be created by initialize_services.
pipeline_instance: LinkedInOutreachPipeline | None = None
db_ops_instance: DatabaseOps | None = None
scraper_instance: LinkedInScraper | None = None # This holds the persistent Playwright session via LinkedInAuth
session_is_valid: bool = False
last_session_check: datetime | None = None
config_instance: Config | None = None

def initialize_services():
    """
    Initialize LinkedIn scraper and pipeline ONCE and reuse the instances.
    Manages the persistent Playwright session via the scraper_instance.
    """
    global config_instance, pipeline_instance, db_ops_instance, scraper_instance
    global session_is_valid, last_session_check

    # Lock or synchronization mechanism might be needed if high concurrency is expected
    # For typical use, this sequential check is often sufficient.

    if scraper_instance is None: # Check if core component (scraper) is initialized
        print("Initializing LinkedIn services for the first time...")
        logger.info("Initializing LinkedIn services (Singleton)...")
        try:
            config_instance = Config()
            db_ops_instance = DatabaseOps()
            # Create the scraper instance - this starts Playwright via LinkedInAuth
            scraper_instance = LinkedInScraper(config_instance)

            # Create the pipeline instance (uses shared config, db_ops)
            # Note: Pipeline itself doesn't hold the scraper state.
            pipeline_instance = LinkedInOutreachPipeline(
                scraper=scraper_instance, # Pass scraper if pipeline needs it directly (or remove if not)
                researcher=CompanyResearcher(config_instance),
                generator=MessageGenerator(config_instance),   # <-- ENSURE THIS USES IMPORTED CLASS
                db_ops=db_ops_instance
            )

            # Attempt initial login immediately after creating the scraper
            print("Attempting initial LinkedIn login...")
            logger.info("Attempting initial LinkedIn login...")
            login_success = scraper_instance.login_to_linkedin() # This uses Playwright

            if login_success:
                session_is_valid = True
                last_session_check = datetime.now()
                print("Initial LinkedIn login successful!")
                logger.info("Initial LinkedIn login successful!")
            else:
                session_is_valid = False
                # Don't stop the app, but log the error. It might recover later.
                print("WARNING: Initial LinkedIn login failed. Check credentials/network. Service will run with limited functionality.")
                logger.warning("Initial LinkedIn login failed. Service will run with limited functionality.")
                # Return an error status for the first call if login fails
                return {"status": "error", "message": "Initial LinkedIn login failed. Please check logs."}

            print("LinkedIn Tool services initialized.")
            logger.info("LinkedIn Tool services initialized.")
            return {"status": "success"}

        except Exception as e:
            error_msg = f"Critical error during service initialization: {str(e)}"
            print(error_msg)
            logger.critical(error_msg, exc_info=True) # Log stack trace
            traceback.print_exc()
            # Ensure cleanup if initialization fails partway
            if scraper_instance:
                scraper_instance.close()
            scraper_instance = None # Reset globals on failure
            pipeline_instance = None
            db_ops_instance = None
            session_is_valid = False
            return {"status": "error", "message": error_msg}
    else:
        # Services already initialized, verify session periodically
        print("Services already initialized. Verifying session...")
        logger.debug("Services already initialized. Verifying session...")
        current_time = datetime.now()
        # Check more frequently if session was previously invalid
        check_interval = 1800 if session_is_valid else 300 # 30 mins if valid, 5 mins if invalid

        if (not session_is_valid or
                last_session_check is None or
                (current_time - last_session_check).total_seconds() > check_interval):

            print(f"Session check needed (Last check: {last_session_check}, Valid: {session_is_valid}). Verifying...")
            logger.info(f"Performing periodic session check (Last check: {last_session_check}, Valid: {session_is_valid})")
            try:
                # Use the existing scraper instance to verify
                session_is_valid = scraper_instance.verify_session() # This uses Playwright
                last_session_check = current_time

                if not session_is_valid:
                    print("LinkedIn session invalid or expired. Attempting to re-login...")
                    logger.warning("LinkedIn session invalid or expired. Attempting re-login.")
                    # Attempt re-login using the existing scraper instance
                    login_success = scraper_instance.login_to_linkedin()
                    if login_success:
                        session_is_valid = True
                        print("LinkedIn re-login successful!")
                        logger.info("LinkedIn re-login successful!")
                    else:
                        print("WARNING: LinkedIn re-login failed.")
                        logger.warning("LinkedIn re-login failed.")
                        # Don't necessarily return error here, allow requests to proceed maybe?
                        # Or return error to signal problem:
                        # return {"status": "error", "message": "Session invalid and re-login failed."}
                else:
                    print("LinkedIn session is still valid.")
                    logger.info("LinkedIn session verified as still valid.")

            except Exception as e:
                 error_msg = f"Error during session verification/re-login: {str(e)}"
                 print(error_msg)
                 logger.error(error_msg, exc_info=True)
                 session_is_valid = False # Assume invalid on error
                 # Decide if this error should block requests
                 # return {"status": "error", "message": error_msg}

        return {"status": "success"} # Indicate services are ready (even if login failed previously)


# --- Initialize Services on App Start ---
print("Starting LinkedIn Tool API Server...")
# Perform initial setup. Handle potential errors during startup.
initialization_result = initialize_services()
if initialization_result["status"] == "error":
    print(f"FATAL: Could not initialize services: {initialization_result['message']}")
    # Depending on severity, you might exit or let Flask start anyway
    # sys.exit("Exiting due to initialization failure.")
    print("Warning: Flask server starting despite service initialization errors.")
else:
    print("Services initialized successfully during startup.")


# --- Ensure Cleanup on Exit ---
def cleanup_resources():
    global scraper_instance
    print("Shutting down API server. Cleaning up resources...")
    logger.info("Shutting down API server. Cleaning up resources...")
    if scraper_instance:
        try:
            scraper_instance.close() # This closes Playwright
            print("Playwright resources closed.")
            logger.info("Playwright resources closed.")
        except Exception as e:
            print(f"Error during cleanup: {e}")
            logger.error(f"Error during cleanup: {e}", exc_info=True)

# Register the cleanup function to be called when the application exits
atexit.register(cleanup_resources)


# --- Flask Routes ---

@app.route('/')
def index():
    # Ensure static files are in a 'static' subdirectory or configure static_folder
    # If index.html is in the root, adjust static_folder= '.'
    return app.send_static_file('index.html')

# Serve static files (adjust paths if needed)
@app.route('/js/<path:path>')
def serve_js(path):
     # Assuming js files are inside a 'static/js' directory
     # return send_from_directory(os.path.join(app.static_folder, 'js'), path)
     # If js is directly under static_folder ('.')
     return app.send_static_file(f'js/{path}')


@app.route('/assets/<path:path>')
def serve_assets(path):
     # Assuming assets are inside 'static/assets'
     # return send_from_directory(os.path.join(app.static_folder, 'assets'), path)
     # If assets is directly under static_folder ('.')
     return app.send_static_file(f'assets/{path}')


@app.route('/api/process_profile', methods=['POST'])
def process_profile():
    """Process a single LinkedIn profile URL using the persistent scraper."""
    # 1. Ensure services are initialized and session is checked
    init_status = initialize_services()
    # Allow processing even if login failed initially, but log it.
    # if init_status["status"] == "error":
    #     return jsonify({"error": f"Service initialization error: {init_status['message']}"}), 503 # Service Unavailable

    if not pipeline_instance or not scraper_instance or not db_ops_instance:
         return jsonify({"error": "Services not available. Initialization might have failed."}), 503

    # Check session validity *before* processing
    if not session_is_valid:
         logger.warning("Processing profile requested, but LinkedIn session is currently invalid.")
         # Optionally return an error or try to proceed cautiously
         # return jsonify({"error": "LinkedIn session is invalid. Please try again later or check logs."}), 503

    try:
        data = request.json
        linkedin_url = data.get('url')

        if not linkedin_url:
            return jsonify({"error": "LinkedIn URL is required"}), 400

        # Use the SINGLETON instances
        # Pass the persistent scraper_instance to the pipeline method
        result = pipeline_instance.process_single_profile_with_scraper(linkedin_url, scraper_instance)

        if result is None:
            # Check logs for the specific error in process_single_profile_with_scraper
            logger.error(f"process_single_profile_with_scraper returned None for URL: {linkedin_url}")
            return jsonify({"error": "Failed to process profile. Check server logs for details."}), 500

        # Result should already contain 'message_id' if successful
        # message_id = result.get('message_id') # Already included in result dict

        # Return the full result dictionary
        return jsonify(result)

    except Exception as e:
        error_msg = f"Error processing profile {linkedin_url}: {str(e)}"
        print(error_msg)
        logger.exception(error_msg) # Log stack trace
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred."}), 500


@app.route('/api/process_batch', methods=['POST'])
def process_batch():
    """Process multiple LinkedIn profile URLs using the persistent scraper."""
    init_status = initialize_services()
    # if init_status["status"] == "error":
    #     return jsonify({"error": f"Service initialization error: {init_status['message']}"}), 503

    if not pipeline_instance or not scraper_instance or not db_ops_instance:
         return jsonify({"error": "Services not available."}), 503

    if not session_is_valid:
         logger.warning("Batch processing requested, but LinkedIn session is currently invalid.")
         # return jsonify({"error": "LinkedIn session is invalid. Cannot process batch."}), 503

    try:
        data = request.json
        urls = data.get('urls', [])

        if not urls:
            return jsonify({"error": "At least one LinkedIn URL is required"}), 400

        # Limit batch size to avoid overwhelming LinkedIn or the server
        MAX_BATCH_SIZE = 5
        if len(urls) > MAX_BATCH_SIZE:
            return jsonify({"error": f"Maximum {MAX_BATCH_SIZE} URLs allowed per batch"}), 400

        results = []
        total = len(urls)
        processed_count = 0

        for i, url in enumerate(urls):
            print(f"Processing batch item {i+1}/{total}: {url}")
            logger.info(f"Processing batch item {i+1}/{total}: {url}")
            try:
                # Use the SINGLETON instances
                result = pipeline_instance.process_single_profile_with_scraper(url, scraper_instance)
                if result:
                    results.append(result)
                    processed_count += 1
                    print(f"Successfully processed batch item: {url}")
                    logger.info(f"Successfully processed batch item: {url}")
                else:
                    print(f"Failed to process batch item: {url}")
                    logger.warning(f"Failed to process batch item: {url}")
                    # Optionally add error info to results: results.append({"url": url, "error": "Processing failed"})

                # Add a significant delay between batch items
                delay = random.uniform(10, 20)
                print(f"Waiting {delay:.1f}s before next profile...")
                time.sleep(delay)

            except Exception as e:
                error_msg = f"Error processing URL {url} in batch: {str(e)}"
                print(error_msg)
                logger.exception(error_msg)
                results.append({"url": url, "error": "Internal server error during processing"})
                # Continue with the next URL

        print(f"Batch processing complete. Processed {processed_count}/{total} URLs.")
        logger.info(f"Batch processing complete. Processed {processed_count}/{total} URLs.")

        if not results:
             # This might happen if all URLs failed
             return jsonify({"error": "Failed to process any URLs in the batch. Check logs."}), 500

        return jsonify(results) # Return list of result dicts

    except Exception as e:
        error_msg = f"Error processing batch request: {str(e)}"
        print(error_msg)
        logger.exception(error_msg)
        return jsonify({"error": "An internal server error occurred during batch processing."}), 500


@app.route('/api/message_history', methods=['GET'])
def message_history():
    """Get message history from the database using the singleton db_ops."""
    # No need to call initialize_services() here unless db connection needs checking
    if not db_ops_instance:
         return jsonify({"error": "Database service not available."}), 503
    try:
        # Use the singleton db_ops_instance
        messages_data = db_ops_instance.get_all_messages() # Should return list of dicts

        # Format data for frontend if necessary (already list of dicts)
        # Example: Convert was_sent to boolean if it's not already
        for msg in messages_data:
             msg['sent'] = bool(msg.get('was_sent', 0))
             # Ensure all expected keys are present
             msg.setdefault('full_name', '')
             msg.setdefault('linkedin_url', '')
             msg.setdefault('company_name', '')
             msg.setdefault('message_text', '')
             msg.setdefault('generated_date', '')
             msg.setdefault('message_id', None) # Ensure message_id is present

        return jsonify(messages_data)
    except Exception as e:
        error_msg = f"Error fetching message history: {str(e)}"
        print(error_msg)
        logger.exception(error_msg)
        return jsonify({"error": "Failed to retrieve message history."}), 500


@app.route('/api/mark_sent', methods=['POST'])
def mark_sent():
    """Mark a message as sent using the singleton db_ops."""
    if not db_ops_instance:
         return jsonify({"error": "Database service not available."}), 503
    try:
        data = request.json
        # Use 'message_id' consistent with get_all_messages response
        message_id = data.get('message_id')

        if message_id is None: # Check for None explicitly
            return jsonify({"error": "Message ID is required"}), 400

        # Use the singleton db_ops_instance
        success = db_ops_instance.mark_message_as_sent(message_id)

        if not success:
            # Log the failure reason if possible (db_ops should log it)
            logger.warning(f"Failed attempt to mark message ID {message_id} as sent.")
            return jsonify({"error": "Failed to mark message as sent (e.g., ID not found)"}), 404 # Not Found or 500

        return jsonify({"success": True})

    except Exception as e:
        error_msg = f"Error marking message as sent: {str(e)}"
        print(error_msg)
        logger.exception(error_msg)
        return jsonify({"error": "An internal server error occurred."}), 500


@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    """Export message history as CSV using the singleton db_ops."""
    if not db_ops_instance:
         return jsonify({"error": "Database service not available."}), 503
    try:
        # Define the CSV path (consider making it temporary or configurable)
        csv_filename = f"linkedin_messages_{datetime.now():%Y%m%d_%H%M%S}.csv"
        csv_path = os.path.join(os.getcwd(), csv_filename) # Save in current dir for simplicity

        # Use the singleton db_ops_instance method
        success = db_ops_instance.export_messages_to_csv(filename=csv_path)

        if not success:
             logger.error("Failed to generate CSV export file.")
             return jsonify({"error": "Failed to generate CSV file."}), 500

        # Send the generated file
        return send_file(
            csv_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name='linkedin_messages_export.csv' # User-friendly download name
        )
        # Consider deleting the file after sending if it's temporary

    except Exception as e:
        error_msg = f"Error exporting CSV: {str(e)}"
        print(error_msg)
        logger.exception(error_msg)
        return jsonify({"error": "Failed to export data as CSV."}), 500


# Remove the enhance_db_ops function and call, as methods are now part of the class.

if __name__ == '__main__':
    # Create assets directory if it doesn't exist (relative to where script is run)
    initialization_result = initialize_services()
    if initialization_result["status"] == "error":
        print(f"FATAL: Could not initialize services: {initialization_result['message']}")
        # Decide if you want to exit or run with limited functionality
        # sys.exit(1) # Example: exit on fatal error
        print("Warning: Flask server starting despite service initialization errors.")
    elif initialization_result["status"] == "warning":
         print(f"Warning: {initialization_result['message']}")
    else:
        print("Services initialized successfully during startup.")

    # Start the Flask app
    # use_reloader=False is important to prevent re-initialization and losing the persistent session
    # debug=True can cause issues with persistence if it triggers reloads, use cautiously
    print("Starting Flask development server on http://127.0.0.1:8000/")
    app.run(host='127.0.0.1', port=8000, debug=False, use_reloader=False,threaded=False, processes=1)