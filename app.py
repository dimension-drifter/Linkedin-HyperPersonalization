import streamlit as st
import main  # Import your main script
import pandas as pd

# Page configuration
st.set_page_config(page_title="LinkedIn Outreach Tool", page_icon="🔗", layout="wide")

# App title and description
st.title("LinkedIn Outreach Tool")
st.markdown("Process LinkedIn profiles to generate personalized outreach messages")

# Initialize session state to track login status
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    
# --- Initialize Pipeline and LinkedInScraper OUTSIDE button logic ---
@st.cache_resource
def get_pipeline_and_scraper():
    pipeline = main.LinkedInOutreachPipeline()
    db_ops = main.DatabaseOps()
    linkedin_scraper = main.LinkedInScraper(pipeline.config)
    return pipeline, db_ops, linkedin_scraper

pipeline, db_ops, linkedin_scraper = get_pipeline_and_scraper()

# Login section
if not st.session_state.logged_in:
    with st.spinner("Logging in to LinkedIn... (This may take a moment)"):
        login_success = linkedin_scraper.login_to_linkedin()
        if login_success:
            st.session_state.logged_in = True
            st.success("Successfully logged into LinkedIn!")
        else:
            st.error("Failed to login to LinkedIn. Please check your credentials in the .env file.")

# Profile processing UI
if st.session_state.logged_in:
    linkedin_profile_url = st.text_input("Enter LinkedIn Profile URL:")
    
    if st.button("Process Profile"):
        if linkedin_profile_url:
            with st.spinner("Processing profile..."):
                # Use the already logged-in scraper instance
                # Modify process_single_profile_with_scraper to skip login
                result = pipeline.process_single_profile_with_scraper(linkedin_profile_url, linkedin_scraper)
            if result:
                st.success("Profile processed successfully!")
                
                # Display founder information
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Founder Information")
                    st.write(f"**Name:** {result['founder'].get('full_name', '')}")
                    st.write(f"**Headline:** {result['founder'].get('headline', '')}")
                    st.write(f"**Location:** {result['founder'].get('location', '')}")
                
                with col2:
                    st.subheader("Company Information")
                    st.write(f"**Company:** {result['company'].get('name', '')}")
                    st.write(f"**Website:** {result['company'].get('website', '')}")
                
                st.subheader("Company Summary")
                st.info(result['summary'])
                
                st.subheader("Personalized LinkedIn Message")
                message_box = st.text_area("Ready to copy and paste:", value=result['message'], height=150)
                st.caption(f"Character count: {len(result['message'])} (LinkedIn limit: 300 for first message)")
            else:
                st.error("Failed to process profile. Check logs for details.")
        else:
            st.warning("Please enter a LinkedIn Profile URL.")
    
    st.markdown("---")
    st.subheader("Generated Messages History")
    
    messages = db_ops.get_all_messages()
    if messages:
        messages_df = pd.DataFrame(messages)
        st.dataframe(messages_df)
    else:
        st.info("No messages generated yet.")
    
    if st.button("Export Messages to CSV"):
        with st.spinner("Exporting messages..."):
            if db_ops.export_messages_to_csv():
                st.success("Messages exported to linkedin_messages.csv")
            else:
                st.error("Error exporting messages. Check logs.")