import asyncio
import random
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta
import json

from playwright.async_api import async_playwright, Browser, Page
from fake_useragent import UserAgent
from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.job import Job
from app.models.user import User


class LinkedInJobScraper:
    """LinkedIn job scraper with anti-detection capabilities"""
    
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
            
            logger.info("Browser initialized successfully")
            
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
    
    async def search_jobs(self, 
                         keywords: str, 
                         location: str = "", 
                         experience_level: Optional[List[str]] = None,
                         employment_type: Optional[List[str]] = None,
                         remote: bool = False,
                         easy_apply: bool = False,
                         limit: int = 25) -> List[Dict[str, Any]]:
        """Search for jobs on LinkedIn with specified criteria"""
        try:
            logger.info(f"Searching for jobs: {keywords} in {location}")
            
            # Build search URL
            search_params = {
                "keywords": keywords,
                "location": location,
                "f_TPR": "r86400",  # Past 24 hours
                "f_AL": "true" if easy_apply else None,
                "f_WT": "2" if remote else None,
                "start": 0
            }
            
            # Add experience level filters
            if experience_level:
                exp_map = {
                    "Entry": "1",
                    "Associate": "2", 
                    "Mid": "3",
                    "Senior": "4",
                    "Director": "5",
                    "Executive": "6"
                }
                exp_values = [exp_map.get(exp) for exp in experience_level if exp_map.get(exp)]
                if exp_values:
                    search_params["f_E"] = ",".join(exp_values)
            
            # Add employment type filters
            if employment_type:
                emp_map = {
                    "Full-time": "F",
                    "Part-time": "P",
                    "Contract": "C",
                    "Temporary": "T",
                    "Internship": "I"
                }
                emp_values = [emp_map.get(emp) for emp in employment_type if emp_map.get(emp)]
                if emp_values:
                    search_params["f_JT"] = ",".join(emp_values)
            
            # Clean up None values
            search_params = {k: v for k, v in search_params.items() if v is not None}
            
            # Navigate to jobs search
            search_url = f"https://www.linkedin.com/jobs/search/?{urlencode(search_params)}"
            await self.page.goto(search_url, wait_until="networkidle")
            await self.human_delay(2, 4)
            
            jobs = []
            processed_ids = set()
            
            # Scroll and collect job listings
            for page_num in range(0, min(limit // 25 + 1, 40)):  # LinkedIn limits to ~1000 results
                await self.scroll_and_load_jobs()
                
                # Extract job cards
                job_cards = await self.page.query_selector_all("[data-occludable-job-id]")
                
                for card in job_cards:
                    if len(jobs) >= limit:
                        break
                        
                    try:
                        job_data = await self.extract_job_data(card)
                        if job_data and job_data.get("linkedin_job_id") not in processed_ids:
                            jobs.append(job_data)
                            processed_ids.add(job_data.get("linkedin_job_id"))
                            
                    except Exception as e:
                        logger.warning(f"Error extracting job data: {e}")
                        continue
                
                # Load next page if available and not at limit
                if len(jobs) >= limit:
                    break
                    
                next_button = await self.page.query_selector("button[aria-label='View next page']")
                if next_button and await next_button.is_enabled():
                    await next_button.click()
                    await self.human_delay(3, 5)
                else:
                    break
            
            logger.info(f"Found {len(jobs)} job listings")
            return jobs
            
        except Exception as e:
            logger.error(f"Job search error: {e}")
            return []
    
    async def extract_job_data(self, job_card) -> Optional[Dict[str, Any]]:
        """Extract job data from a job card element"""
        try:
            # Get job ID
            job_id = await job_card.get_attribute("data-occludable-job-id")
            if not job_id:
                return None
            
            # Click on job card to load details
            await job_card.click()
            await self.human_delay(1, 2)
            
            # Wait for job details to load
            await self.page.wait_for_selector(".job-details", timeout=5000)
            
            # Extract basic job info
            title_elem = await self.page.query_selector("h1.job-title")
            title = await title_elem.inner_text() if title_elem else ""
            
            company_elem = await self.page.query_selector(".job-details-jobs-unified-top-card__company-name a")
            company = await company_elem.inner_text() if company_elem else ""
            
            location_elem = await self.page.query_selector(".job-details-jobs-unified-top-card__bullet")
            location = await location_elem.inner_text() if location_elem else ""
            
            # Extract job description
            description_elem = await self.page.query_selector(".job-details-jobs-unified-description__content")
            description = await description_elem.inner_text() if description_elem else ""
            
            # Extract job metadata
            posted_time_elem = await self.page.query_selector(".job-details-jobs-unified-top-card__primary-description-without-tagline time")
            posted_time = await posted_time_elem.get_attribute("datetime") if posted_time_elem else None
            
            # Check for Easy Apply
            easy_apply = bool(await self.page.query_selector("button[data-test-id='jobs-apply-button']"))
            
            # Get job URL
            job_url = self.page.url
            
            # Extract additional details
            employment_type = await self.extract_employment_type()
            experience_level = await self.extract_experience_level()
            is_remote = await self.check_remote_work()
            
            job_data = {
                "linkedin_job_id": job_id,
                "title": title.strip(),
                "company": company.strip(),
                "location": location.strip(),
                "description": description.strip(),
                "employment_type": employment_type,
                "experience_level": experience_level,
                "is_remote": is_remote,
                "easy_apply": easy_apply,
                "linkedin_url": job_url,
                "posted_date": self.parse_posted_date(posted_time) if posted_time else None,
                "scraped_at": datetime.utcnow()
            }
            
            return job_data
            
        except Exception as e:
            logger.warning(f"Error extracting job data: {e}")
            return None
    
    async def extract_employment_type(self) -> Optional[str]:
        """Extract employment type from job details"""
        try:
            # Look for employment type in job criteria section
            criteria_items = await self.page.query_selector_all(".job-criteria__item")
            for item in criteria_items:
                header = await item.query_selector(".job-criteria__subheader")
                if header:
                    header_text = await header.inner_text()
                    if "Employment type" in header_text:
                        value_elem = await item.query_selector(".job-criteria__text")
                        return await value_elem.inner_text() if value_elem else None
            return None
        except:
            return None
    
    async def extract_experience_level(self) -> Optional[str]:
        """Extract experience level from job details"""
        try:
            criteria_items = await self.page.query_selector_all(".job-criteria__item")
            for item in criteria_items:
                header = await item.query_selector(".job-criteria__subheader")
                if header:
                    header_text = await header.inner_text()
                    if "Seniority level" in header_text:
                        value_elem = await item.query_selector(".job-criteria__text")
                        return await value_elem.inner_text() if value_elem else None
            return None
        except:
            return None
    
    async def check_remote_work(self) -> bool:
        """Check if job offers remote work"""
        try:
            # Check job description and location for remote indicators
            description_elem = await self.page.query_selector(".job-details-jobs-unified-description__content")
            if description_elem:
                description = await description_elem.inner_text()
                remote_keywords = ["remote", "work from home", "wfh", "telecommute", "distributed"]
                return any(keyword in description.lower() for keyword in remote_keywords)
            return False
        except:
            return False
    
    def parse_posted_date(self, posted_time: str) -> Optional[datetime]:
        """Parse LinkedIn posted time to datetime"""
        try:
            if posted_time:
                return datetime.fromisoformat(posted_time.replace('Z', '+00:00'))
            return None
        except:
            return None
    
    async def scroll_and_load_jobs(self):
        """Scroll page to load more job listings"""
        try:
            # Scroll to bottom to trigger loading
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.human_delay(2, 3)
            
            # Scroll back up slightly
            await self.page.evaluate("window.scrollBy(0, -200)")
            await self.human_delay(1, 2)
            
        except Exception as e:
            logger.warning(f"Error scrolling page: {e}")
    
    async def human_delay(self, min_seconds: float = 1, max_seconds: float = 3):
        """Add human-like delay between actions"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        
        # Update request tracking
        self.request_count += 1
        self.last_request_time = time.time()
        
        # Add longer delay if too many requests
        if self.request_count > 50:
            await asyncio.sleep(random.uniform(10, 20))
            self.request_count = 0
    
    async def human_type(self, element, text: str):
        """Type text with human-like delays"""
        for char in text:
            await element.type(char, delay=random.uniform(50, 150))
    
    async def close(self):
        """Close browser and cleanup"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")


async def scrape_linkedin_jobs(user_id: int, search_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Main function to scrape LinkedIn jobs for a user"""
    db = next(get_db())
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user or not user.linkedin_email or not user.linkedin_password:
        logger.error(f"User {user_id} missing LinkedIn credentials")
        return []
    
    async with LinkedInJobScraper() as scraper:
        # Login to LinkedIn
        if not await scraper.login_to_linkedin(user.linkedin_email, user.linkedin_password):
            logger.error("Failed to login to LinkedIn")
            return []
        
        # Search for jobs
        jobs = await scraper.search_jobs(**search_params)
        
        # Save jobs to database
        saved_jobs = []
        for job_data in jobs:
            try:
                # Check if job already exists
                existing_job = db.query(Job).filter(
                    Job.linkedin_job_id == job_data["linkedin_job_id"]
                ).first()
                
                if not existing_job:
                    # Create new job
                    job = Job(**job_data)
                    db.add(job)
                    db.commit()
                    db.refresh(job)
                    saved_jobs.append(job_data)
                else:
                    # Update existing job
                    for key, value in job_data.items():
                        if hasattr(existing_job, key):
                            setattr(existing_job, key, value)
                    existing_job.scraped_at = datetime.utcnow()
                    db.commit()
                    saved_jobs.append(job_data)
                    
            except Exception as e:
                logger.error(f"Error saving job {job_data.get('linkedin_job_id')}: {e}")
                db.rollback()
                continue
        
        logger.info(f"Saved {len(saved_jobs)} jobs to database")
        return saved_jobs