# filepath: c:\Users\deepa\OneDrive\Desktop\Dee\ML Projects\Linkedin tool\message_generator.py
import os
import json
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

class MessageGenerator:
    def __init__(self, config):
        """
        Initializes the MessageGenerator.

        Args:
            config: A configuration object containing necessary settings like API keys.
                    Expected to have 'gemini_api_key'.
        """
        self.config = config
        if not self.config or not hasattr(self.config, 'gemini_api_key') or not self.config.gemini_api_key:
             logger.error("Gemini API key not found in config during MessageGenerator initialization.")
             raise ValueError("Gemini API key is required for MessageGenerator.")

        # Configure Gemini if not already done (safe to call multiple times)
        try:
            genai.configure(api_key=self.config.gemini_api_key)
            # Consider using a specific model if needed, e.g., 'gemini-1.5-flash'
            self.generation_model = genai.GenerativeModel('gemini-1.5-flash') # Updated model name
            logger.info("MessageGenerator initialized with Gemini model.")
        except Exception as e:
             logger.error(f"Failed to configuwritere Gemini or initialize model: {e}")
             raise RuntimeError(f"Failed to initialize Gemini: {e}") from e

    def summarize_company_data(self, founder_data, company_data):
        """Summarize all the data we have about the founder and company using Gemini"""
        try:
            # Create a comprehensive founder summary with all available data
            founder_summary = {
                'name': founder_data.get('full_name', ''),
                'headline': founder_data.get('headline', ''),
                'summary': founder_data.get('summary', ''),
                'location': founder_data.get('location', ''),
                'primary_company': founder_data.get('primary_company', {}).get('name', ''),
                'primary_title': founder_data.get('primary_company', {}).get('title', '')
            }

            # Include education if available
            if 'education' in founder_data and founder_data['education']:
                founder_summary['education'] = [
                    f"{edu.get('degree', '')} from {edu.get('institution', '')}"
                    for edu in founder_data['education']
                ]

            # Include all experience details
            if 'experiences' in founder_data and founder_data['experiences']:
                founder_summary['experiences'] = [
                    f"{exp.get('title', '')} at {exp.get('company', '')}"
                    for exp in founder_data['experiences'][:3]  # Limit to top 3
                ]

            company_summary_data = {
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

            # New ultra-detailed prompt for Gemini Flash
            prompt = f"""
                **Deep Founder & Company Master Profile Summary for Ultra-Personalized Outreach**

                **Objective:** Using the comprehensive dataset provided, generate an in-depth and data-rich profile that captures every dimension of the founder and their company. The output must be used as the basis for crafting a hyper-personalized LinkedIn outreach message.

                **Input Data:**

                * **Founder Profile Data:** {json.dumps(founder_summary, indent=2)}
                  - Data includes full name, headline, detailed summary, location, educational background, top 3 significant experiences, awards and recognitions, and any unique personal attributes.
                * **Company Data:** {json.dumps(company_summary_data, indent=2)}
                  - Data includes company name, a full description, website URL, core product/service, industry positioning, competitive advantages, and any quantifiable business achievements.
                * **Supplementary Insights:** {news_summary}
                  - Contains recent news articles and relevant market signals, including social media sentiment and strategic partnerships.

                **Data Points to Emphasize:**
                1. **Founder’s Detailed Biography & Achievements:**
                   - Chronicle the founder’s career journey including key milestones, quantifiable successes (e.g., revenue growth, team leadership, technological breakthroughs), and personal awards.
                   - Highlight educational achievements, pivotal career shifts, and unique personal traits or interests.
                2. **Comprehensive Company Overview:**
                   - Clearly define the company’s core mission, value proposition, and the problem it solves.
                   - Include innovative aspects such as patent-pending technology, disruptive business model, or market positioning that sets it apart.
                   - Integrate any quantifiable metrics (e.g., funding raised, growth rates) and recent notable developments.
                3. **Synergistic Dynamics:**
                   - Identify unique intersections between the founder’s expertise and the company’s strategic direction.
                   - Detect subtle but significant details that would serve as conversation starters, such as niche industry insights or non-obvious achievements.
                4. **Data Enrichment:**
                   - Leverage every data element provided to ensure the summary is rich in context, factual details, and actionable insights.

                **Output Requirements:**
                - The summary must be highly detailed yet remain within a comprehensive 450-word limit.
                - It should be actionable, fact-based, and structured into clear segments explaining the founder’s journey and the company’s value proposition.
                - The tone must be professional, insightful, and tailored for immediately creating a personalized LinkedIn outreach message.

                **Generate the comprehensive, multi-dimensional founder and company profile summary now, ensuring maximum data enrichment for ultra-personalized outreach.**
                """

            response = self.generation_model.generate_content(prompt)
            # Add basic error handling for response
            if not response or not hasattr(response, 'text'):
                 logger.error("Invalid response received from Gemini API during summarization.")
                 raise ValueError("Invalid response from Gemini API.")
            return response.text

        except Exception as e:
            logger.error(f"Error summarizing company data: {str(e)}", exc_info=True)
            # Provide a more informative fallback
            return f"Summary Error: Could not generate summary for {founder_data.get('full_name', 'founder')} at {company_data.get('name', 'company')}."

    def generate_personalized_message(self, founder_data, company_summary):
        """Generate a personalized outreach message using Gemini"""
        try:
            founder_name = founder_data.get('full_name', '').split()[0] if founder_data.get('full_name') else 'there' # Get first name or fallback
            company_name = founder_data.get('primary_company', {}).get('name', 'their company')


            prompt = f"""
            **Objective:** Generate a **highly personalized and insightful** LinkedIn connection request message (strictly under 600 characters) to {founder_name}, the leader of {company_name}. The message must demonstrate genuine interest based on specific details from the provided summary.

            **Sender Persona (Implicit):** Assume the sender has a background or strong interest relevant to the founder's industry or technology (e.g., ML/AI, business strategy, specific market sector). Frame the connection point from this perspective.

            **Core Task:** Synthesize the provided summary to extract **unique, non-obvious points of resonance** or **specific achievements/challenges** that genuinely capture the sender's interest. Avoid surface-level observations.

            **Recipient:** {founder_name}
            **Recipient's Company:** {company_name}

            **Detailed Founder & Company Summary (Source for Deep Personalization):**
            --- START SUMMARY ---
            {company_summary}
            --- END SUMMARY ---

            **Instructions for Message Generation:**

            1.  **Deep Analysis:** Scrutinize the entire summary. Look beyond headlines for specific projects, unique approaches, stated values, career pivots, recent milestones, or challenges mentioned.
            2.  **Identify Unique Hook:** Pinpoint 1 (maximum 2) **specific and compelling detail** that stands out. Ask yourself: "What detail is least likely to be mentioned by others?" or "What connects most strongly to the sender's assumed background/interest?"
            3.  **Establish Relevance (Crucial):** Briefly explain *why* this specific detail caught your attention, connecting it implicitly or explicitly to the sender's persona/interest (e.g., "As someone focused on [Sender's Area], I was particularly interested in your approach to [Specific Detail]...").
            4.  **Draft Message:**
                *   Start warmly and professionally: "Hi {founder_name},"
                *   Immediately reference the **specific unique hook** identified. (e.g., "I read the summary about your work at {company_name} and was fascinated by the mention of [Specific Detail from Summary]..." or "Your perspective on [Specific Topic from Summary] really resonated...")
                *   Briefly state the **relevance** or the connection to the sender's interest.
                *   Express a clear, concise, and genuine call to action (e.g., "Would love to connect and follow your journey," "Interested to learn more about your work in this area," "Hope to connect.").
                *   Maintain a respectful, curious, and concise tone throughout.
            5.  **Constraint Checklist:**
                *   Strictly under 600 characters.
                *   Mentions {founder_name} by name.
                *   References a *specific* detail from the `{company_summary}`.
                *   Implies or states sender relevance/interest.
                *   Professional, genuine, and curious tone.

            **What to AVOID:**
            *   Generic praise ("Great work!", "Impressed by your company").
            *   Simply stating the company name or founder's title without a specific hook.
            *   Vague interest ("Interested in your industry").
            *   Anything that sounds like a template.
            *   Exceeding the character limit.

            **Enhanced Example Structure:**
            "Hi {founder_name}, I came across the summary detailing your journey with {company_name}. As someone working in [Sender's Field, e.g., scalable AI systems], I was particularly struck by your team's approach to [Specific Unique Detail from Summary, e.g., implementing federated learning for X]. Would be great to connect and follow how that develops."

            **Generate the hyper-personalized connection request message now, adhering strictly to all instructions and constraints.**
            """

            response = self.generation_model.generate_content(prompt)
            # Add basic error handling for response
            if not response or not hasattr(response, 'text'):
                 logger.error("Invalid response received from Gemini API during message generation.")
                 raise ValueError("Invalid response from Gemini API.")
            message = response.text.strip() # Strip whitespace

            # Check character limit for LinkedIn first messages (600)
            if len(message) > 600:
                logger.warning(f"Generated message exceeded 600 characters ({len(message)}). Attempting to shorten.")
                # Use a simpler prompt for shortening
                shorten_prompt = f"""
                Shorten the following message to be under 600 characters, while retaining the core personalization about {founder_name} and {company_name}. Keep it professional and concise.

                Original Message:
                {message}
                """
                response = self.generation_model.generate_content(shorten_prompt)
                if response and hasattr(response, 'text'):
                     message = response.text.strip()
                     logger.info(f"Shortened message length: {len(message)}")
                else:
                     logger.error("Failed to shorten the message.")
                     # Fallback: Truncate harshly if shortening fails
                     message = message[:595] + "..."


            # Final length check
            if len(message) > 600:
                 logger.warning("Message still too long after shortening attempt. Truncating.")
                 message = message[:595] + "..." # Truncate if still too long

            return message

        except Exception as e:
            logger.error(f"Error generating personalized message: {str(e)}", exc_info=True)
            # Provide a more informative fallback message
            fallback_name = founder_data.get('full_name', 'there')
            fallback_company = company_name or 'your company'
            return f"Hi {fallback_name}, I came across your profile and work at {fallback_company}. I'm interested in learning more about your industry. Would be great to connect."