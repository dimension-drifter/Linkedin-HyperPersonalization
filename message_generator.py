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
             logger.error(f"Failed to configure Gemini or initialize model: {e}")
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
                news_summary = "Recent news:\n" + "\n".join([f"- {article['title']}" for article in company_data['news']])

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

    def _shorten_message(self, message, target_length, context_name, context_company):
        """Internal helper to shorten a message using Gemini."""
        if len(message) <= target_length:
            return message

        logger.warning(f"Generated message exceeded {target_length} characters ({len(message)}). Attempting to shorten.")
        shorten_prompt = f"""
        Shorten the following message to be under {target_length} characters, while retaining the core personalization about {context_name} and {context_company}. Keep it professional and concise.

        Original Message:
        {message}
        """
        try:
            response = self.generation_model.generate_content(shorten_prompt)
            if response and hasattr(response, 'text'):
                 shortened = response.text.strip()
                 logger.info(f"Shortened message length: {len(shortened)}")
                 # Final check and truncate if shortening failed to meet target
                 if len(shortened) > target_length:
                     logger.warning(f"Shortening attempt still exceeded limit ({len(shortened)}). Truncating.")
                     return shortened[:target_length-3] + "..."
                 return shortened
            else:
                 logger.error("Failed to shorten the message via API.")
                 # Fallback: Truncate harshly if shortening fails
                 return message[:target_length-3] + "..."
        except Exception as e:
            logger.error(f"Error during message shortening API call: {e}")
            return message[:target_length-3] + "..." # Fallback

    def generate_connection_request(self, founder_data, company_summary, resume_data=None):
        """Generate a personalized LinkedIn connection request message (under 300 chars) with resume data."""
        try:
            founder_name = founder_data.get('full_name', '').split()[0] if founder_data.get('full_name') else 'there'
            company_name = founder_data.get('primary_company', {}).get('name', 'their company')
            
            # Create resume context if available
            resume_context = ""
            if resume_data:
                # Extract relevant information from resume
                basic_info = resume_data.get('basic_info', {})
                user_name = basic_info.get('full_name', '')
                
                skills = resume_data.get('skills', {})
                tech_skills = skills.get('technical_skills', [])
                if isinstance(tech_skills, list):
                    tech_skills = ', '.join(tech_skills[:5])  # Limit to top 5 skills
                    
                recent_experience = None
                if resume_data.get('experience') and len(resume_data['experience']) > 0:
                    recent_experience = resume_data['experience'][0]
                
                # Build context string
                resume_context = f"""
                User's Resume Information:
                Name: {user_name}
                Key Technical Skills: {tech_skills}
                """
                
                if recent_experience:
                    resume_context += f"""
                    Recent Role: {recent_experience.get('title', '')} at {recent_experience.get('company', '')}
                    """

            # Enhanced prompt with resume data
            prompt = f"""
            **Objective:** Generate a **highly personalized and concise** LinkedIn connection request message (strictly under 400 characters) to {founder_name}, the leader of {company_name}. The message must demonstrate genuine interest based on a *specific* detail from the provided summary.

            **Sender Information:**
            {resume_context}

            **Recipient:** {founder_name}
            **Recipient's Company:** {company_name}

            **Detailed Founder & Company Summary (Source for Personalization):**
            --- START SUMMARY ---
            {company_summary}
            --- END SUMMARY ---

            **Instructions:**
            1. **Identify Common Ground:** Find a specific connection point between the sender's background/skills and the recipient's company/work.
            2. **Draft Message:**
               * Start warmly: "Hi {founder_name},"
               * Briefly mention specific relevant experience/skill from the sender's background that relates to {company_name}'s work.
               * Reference something specific about their company that connects to your background.
               * End with a simple call to connect.
            3. **Constraint Checklist:**
               * Strictly under 300 characters (critical LinkedIn limitation).
               * Mentions both {founder_name} and your own relevant background.
               * References a *specific* detail from the recipient's company.
               * Professional, genuine, and personalized tone.

            **Generate the connection request message now.**
            """

            response = self.generation_model.generate_content(prompt)
            if not response or not hasattr(response, 'text'):
                logger.error("Invalid response received from Gemini API during connection request generation.")
                raise ValueError("Invalid response from Gemini API.")
            message = response.text.strip()

            # Shorten if needed (target 300 chars for connection requests)
            message = self._shorten_message(message, 400, founder_name, company_name)

            return message

        except Exception as e:
            logger.error(f"Error generating connection request message: {str(e)}", exc_info=True)
            fallback_name = founder_data.get('full_name', 'there')
            return f"Hi {fallback_name}, saw your profile and work. Would be great to connect." # Shorter fallback

    def generate_job_inquiry(self, founder_data, company_summary, user_tech_stack="", resume_data=None):
        """Generate a personalized message inquiring about roles with resume data."""
        try:
            founder_name = founder_data.get('full_name', '').split()[0] if founder_data.get('full_name') else 'there'
            company_name = founder_data.get('primary_company', {}).get('name', 'their company')
            
            # Use resume data if available, otherwise fall back to tech stack string
            detailed_background = ""
            
            if resume_data:
                # Extract relevant details from resume
                basic_info = resume_data.get('basic_info', {})
                user_name = basic_info.get('full_name', '')
                
                # Get skills
                skills_section = []
                tech_skills = resume_data.get('skills', {}).get('technical_skills', [])
                if tech_skills:
                    if isinstance(tech_skills, list):
                        skills_section.append(f"Technical skills: {', '.join(tech_skills)}")
                    else:
                        skills_section.append(f"Technical skills: {tech_skills}")
                        
                soft_skills = resume_data.get('skills', {}).get('soft_skills', [])
                if soft_skills:
                    if isinstance(soft_skills, list) and soft_skills:
                        skills_section.append(f"Soft skills: {', '.join(soft_skills[:3])}")
                    elif isinstance(soft_skills, str):
                        skills_section.append(f"Soft skills: {soft_skills}")
                
                # Get experience
                experience_section = []
                experiences = resume_data.get('experience', [])
                if experiences:
                    for i, exp in enumerate(experiences[:2]):  # Get top 2 experiences
                        exp_line = f"- {exp.get('title', '')} at {exp.get('company', '')}"
                        if exp.get('duration'):
                            exp_line += f" ({exp.get('duration', '')})"
                        experience_section.append(exp_line)
                
                # Get education
                education_section = []
                education = resume_data.get('education', [])
                if education:
                    for edu in education[:1]:  # Get top education
                        edu_line = f"- {edu.get('degree', '')} in {edu.get('field', '')}"
                        if edu.get('institution'):
                            edu_line += f" from {edu.get('institution', '')}"
                        education_section.append(edu_line)
                
                # Build detailed background
                detailed_background = f"""
                User's Name: {user_name}
                
                Skills:
                {chr(10).join(skills_section)}
                
                Key Experience:
                {chr(10).join(experience_section)}
                
                Education:
                {chr(10).join(education_section)}
                """
            else:
                # Fall back to tech stack string if no resume
                detailed_background = f"User's tech stack/background: {user_tech_stack}"

            # Enhanced prompt with resume data
            prompt = f"""
            **Objective:** Generate a personalized and professional LinkedIn message (around 800-1200 characters) to {founder_name} of {company_name}. Assume you are already connected. The goal is to express genuine interest in the company based on their work and inquire about potential opportunities relevant to the user's background.

            **Recipient:** {founder_name}
            **Recipient's Company:** {company_name}

            **User's Detailed Background:**
            {detailed_background}

            **Detailed Founder & Company Summary (Source for Personalization):**
            --- START SUMMARY ---
            {company_summary}
            --- END SUMMARY ---

            **Instructions:**
            1. **Reference Connection:** Briefly mention connecting previously or following their work.
            2. **Highlight Relevant Experience:** Reference 1-2 specific experiences or skills from the user's background that align well with {company_name}'s work. Be specific about why these experiences would be valuable to their company.
            3. **Demonstrate Company Knowledge:** Reference a *specific* aspect of the company's work or mission that connects to the user's experience.
            4. **Express Interest in Opportunities:** Clearly state interest in exploring potential roles that align with the user's skills.
            5. **Call to Action:** Ask politely about potential openings or who the appropriate contact might be.
            6. **Tone:** Professional, enthusiastic, and authentically personal.

            **Generate the personalized job inquiry message now.**
            """

            response = self.generation_model.generate_content(prompt)
            if not response or not hasattr(response, 'text'):
                logger.error("Invalid response received from Gemini API during job inquiry generation.")
                raise ValueError("Invalid response from Gemini API.")
            message = response.text.strip()

            # Shorten if needed
            message = self._shorten_message(message, 2500, founder_name, company_name)

            return message

        except Exception as e:
            logger.error(f"Error generating job inquiry message: {str(e)}", exc_info=True)
            fallback_name = founder_data.get('full_name', 'there')
            fallback_company = company_name or 'your company'
            return f"Hi {fallback_name}, following up on our connection. I'm impressed with {fallback_company}'s work. With my background in {user_tech_stack}, I'm interested in exploring potential opportunities. Could you advise on the best way to learn more? Thanks." # Fallback