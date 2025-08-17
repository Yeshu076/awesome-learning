import asyncio
import random
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json

from playwright.async_api import async_playwright, Browser, Page, ElementHandle
from fake_useragent import UserAgent
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.job import Job
from app.models.user import User
from app.models.application import JobApplication, Resume
from app.linkedin.scraper import LinkedInJobScraper


class LinkedInJobApplicator:
    """LinkedIn job application automation with form detection"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.user_agent = UserAgent()
        self.session_cookies: Dict = {}
        self.request_count = 0
        self.last_request_time = 0
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize_browser()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        
    async def initialize_browser(self):
        """Initialize browser with anti-detection settings"""
        try:
            playwright = await async_playwright().start()
            
            # Browser launch options for anti-detection
            browser_options = {
                "headless": settings.HEADLESS_BROWSER,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--no-first-run",
                    "--no-zygote",
                    "--disable-gpu",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--window-size=1920,1080"
                ]
            }
            
            self.browser = await playwright.chromium.launch(**browser_options)
            
            # Create context with realistic settings
            context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=self.user_agent.random,
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"]
            )
            
            # Add stealth scripts
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
            """)
            
            self.page = await context.new_page()
            
            # Set additional headers
            await self.page.set_extra_http_headers({
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            })
            
            logger.info("Application browser initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def login_to_linkedin(self, email: str, password: str) -> bool:
        """Login to LinkedIn with anti-detection measures"""
        try:
            logger.info("Starting LinkedIn login process")
            
            # Navigate to LinkedIn login
            await self.page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            await self.human_delay()
            
            # Fill email
            email_input = await self.page.wait_for_selector("#username", timeout=10000)
            await self.human_type(email_input, email)
            await self.human_delay()
            
            # Fill password
            password_input = await self.page.wait_for_selector("#password", timeout=10000)
            await self.human_type(password_input, password)
            await self.human_delay()
            
            # Click login button
            login_button = await self.page.wait_for_selector("button[type='submit']", timeout=10000)
            await login_button.click()
            
            # Wait for navigation or CAPTCHA/2FA
            try:
                await self.page.wait_for_url("**/feed/**", timeout=30000)
                logger.info("Successfully logged into LinkedIn")
                
                # Store session cookies
                cookies = await self.page.context.cookies()
                self.session_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
                
                return True
                
            except Exception as e:
                # Check for CAPTCHA or 2FA
                if await self.page.query_selector("[data-test-id='captcha']"):
                    logger.warning("CAPTCHA detected - manual intervention required")
                    return False
                elif await self.page.query_selector("[data-test-id='challenge']"):
                    logger.warning("2FA challenge detected - manual intervention required")
                    return False
                else:
                    logger.error(f"Login failed: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"LinkedIn login error: {e}")
            return False
    
    async def apply_to_job(self, 
                          job_url: str, 
                          user_data: Dict[str, Any],
                          resume_path: Optional[str] = None,
                          cover_letter: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
        """Apply to a LinkedIn job with form automation"""
        
        application_log = {
            "start_time": datetime.utcnow().isoformat(),
            "steps": [],
            "errors": [],
            "form_data": {}
        }
        
        try:
            logger.info(f"Starting application process for job: {job_url}")
            
            # Navigate to job page
            await self.page.goto(job_url, wait_until="networkidle")
            await self.human_delay(2, 4)
            
            application_log["steps"].append("Navigated to job page")
            
            # Check if Easy Apply is available
            easy_apply_button = await self.page.query_selector("button[data-test-id='jobs-apply-button']")
            if not easy_apply_button:
                # Look for external apply button
                external_apply = await self.page.query_selector("a[data-test-id='jobs-apply-button']")
                if external_apply:
                    application_log["errors"].append("Job requires external application - not supported")
                    return False, application_log
                else:
                    application_log["errors"].append("No apply button found")
                    return False, application_log
            
            # Click Easy Apply button
            await easy_apply_button.click()
            await self.human_delay(2, 3)
            
            application_log["steps"].append("Clicked Easy Apply button")
            
            # Wait for application modal to load
            await self.page.wait_for_selector(".jobs-easy-apply-modal", timeout=10000)
            
            # Process application steps
            step_count = 0
            max_steps = 10
            
            while step_count < max_steps:
                step_count += 1
                
                # Check if we're on the final review step
                if await self.page.query_selector("button[data-test-id='jobs-apply-form-submit-button']"):
                    # Final submit step
                    submit_result = await self.handle_final_submit(application_log)
                    if submit_result:
                        application_log["steps"].append("Application submitted successfully")
                        application_log["end_time"] = datetime.utcnow().isoformat()
                        return True, application_log
                    else:
                        application_log["errors"].append("Failed to submit application")
                        return False, application_log
                
                # Handle current step
                step_handled = await self.handle_application_step(
                    user_data, resume_path, cover_letter, application_log
                )
                
                if not step_handled:
                    application_log["errors"].append(f"Failed to handle step {step_count}")
                    return False, application_log
                
                # Look for Next button
                next_button = await self.page.query_selector("button[data-test-id='jobs-apply-form-continue-button']")
                if next_button and await next_button.is_enabled():
                    await next_button.click()
                    await self.human_delay(2, 3)
                    application_log["steps"].append(f"Completed step {step_count}")
                else:
                    # Check if we're done or stuck
                    if not await self.page.query_selector("button[data-test-id='jobs-apply-form-submit-button']"):
                        application_log["errors"].append(f"Stuck on step {step_count} - no next button")
                        return False, application_log
            
            application_log["errors"].append("Exceeded maximum steps")
            return False, application_log
            
        except Exception as e:
            application_log["errors"].append(f"Application error: {str(e)}")
            application_log["end_time"] = datetime.utcnow().isoformat()
            logger.error(f"Error applying to job: {e}")
            return False, application_log
    
    async def handle_application_step(self, 
                                    user_data: Dict[str, Any],
                                    resume_path: Optional[str],
                                    cover_letter: Optional[str],
                                    application_log: Dict[str, Any]) -> bool:
        """Handle individual application step"""
        try:
            # Check for resume upload
            resume_upload = await self.page.query_selector("input[type='file'][accept*='pdf']")
            if resume_upload and resume_path:
                await resume_upload.set_input_files(resume_path)
                await self.human_delay(1, 2)
                application_log["steps"].append("Resume uploaded")
            
            # Check for cover letter
            cover_letter_textarea = await self.page.query_selector("textarea[data-test-id='jobs-apply-form-cover-letter']")
            if cover_letter_textarea and cover_letter:
                await self.human_type(cover_letter_textarea, cover_letter)
                await self.human_delay(1, 2)
                application_log["steps"].append("Cover letter filled")
            
            # Handle form fields
            form_fields = await self.page.query_selector_all("input, select, textarea")
            
            for field in form_fields:
                try:
                    field_type = await field.get_attribute("type")
                    field_name = await field.get_attribute("name")
                    field_id = await field.get_attribute("id")
                    field_placeholder = await field.get_attribute("placeholder")
                    field_label = await self.get_field_label(field)
                    
                    # Skip file inputs and hidden fields
                    if field_type in ["file", "hidden", "submit", "button"]:
                        continue
                    
                    # Handle different field types
                    if field_type == "text" or field_type == "email" or field_type == "tel":
                        await self.handle_text_field(field, field_name, field_label, user_data, application_log)
                    elif field_type == "select" or await field.evaluate("el => el.tagName.toLowerCase()") == "select":
                        await self.handle_select_field(field, field_name, field_label, user_data, application_log)
                    elif field_type == "radio":
                        await self.handle_radio_field(field, field_name, field_label, user_data, application_log)
                    elif field_type == "checkbox":
                        await self.handle_checkbox_field(field, field_name, field_label, user_data, application_log)
                    elif await field.evaluate("el => el.tagName.toLowerCase()") == "textarea":
                        await self.handle_textarea_field(field, field_name, field_label, user_data, application_log)
                        
                except Exception as e:
                    logger.warning(f"Error handling form field: {e}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling application step: {e}")
            return False
    
    async def handle_text_field(self, field: ElementHandle, field_name: str, field_label: str, user_data: Dict[str, Any], application_log: Dict[str, Any]):
        """Handle text input fields"""
        try:
            # Skip if field is already filled
            current_value = await field.get_attribute("value")
            if current_value and current_value.strip():
                return
            
            # Determine what to fill based on field identifiers
            field_info = f"{field_name} {field_label}".lower()
            
            if any(keyword in field_info for keyword in ["first", "fname", "given"]):
                value = user_data.get("first_name", "")
            elif any(keyword in field_info for keyword in ["last", "lname", "surname", "family"]):
                value = user_data.get("last_name", "")
            elif any(keyword in field_info for keyword in ["email", "e-mail"]):
                value = user_data.get("email", "")
            elif any(keyword in field_info for keyword in ["phone", "mobile", "telephone"]):
                value = user_data.get("phone", "")
            elif any(keyword in field_info for keyword in ["city", "location"]):
                value = user_data.get("city", "")
            elif any(keyword in field_info for keyword in ["zip", "postal"]):
                value = user_data.get("zip_code", "")
            elif any(keyword in field_info for keyword in ["linkedin", "profile"]):
                value = user_data.get("linkedin_url", "")
            elif any(keyword in field_info for keyword in ["website", "portfolio", "url"]):
                value = user_data.get("website", "")
            else:
                # Skip unknown fields
                return
            
            if value:
                await self.human_type(field, value)
                application_log["form_data"][field_name or field_label] = value
                
        except Exception as e:
            logger.warning(f"Error handling text field: {e}")
    
    async def handle_select_field(self, field: ElementHandle, field_name: str, field_label: str, user_data: Dict[str, Any], application_log: Dict[str, Any]):
        """Handle select dropdown fields"""
        try:
            field_info = f"{field_name} {field_label}".lower()
            
            # Get available options
            options = await field.query_selector_all("option")
            option_texts = []
            for option in options:
                text = await option.inner_text()
                option_texts.append(text.strip())
            
            # Determine what to select based on field type
            if any(keyword in field_info for keyword in ["country"]):
                target_value = user_data.get("country", "United States")
            elif any(keyword in field_info for keyword in ["state", "province", "region"]):
                target_value = user_data.get("state", "")
            elif any(keyword in field_info for keyword in ["experience", "years"]):
                target_value = user_data.get("years_experience", "")
            elif any(keyword in field_info for keyword in ["education", "degree"]):
                target_value = user_data.get("education_level", "")
            else:
                # For unknown selects, try to pick a reasonable default
                if len(option_texts) > 1:
                    # Skip "Select..." or empty options, pick first real option
                    for option_text in option_texts[1:]:
                        if option_text and not any(skip in option_text.lower() for skip in ["select", "choose", "please"]):
                            await field.select_option(label=option_text)
                            application_log["form_data"][field_name or field_label] = option_text
                            break
                return
            
            # Find matching option
            if target_value:
                for option_text in option_texts:
                    if target_value.lower() in option_text.lower() or option_text.lower() in target_value.lower():
                        await field.select_option(label=option_text)
                        application_log["form_data"][field_name or field_label] = option_text
                        break
                        
        except Exception as e:
            logger.warning(f"Error handling select field: {e}")
    
    async def handle_radio_field(self, field: ElementHandle, field_name: str, field_label: str, user_data: Dict[str, Any], application_log: Dict[str, Any]):
        """Handle radio button fields"""
        try:
            field_info = f"{field_name} {field_label}".lower()
            
            # Handle common radio button scenarios
            if any(keyword in field_info for keyword in ["authorized", "eligible", "work", "visa"]):
                # Work authorization - assume yes
                if any(keyword in field_info for keyword in ["yes", "authorized", "eligible"]):
                    await field.check()
                    application_log["form_data"][field_name or field_label] = "Yes"
            elif any(keyword in field_info for keyword in ["relocate", "relocation"]):
                # Willing to relocate - use user preference or default to yes
                willing_relocate = user_data.get("willing_to_relocate", True)
                if (willing_relocate and "yes" in field_info) or (not willing_relocate and "no" in field_info):
                    await field.check()
                    application_log["form_data"][field_name or field_label] = "Yes" if willing_relocate else "No"
            elif any(keyword in field_info for keyword in ["remote", "onsite", "hybrid"]):
                # Work preference
                work_preference = user_data.get("work_preference", "remote").lower()
                if work_preference in field_info:
                    await field.check()
                    application_log["form_data"][field_name or field_label] = work_preference.title()
                    
        except Exception as e:
            logger.warning(f"Error handling radio field: {e}")
    
    async def handle_checkbox_field(self, field: ElementHandle, field_name: str, field_label: str, user_data: Dict[str, Any], application_log: Dict[str, Any]):
        """Handle checkbox fields"""
        try:
            field_info = f"{field_name} {field_label}".lower()
            
            # Handle common checkboxes
            if any(keyword in field_info for keyword in ["terms", "conditions", "privacy", "agree"]):
                # Agree to terms - check by default
                await field.check()
                application_log["form_data"][field_name or field_label] = "Checked"
            elif any(keyword in field_info for keyword in ["newsletter", "updates", "marketing"]):
                # Marketing emails - use user preference or default to unchecked
                subscribe = user_data.get("subscribe_to_updates", False)
                if subscribe:
                    await field.check()
                    application_log["form_data"][field_name or field_label] = "Checked"
                    
        except Exception as e:
            logger.warning(f"Error handling checkbox field: {e}")
    
    async def handle_textarea_field(self, field: ElementHandle, field_name: str, field_label: str, user_data: Dict[str, Any], application_log: Dict[str, Any]):
        """Handle textarea fields"""
        try:
            # Skip if already filled
            current_value = await field.get_attribute("value")
            if current_value and current_value.strip():
                return
                
            field_info = f"{field_name} {field_label}".lower()
            
            if any(keyword in field_info for keyword in ["cover", "letter", "motivation"]):
                # Cover letter field - already handled separately
                return
            elif any(keyword in field_info for keyword in ["why", "interest", "reason"]):
                value = user_data.get("why_interested", "I am very interested in this position and believe my skills and experience make me a great fit for your team.")
            elif any(keyword in field_info for keyword in ["additional", "other", "comments"]):
                value = user_data.get("additional_info", "Thank you for considering my application. I look forward to hearing from you.")
            else:
                return
            
            if value:
                await self.human_type(field, value)
                application_log["form_data"][field_name or field_label] = value
                
        except Exception as e:
            logger.warning(f"Error handling textarea field: {e}")
    
    async def get_field_label(self, field: ElementHandle) -> str:
        """Get the label text for a form field"""
        try:
            # Try to find associated label
            field_id = await field.get_attribute("id")
            if field_id:
                label = await self.page.query_selector(f"label[for='{field_id}']")
                if label:
                    return await label.inner_text()
            
            # Try to find parent label
            parent_label = await field.query_selector("xpath=ancestor::label[1]")
            if parent_label:
                return await parent_label.inner_text()
            
            # Try to find nearby label
            placeholder = await field.get_attribute("placeholder")
            if placeholder:
                return placeholder
                
            return ""
            
        except:
            return ""
    
    async def handle_final_submit(self, application_log: Dict[str, Any]) -> bool:
        """Handle the final application submission"""
        try:
            # Look for submit button
            submit_button = await self.page.query_selector("button[data-test-id='jobs-apply-form-submit-button']")
            if not submit_button:
                return False
            
            # Check if button is enabled
            if not await submit_button.is_enabled():
                application_log["errors"].append("Submit button is disabled")
                return False
            
            # Add final delay before submission
            await self.human_delay(2, 4)
            
            # Click submit
            await submit_button.click()
            
            # Wait for confirmation or error
            try:
                # Wait for success message or redirect
                await self.page.wait_for_selector(".jobs-apply-confirmation", timeout=15000)
                return True
            except:
                # Check for error message
                error_message = await self.page.query_selector(".jobs-apply-error")
                if error_message:
                    error_text = await error_message.inner_text()
                    application_log["errors"].append(f"Application error: {error_text}")
                return False
                
        except Exception as e:
            application_log["errors"].append(f"Submit error: {str(e)}")
            return False
    
    async def human_delay(self, min_seconds: float = 1, max_seconds: float = 3):
        """Add human-like delay between actions"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        
        # Update request tracking
        self.request_count += 1
        self.last_request_time = time.time()
        
        # Add longer delay if too many requests
        if self.request_count > 30:
            await asyncio.sleep(random.uniform(5, 10))
            self.request_count = 0
    
    async def human_type(self, element, text: str):
        """Type text with human-like delays"""
        await element.clear()
        for char in text:
            await element.type(char, delay=random.uniform(50, 150))
    
    async def close(self):
        """Close browser and cleanup"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            logger.info("Application browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")


async def apply_to_linkedin_job(user_id: int, job_id: int, resume_id: Optional[int] = None, cover_letter: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
    """Main function to apply to a LinkedIn job"""
    db = next(get_db())
    
    # Get user, job, and resume data
    user = db.query(User).filter(User.id == user_id).first()
    job = db.query(Job).filter(Job.id == job_id).first()
    resume = db.query(Resume).filter(Resume.id == resume_id).first() if resume_id else None
    
    if not user:
        return False, {"error": "User not found"}
    
    if not job:
        return False, {"error": "Job not found"}
    
    if not user.linkedin_email or not user.linkedin_password:
        return False, {"error": "LinkedIn credentials not configured"}
    
    # Prepare user data for form filling
    user_data = {
        "first_name": user.full_name.split()[0] if user.full_name else "",
        "last_name": " ".join(user.full_name.split()[1:]) if user.full_name and len(user.full_name.split()) > 1 else "",
        "email": user.email,
        "phone": user.phone or "",
        "city": user.location or "",
        "linkedin_url": f"https://linkedin.com/in/{user.email.split('@')[0]}",
        "years_experience": "5+ years",  # Could be extracted from user profile
        "education_level": "Bachelor's degree",  # Could be extracted from user profile
        "willing_to_relocate": True,
        "work_preference": "remote",
        "subscribe_to_updates": False,
        "why_interested": f"I am very interested in the {job.title} position at {job.company}. My background and skills align well with the requirements, and I would love to contribute to your team's success.",
        "additional_info": "Thank you for considering my application. I look forward to discussing how I can contribute to your organization."
    }
    
    # Get resume file path if available
    resume_path = resume.file_path if resume else None
    
    async with LinkedInJobApplicator() as applicator:
        # Login to LinkedIn
        if not await applicator.login_to_linkedin(user.linkedin_email, user.linkedin_password):
            return False, {"error": "Failed to login to LinkedIn"}
        
        # Apply to job
        success, application_log = await applicator.apply_to_job(
            job.linkedin_url, 
            user_data, 
            resume_path, 
            cover_letter
        )
        
        # Create application record
        try:
            application = JobApplication(
                user_id=user_id,
                job_id=job_id,
                resume_id=resume_id,
                status="applied" if success else "failed",
                cover_letter=cover_letter,
                applied_automatically=True,
                automation_log=application_log,
                applied_at=datetime.utcnow() if success else None
            )
            
            db.add(application)
            db.commit()
            db.refresh(application)
            
            return success, {
                "application_id": application.id,
                "automation_log": application_log
            }
            
        except Exception as e:
            logger.error(f"Error creating application record: {e}")
            db.rollback()
            return success, {"error": f"Failed to save application: {str(e)}", "automation_log": application_log}