import streamlit as st
import main  
import pandas as pd
import random
import time

st.set_page_config(page_title="LinkedIn Hyper-Personalized Outreach", page_icon="🔗", layout="wide")

# Add a more visually appealing header with columns
col1, col2 = st.columns([1, 3])
with col1:
    st.image("https://cdn-icons-png.flaticon.com/512/174/174857.png", width=100)
with col2:
    st.title("LinkedIn Hyper-Personalized Outreach")
    st.caption("Process LinkedIn profiles and generate hyper-personalized outreach messages")

st.markdown("""
<style>
    .main-header {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

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
        
        # Initialize session state for tracking deleted profiles
        if 'deleted_profiles' not in st.session_state:
            st.session_state.deleted_profiles = set()
        
        # Check for deletion action from previous interaction
        if 'delete_message_id' in st.session_state:
            msg_id = st.session_state.delete_message_id
            name = st.session_state.delete_name
            if db_ops.delete_profile(int(msg_id)):
                st.success(f"Profile for {name} deleted successfully!")
                # Remove from session state
                if msg_id in st.session_state.sent_messages:
                    del st.session_state.sent_messages[msg_id]
                # Add to deleted profiles set (as a backup)
                st.session_state.deleted_profiles.add(str(msg_id))
            else:
                st.error("Failed to delete profile. See logs for details.")
            
            # Clear the deletion state
            del st.session_state.delete_message_id
            del st.session_state.delete_name
            
            # Re-fetch messages after deletion
            messages = db_ops.get_all_messages()
        else:
            # Normal flow - fetch all messages
            messages = db_ops.get_all_messages()
        
        if messages:
            # Initialize session state for tracking sent messages if not exists
            if 'sent_messages' not in st.session_state:
                st.session_state.sent_messages = {}
            
            # Create a DataFrame and display it
            messages_df = pd.DataFrame(messages)
            
            # Add message_id column if not present for tracking
            if 'id' not in messages_df.columns:
                messages_df['id'] = messages_df.index.astype(str)
            
            # Create a temporary dataframe with sent status for display
            display_df = messages_df.copy()
            display_df['sent'] = False
            
            # Update with session state values
            for idx, row in display_df.iterrows():
                msg_id = str(row.get('id', idx))
                if msg_id in st.session_state.sent_messages:
                    display_df.at[idx, 'sent'] = st.session_state.sent_messages[msg_id]
            
            # Show each message with a checkbox
            st.subheader("Track Your Outreach")
            st.caption("Check the box once you've sent the message")
            
            delete_occurred = False
            
            # Iterate through a copy to avoid modification issues during iteration
            for idx, row in display_df.iterrows():
                msg_id = str(row.get('id', idx))
                
                # Skip if this profile has been marked for deletion
                if (msg_id in st.session_state.deleted_profiles or 
                    ('pending_delete' in st.session_state and msg_id == st.session_state.pending_delete)):
                    continue
                
                name = row.get('full_name', 'Unknown')
                company = row.get('company_name', 'Unknown')
                
                col1, col2, col3 = st.columns([1, 8, 1])
                with col1:
                    is_sent = st.checkbox(
                        "✓", 
                        value=st.session_state.sent_messages.get(msg_id, False),
                        key=f"sent_{msg_id}",
                        help="Mark as sent"
                    )
                    # Update session state when checkbox changes
                    st.session_state.sent_messages[msg_id] = is_sent
                    # Update display dataframe
                    display_df.at[idx, 'sent'] = is_sent
                
                with col2:
                    st.markdown(f"**{name}** - {company}")
                
                with col3:
                    # Add delete button with immediate visual feedback
                    if st.button("🗑️", key=f"delete_{msg_id}", help="Delete this profile"):
                        # Mark for immediate deletion in UI
                        st.session_state.pending_delete = msg_id
                        # Store for actual database operation in next run
                        st.session_state.delete_message_id = msg_id
                        st.session_state.delete_name = name
                        # Also add to our persistent deleted set
                        st.session_state.deleted_profiles.add(msg_id)
                        delete_occurred = True
            
            # If a deletion occurred, rerun to update UI immediately
            if delete_occurred:
                st.rerun()
            
            # Generate CSV for download including sent status
            @st.cache_data
            def convert_df_to_csv(df):
                return df.to_csv(index=False).encode('utf-8')
            
            # Add sent status to the export
            export_df = messages_df.copy()
            export_df['message_sent'] = False
            
            # Update with session state values for export
            for idx, row in export_df.iterrows():
                msg_id = str(row.get('id', idx))
                if msg_id in st.session_state.sent_messages:
                    export_df.at[idx, 'message_sent'] = st.session_state.sent_messages[msg_id]
            
            csv_data = convert_df_to_csv(export_df)
            
            # Add download button
            st.download_button(
                label="📥 Download as CSV (Includes Sent Status)",
                data=csv_data,
                file_name="linkedin_messages.csv",
                mime="text/csv",
                help="Click to download all messages as a CSV file with sent status"
            )
            
            # Standard table view of all messages
            st.subheader("All Messages")
            st.dataframe(
                display_df,
                column_config={
                    "full_name": "Name",
                    "company_name": "Company",
                    "linkedin_url": st.column_config.LinkColumn("Profile URL"),
                    "message_text": "Message",
                    "generated_date": st.column_config.DatetimeColumn(
                        "Generated On",
                        format="MM/DD/YYYY, HH:mm"
                    ),
                    "sent": st.column_config.CheckboxColumn("Sent ✓")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No messages generated yet.")

    # Simple footer
    st.markdown("---")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("""
        <div style='text-align: center; color: #888888;'>
            <p>LinkedIn Personalization Tool | Built with ❤️ using Streamlit</p>
        </div>
        """, unsafe_allow_html=True)