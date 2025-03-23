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
            result = pipeline.process_single_profile_with_scraper(linkedin_profile_url, linkedin_scraper)
        
        if result:
            st.success("Profile processed successfully!")
            
            # Display founder information
            st.subheader("Founder Information")
            founder_info = result.get('founder_data', {})
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Name:** {founder_info.get('full_name', 'N/A')}")
                st.write(f"**Location:** {founder_info.get('location', 'N/A')}")
            
            with col2:
                st.write(f"**Headline:** {founder_info.get('headline', 'N/A')}")
            
            if founder_info.get('summary'):
                st.write("**Summary:**")
                st.write(founder_info.get('summary'))
            
            # Display company information
            st.subheader("Company Information")
            company_info = result.get('company_data', {})
            st.write(f"**Company:** {company_info.get('name', 'N/A')}")
            if company_info.get('website'):
                st.write(f"**Website:** {company_info.get('website')}")
            if company_info.get('description'):
                st.write("**Description:**")
                st.write(company_info.get('description'))
                
            # Display the summary
            st.subheader("AI-Generated Summary")
            st.write(result.get('summary', 'No summary generated'))
            
            # Display the generated message in a highlighted box
            st.subheader("Personalized Outreach Message")
            message = result.get('message', 'No message generated')
            # Process the message to properly handle line breaks for HTML
            formatted_message = message.replace('\n', '<br>')
            
            st.markdown(
                f"""<div style="background-color: #f0f2f6; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                {formatted_message}
                </div>
                <p>Character count: {len(message)}</p>""", 
                unsafe_allow_html=True
            )
            
            # Add a copy button
            if st.button("Copy Message to Clipboard"):
                st.code(message, language="")
                st.info("You can now copy the message from the code block above")
                
        else:
            st.error("Failed to process profile. Check logs for details.")
    else:
        st.warning("Please enter a LinkedIn Profile URL.")

st.markdown("---")
st.subheader("Generated Messages History")

messages = db_ops.get_all_messages()
if messages:
    # Format the dataframe for better display
    messages_df = pd.DataFrame(messages)
    
    # Rename columns for better readability
    if 'full_name' in messages_df.columns:
        messages_df = messages_df.rename(columns={
            'full_name': 'Founder Name',
            'company_name': 'Company',
            'message_text': 'Message',
            'generated_date': 'Generated On',
            'was_sent': 'Sent'
        })
        
        # Convert was_sent to Yes/No
        if 'Sent' in messages_df.columns:
            messages_df['Sent'] = messages_df['Sent'].map({1: 'Yes', 0: 'No'})
            
    st.dataframe(messages_df)
    
    # Add ability to view a specific message
    if len(messages) > 0:
        selected_message = st.selectbox(
            "Select message to view:",
            options=range(len(messages)),
            format_func=lambda i: f"{messages[i]['full_name']} - {messages[i]['company_name']}"
        )
        
        if selected_message is not None:
            st.text_area("Full message", messages[selected_message]['message_text'], 
                         height=150, key="selected_message")
else:
    st.info("No messages generated yet.")

if st.button("Export Messages to CSV"):
    with st.spinner("Exporting messages..."):
        if db_ops.export_messages_to_csv():
            st.success("Messages exported to linkedin_messages.csv")
        else:
            st.error("Error exporting messages. Check logs.")