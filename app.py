import streamlit as st
import main  
import pandas as pd
import random
import time

st.set_page_config(page_title="LinkedIn Hyper-Personalized Outreach", page_icon="🔗", layout="wide")

st.title("LinkedIn Hyper-Personalized Outreach")
st.caption("Process LinkedIn profiles and generate hyper-personalized outreach messages")

st.markdown("---")

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'batch_results' not in st.session_state:
    st.session_state.batch_results = []
if 'batch_processing' not in st.session_state:
    st.session_state.batch_processing = False
if 'processed_count' not in st.session_state:
    st.session_state.processed_count = 0
if 'total_to_process' not in st.session_state:
    st.session_state.total_to_process = 0
    
@st.cache_resource
def get_pipeline_and_scraper():
    pipeline = main.LinkedInOutreachPipeline()
    db_ops = main.DatabaseOps()
    linkedin_scraper = main.LinkedInScraper(pipeline.config)
    return pipeline, db_ops, linkedin_scraper

pipeline, db_ops, linkedin_scraper = get_pipeline_and_scraper()

# Login section
if not st.session_state.logged_in:
    st.info("Please wait while we log into LinkedIn...")
    with st.spinner("Logging in to LinkedIn... (This may take a moment)"):
        login_success = linkedin_scraper.login_to_linkedin()
        if login_success:
            st.session_state.logged_in = True
            st.success("Successfully logged into LinkedIn!")
        else:
            st.error("Failed to login to LinkedIn. Please check your credentials in the .env file.")

# Profile processing UI
if st.session_state.logged_in:
    # Create simple tabs
    tabs = st.tabs(["Single Profile", "Batch Processing", "History"])
    
    # Single Profile Tab
    with tabs[0]:
        st.header("Process Individual LinkedIn Profile")
        
        linkedin_profile_url = st.text_input("Enter LinkedIn Profile URL:")
        process_button = st.button("Process Profile")
        
        if process_button:
            if linkedin_profile_url:
                with st.spinner("Processing profile..."):
                    result = pipeline.process_single_profile_with_scraper(linkedin_profile_url, linkedin_scraper)
                
                if result:
                    st.success("Profile processed successfully!")
                    
                    # Display results
                    st.subheader("Founder Information")
                    st.write(f"**Name:** {result['founder'].get('full_name', '')}")
                    st.write(f"**Headline:** {result['founder'].get('headline', '')}")
                    st.write(f"**Location:** {result['founder'].get('location', '')}")
                    
                    st.subheader("Company Information")
                    st.write(f"**Company:** {result['company'].get('name', '')}")
                    # st.write(f"**Website:** {result['company'].get('website', '')}")
                    
                    st.subheader("Company Summary")
                    st.info(result['summary'])
                    
                    st.subheader("Personalized LinkedIn Message")
                    message_box = st.text_area("Ready to copy and paste:", value=result['message'], height=150)
                    
                    # Simple character counter
                    character_count = len(result['message'])
                    character_limit = 500
                    st.progress(min(character_count / character_limit, 1.0))
                    st.write(f"{character_count}/{character_limit} characters")
                else:
                    st.error("Failed to process profile. Check logs for details.")
            else:
                st.warning("Please enter a LinkedIn Profile URL.")
    
    # Batch Processing Tab
    with tabs[1]:
        st.header("Process Multiple LinkedIn Profiles")
        
        st.info("Enter up to 5 LinkedIn profile URLs (one per line). Batch processing may take some time.")
        
        batch_urls = st.text_area("Enter LinkedIn Profile URLs (one per line, max 5):", height=150)
        
        col1, col2 = st.columns(2)
        with col1:
            process_batch = st.button("Process Batch")
        with col2:
            clear_results = st.button("Clear Results")
        
        # Parse URLs
        if process_batch:
            profile_urls = [url.strip() for url in batch_urls.split('\n') if url.strip()]
            
            if not profile_urls:
                st.warning("Please enter at least one LinkedIn profile URL.")
            elif len(profile_urls) > 5:
                st.error("You can process a maximum of 10 profiles at once. Please reduce the number of URLs.")
            else:
                st.session_state.batch_processing = True
                st.session_state.batch_results = []
                st.session_state.processed_count = 0
                st.session_state.total_to_process = len(profile_urls)
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Process each URL
                for i, url in enumerate(profile_urls):
                    status_text.text(f"Processing profile {i+1}/{len(profile_urls)}: {url}")
                    
                    try:
                        result = pipeline.process_single_profile_with_scraper(url, linkedin_scraper)
                        if result:
                            st.session_state.batch_results.append({
                                "url": url,
                                "name": result['founder'].get('full_name', ''),
                                "company": result['company'].get('name', ''),
                                "message": result['message'],
                                "status": "success"
                            })
                        else:
                            st.session_state.batch_results.append({
                                "url": url,
                                "name": "N/A",
                                "company": "N/A",
                                "message": "",
                                "status": "failed"
                            })
                    except Exception as e:
                        st.session_state.batch_results.append({
                            "url": url,
                            "name": "N/A",
                            "company": "N/A",
                            "message": f"Error: {str(e)}",
                            "status": "error"
                        })
                    
                    # Update progress
                    st.session_state.processed_count += 1
                    progress_bar.progress(st.session_state.processed_count / len(profile_urls))
                    
                    # Add a small delay between profiles to prevent rate limiting
                    time.sleep(random.uniform(2, 4))
                
                status_text.text("Batch processing complete!")
                st.session_state.batch_processing = False
        
        if clear_results:
            st.session_state.batch_results = []
            st.session_state.processed_count = 0
            st.session_state.total_to_process = 0
            st.session_state.batch_processing = False
        
        # Display batch results
        if st.session_state.batch_results:
            st.subheader("Batch Processing Results")
            
            # Summary stats
            success_count = sum(1 for r in st.session_state.batch_results if r["status"] == "success")
            failed_count = len(st.session_state.batch_results) - success_count
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Successful", success_count)
            with col2:
                st.metric("Failed", failed_count)
            
            result_df = pd.DataFrame(st.session_state.batch_results)
            st.dataframe(result_df[["url", "name", "company", "status"]])
            
            for i, result in enumerate(st.session_state.batch_results):
                if result["status"] == "success":
                    with st.expander(f"{result['name']} ({result['company']})"):
                        st.text_area(f"Message for {result['name']}", 
                                    value=result['message'],
                                    height=100,
                                    key=f"batch_message_{i}")
    
    # History Tab
    with tabs[2]:
        st.header("Generated Messages History")
        
        if st.button("Export to CSV"):
            with st.spinner("Exporting messages..."):
                if db_ops.export_messages_to_csv():
                    st.success("Messages exported to linkedin_messages.csv")
                else:
                    st.error("Error exporting messages. Check logs.")
        
        messages = db_ops.get_all_messages()
        if messages:
            # Create a DataFrame and display it
            messages_df = pd.DataFrame(messages)
            
            st.dataframe(
                messages_df,
                column_config={
                    "full_name": "Name",
                    "company_name": "Company",
                    "linkedin_url": st.column_config.LinkColumn("Profile URL"),
                    "message_text": "Message",
                    "generated_date": st.column_config.DatetimeColumn(
                        "Generated On",
                        format="MM/DD/YYYY, HH:mm"
                    ),
            
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No messages generated yet.")

    # Simple footer
    st.markdown("---")
    st.caption("LinkedIn Personalization | Built with Streamlit")