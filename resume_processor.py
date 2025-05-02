import os
import fitz  # PyMuPDF for PDF processing
import logging
import json
import google.generativeai as genai
from datetime import datetime

logger = logging.getLogger(__name__)

class ResumeProcessor:
    def __init__(self, config):
        """
        Initialize the ResumeProcessor with Gemini Vision API for PDF extraction.
        
        Args:
            config: Configuration object containing API keys
        """
        self.config = config
        if not hasattr(config, 'gemini_api_key') or not config.gemini_api_key:
            logger.error("Gemini API key not found in config during ResumeProcessor initialization.")
            raise ValueError("Gemini API key is required for ResumeProcessor.")
        
        try:
            genai.configure(api_key=config.gemini_api_key)
            self.vision_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("ResumeProcessor initialized with Gemini model.")
        except Exception as e:
            logger.error(f"Failed to configure Gemini or initialize model for resume processing: {e}")
            raise RuntimeError(f"Failed to initialize Gemini for resume processing: {e}") from e
        
        # Create upload directory if it doesn't exist
        self.upload_dir = os.path.join(os.getcwd(), "resume_uploads")
        if not os.path.exists(self.upload_dir):
            os.makedirs(self.upload_dir)
            logger.info(f"Created resume upload directory: {self.upload_dir}")

    def process_resume(self, file_path):
        """
        Process a PDF resume using Gemini Vision API.
        
        Args:
            file_path: Path to the uploaded PDF resume
            
        Returns:
            Dictionary containing extracted resume data
        """
        logger.info(f"Processing resume: {file_path}")
        
        try:
            # Extract images from PDF pages
            resume_images = self._extract_images_from_pdf(file_path)
            if not resume_images:
                logger.error(f"Failed to extract images from PDF: {file_path}")
                return None
            
            # Process each page with Gemini Vision API
            resume_data = self._extract_data_from_images(resume_images)
            
            # Clean up temporary images
            for img_path in resume_images:
                try:
                    os.remove(img_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary image {img_path}: {e}")
            
            if resume_data:
                logger.info("Successfully extracted resume data")
                # Add processing timestamp
                resume_data['processed_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                resume_data['source_file'] = os.path.basename(file_path)
                return resume_data
            else:
                logger.error("Failed to extract data from resume")
                return None
                
        except Exception as e:
            logger.exception(f"Error processing resume {file_path}: {e}")
            return None

    def _extract_images_from_pdf(self, pdf_path):
        """
        Extract images from each page of the PDF for processing.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of paths to extracted page images
        """
        try:
            logger.info(f"Extracting images from PDF: {pdf_path}")
            pdf_document = fitz.open(pdf_path)
            image_paths = []
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                
                # Render page to image with high resolution
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                
                # Save the image
                image_path = os.path.join(
                    self.upload_dir, 
                    f"resume_page_{os.path.basename(pdf_path)}_{page_num}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                )
                pix.save(image_path)
                image_paths.append(image_path)
                logger.debug(f"Extracted page {page_num+1} to {image_path}")
            
            pdf_document.close()
            logger.info(f"Extracted {len(image_paths)} pages from PDF")
            return image_paths
            
        except Exception as e:
            logger.exception(f"Error extracting images from PDF {pdf_path}: {e}")
            return []

    def _extract_data_from_images(self, image_paths):
        """
        Use Gemini Vision API to extract structured data from resume images.
        
        Args:
            image_paths: List of paths to resume page images
            
        Returns:
            Dictionary containing structured resume data
        """
        if not image_paths:
            return None
        
        try:
            # Prepare images for Gemini
            images = []
            for path in image_paths:
                with open(path, "rb") as f:
                    image_bytes = f.read()
                    images.append({
                        'mime_type': 'image/png',
                        'data': image_bytes
                    })
            
            # Construct the prompt for data extraction
            prompt = """
            Analyze this resume PDF and extract the following information in JSON format:
            
            1. basic_info:
               - full_name: The candidate's full name
               - email: Email address
               - phone: Phone number
               - location: Current location
               - linkedin_url: LinkedIn profile URL if present
            
            2. summary: A brief professional summary/objective statement
            
            3. skills:
               - technical_skills: List of technical skills (programming languages, tools, platforms)
               - soft_skills: List of soft skills (communication, leadership, etc.)
               
            4. experience:
               - List of work experiences, each containing:
                 - company: Company name
                 - title: Job title
                 - duration: Employment period
                 - description: Key responsibilities and achievements (as bullet points)
            
            5. education:
               - List of educational qualifications, each containing:
                 - institution: School/University name
                 - degree: Degree obtained
                 - field: Field of study
                 - graduation_date: When they graduated
            
            6. certifications: List of professional certifications
            
            7. projects:
               - List of notable projects, each containing:
                 - name: Project name
                 - description: Brief description
                 - technologies: Technologies used
            
            Extract only what's explicitly mentioned in the resume. If a section is missing, return an empty list or null for that section.
            
            Format the output as a clean, well-structured JSON object without any markdown formatting or extra explanations.
            """
            
            # Process with Gemini Vision API
            logger.info("Sending resume to Gemini Vision API for analysis...")
            
            # For multiple pages, create one request with all images
            content = [prompt] + images
            response = self.vision_model.generate_content(content)
            
            if not response or not hasattr(response, 'text'):
                logger.error("Invalid or empty response from Gemini Vision API")
                return None
                
            # Extract and parse JSON from response
            extracted_text = response.text.strip()
            logger.debug(f"Raw response length from Gemini: {len(extracted_text)}")
            
            # Clean potential markdown code block fences
            if "```json" in extracted_text:
                extracted_text = extracted_text.split("```json")[1]
            if "```" in extracted_text:
                extracted_text = extracted_text.split("```")[0]
            extracted_text = extracted_text.strip()
            
            # Parse the JSON
            resume_data = json.loads(extracted_text)
            
            # Validate essential fields
            if not isinstance(resume_data, dict):
                logger.error("Parsed resume data is not a dictionary")
                return None
                
            # Ensure expected sections exist
            resume_data.setdefault('basic_info', {})
            resume_data.setdefault('skills', {})
            resume_data.setdefault('experience', [])
            resume_data.setdefault('education', [])
            
            logger.info("Successfully extracted and parsed resume data")
            return resume_data
            
        except Exception as e:
            logger.exception(f"Error extracting data from resume images: {e}")
            return None

    def get_tech_stack_summary(self, resume_data):
        """
        Extract and summarize the technical skills from resume data.
        
        Args:
            resume_data: Dictionary containing parsed resume data
            
        Returns:
            String containing a summary of technical skills and experience
        """
        if not resume_data:
            return ""
            
        try:
            # Extract skills
            technical_skills = resume_data.get('skills', {}).get('technical_skills', [])
            
            # Get most recent experience
            experiences = resume_data.get('experience', [])
            recent_experience = experiences[0] if experiences else {}
            
            # Extract education
            education = resume_data.get('education', [])
            recent_education = education[0] if education else {}
            
            # Create a concise summary
            tech_stack_summary = []
            
            # Add technical skills
            if technical_skills:
                if isinstance(technical_skills, list):
                    tech_stack_summary.append(f"Technical skills: {', '.join(technical_skills)}")
                elif isinstance(technical_skills, str):
                    tech_stack_summary.append(f"Technical skills: {technical_skills}")
            
            # Add recent role
            if recent_experience:
                company = recent_experience.get('company', '')
                title = recent_experience.get('title', '')
                if company and title:
                    tech_stack_summary.append(f"Recent role: {title} at {company}")
            
            # Add education
            if recent_education:
                degree = recent_education.get('degree', '')
                field = recent_education.get('field', '')
                institution = recent_education.get('institution', '')
                if degree and institution:
                    education_str = f"Education: {degree}"
                    if field:
                        education_str += f" in {field}"
                    education_str += f" from {institution}"
                    tech_stack_summary.append(education_str)
            
            return "\n".join(tech_stack_summary)
        
        except Exception as e:
            logger.error(f"Error generating tech stack summary: {e}")
            return ""