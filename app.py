import streamlit as st
import main  # Import your main script
import pandas as pd

# --- Initialize Pipeline and LinkedInScraper OUTSIDE button logic ---
pipeline = main.LinkedInOutreachPipeline()
db_ops = main.DatabaseOps()
linkedin_scraper = main.LinkedInScraper(pipeline.config) # Initialize LinkedInScraper here

st.title("LinkedIn Outreach Tool")

linkedin_profile_url = st.text_input("Enter LinkedIn Profile URL:")

if st.button("Process Profile"):
    if linkedin_profile_url:
        with st.spinner("Processing profile..."):
            # Use the PERSISTENT linkedin_scraper instance
            result = pipeline.process_single_profile_with_scraper(linkedin_profile_url, linkedin_scraper) # Modified function call (see main.py changes below)
        if result:
            st.success("Profile processed successfully!")
            # ... (rest of your result display code - founder info, summary, message)
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