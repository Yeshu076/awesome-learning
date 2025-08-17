import os
import re
from typing import Dict, List, Any
from pathlib import Path
import PyPDF2
from docx import Document
from loguru import logger


def parse_resume_file(file_path: str, file_type: str) -> Dict[str, Any]:
    """Parse resume file and extract information"""
    try:
        # Extract text based on file type
        if file_type.lower() == "pdf":
            text = extract_text_from_pdf(file_path)
        elif file_type.lower() in ["doc", "docx"]:
            text = extract_text_from_docx(file_path)
        elif file_type.lower() == "txt":
            text = extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        # Parse extracted text
        parsed_data = {
            "text": text,
            "skills": extract_skills(text),
            "experience": extract_experience(text),
            "education": extract_education(text),
            "contact": extract_contact_info(text)
        }
        
        logger.info(f"Successfully parsed resume: {len(text)} characters extracted")
        return parsed_data
        
    except Exception as e:
        logger.error(f"Error parsing resume file {file_path}: {e}")
        raise


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file"""
    try:
        text = ""
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF {file_path}: {e}")
        raise


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX file"""
    try:
        doc = Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from DOCX {file_path}: {e}")
        raise


def extract_text_from_txt(file_path: str) -> str:
    """Extract text from TXT file"""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except Exception as e:
        logger.error(f"Error extracting text from TXT {file_path}: {e}")
        raise


def extract_skills(text: str) -> List[str]:
    """Extract skills from resume text"""
    try:
        # Common technical skills
        technical_skills = [
            # Programming languages
            "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby", "go", "rust",
            "swift", "kotlin", "scala", "r", "matlab", "sql", "html", "css",
            
            # Frameworks and libraries
            "react", "angular", "vue", "django", "flask", "fastapi", "spring", "express",
            "node.js", "laravel", "rails", "tensorflow", "pytorch", "pandas", "numpy",
            
            # Databases
            "mysql", "postgresql", "mongodb", "redis", "elasticsearch", "oracle", "sqlite",
            
            # Cloud and DevOps
            "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "git", "gitlab", "github",
            "terraform", "ansible", "chef", "puppet",
            
            # Other technical skills
            "machine learning", "artificial intelligence", "data science", "blockchain",
            "microservices", "api", "rest", "graphql", "agile", "scrum", "devops"
        ]
        
        # Soft skills
        soft_skills = [
            "leadership", "communication", "teamwork", "problem solving", "analytical",
            "project management", "time management", "creativity", "adaptability",
            "critical thinking", "collaboration", "negotiation", "presentation"
        ]
        
        all_skills = technical_skills + soft_skills
        text_lower = text.lower()
        
        found_skills = []
        for skill in all_skills:
            if skill in text_lower:
                found_skills.append(skill.title())
        
        return list(set(found_skills))  # Remove duplicates
        
    except Exception as e:
        logger.error(f"Error extracting skills: {e}")
        return []


def extract_experience(text: str) -> List[Dict[str, str]]:
    """Extract work experience from resume text"""
    try:
        experience = []
        
        # Look for common experience patterns
        experience_patterns = [
            r"(\d{4})\s*[-–]\s*(\d{4}|\w+)\s*[:\-]\s*(.+?)(?=\n\d{4}|\nEducation|\nSkills|$)",
            r"(\w+\s+\d{4})\s*[-–]\s*(\w+\s+\d{4}|\w+)\s*[:\-]\s*(.+?)(?=\n\w+\s+\d{4}|\nEducation|\nSkills|$)"
        ]
        
        for pattern in experience_patterns:
            matches = re.finditer(pattern, text, re.MULTILINE | re.DOTALL)
            for match in matches:
                exp_entry = {
                    "start_date": match.group(1),
                    "end_date": match.group(2),
                    "description": match.group(3).strip()
                }
                experience.append(exp_entry)
        
        return experience
        
    except Exception as e:
        logger.error(f"Error extracting experience: {e}")
        return []


def extract_education(text: str) -> List[Dict[str, str]]:
    """Extract education from resume text"""
    try:
        education = []
        
        # Common degree patterns
        degree_patterns = [
            r"(Bachelor|Master|PhD|B\.S\.|M\.S\.|B\.A\.|M\.A\.|MBA).*?(\d{4})",
            r"(University|College|Institute).*?(\d{4})"
        ]
        
        for pattern in degree_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                edu_entry = {
                    "degree": match.group(1),
                    "year": match.group(2)
                }
                education.append(edu_entry)
        
        return education
        
    except Exception as e:
        logger.error(f"Error extracting education: {e}")
        return []


def extract_contact_info(text: str) -> Dict[str, str]:
    """Extract contact information from resume text"""
    try:
        contact = {}
        
        # Email pattern
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        email_match = re.search(email_pattern, text)
        if email_match:
            contact["email"] = email_match.group()
        
        # Phone pattern
        phone_pattern = r"(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})"
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            contact["phone"] = phone_match.group()
        
        # LinkedIn pattern
        linkedin_pattern = r"linkedin\.com/in/[\w-]+"
        linkedin_match = re.search(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_match:
            contact["linkedin"] = "https://" + linkedin_match.group()
        
        return contact
        
    except Exception as e:
        logger.error(f"Error extracting contact info: {e}")
        return {}


def validate_file_upload(file_path: str, max_size_mb: int = 10) -> bool:
    """Validate uploaded file"""
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return False
        
        # Check file size
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > max_size_mb:
            logger.warning(f"File too large: {file_size_mb}MB > {max_size_mb}MB")
            return False
        
        # Check file extension
        allowed_extensions = [".pdf", ".doc", ".docx", ".txt"]
        file_extension = Path(file_path).suffix.lower()
        if file_extension not in allowed_extensions:
            logger.warning(f"Invalid file extension: {file_extension}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating file {file_path}: {e}")
        return False


def clean_filename(filename: str) -> str:
    """Clean filename for safe storage"""
    # Remove special characters and spaces
    cleaned = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    # Remove multiple underscores
    cleaned = re.sub(r'_+', '_', cleaned)
    return cleaned.strip('_')