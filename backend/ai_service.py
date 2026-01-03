import whisper
import nltk
from nltk.tokenize import sent_tokenize
import re
import os
import json

# Ensure NLTK data is available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
    nltk.download('punkt_tab')

# Load Whisper Model (Lazy loading or global)
# Using "base" model for balance of speed and accuracy. 
# "small" is better but slower. "tiny" is fast but less accurate.
print("Loading Whisper model...")
model = whisper.load_model("base")
print("Whisper model loaded.")

def transcribe_audio(file_path):
    """
    Transcribes audio using Whisper.
    Uses task="translate" to automatically translate Hinglish/Hindi to English.
    """
    if not os.path.exists(file_path):
        return ""
    
    try:
        # Whisper handles loading and processing
        # fp16=False is safer for CPU inference if GPU not available/supported
        result = model.transcribe(file_path, task="translate", fp16=False)
        return result["text"].strip()
    except Exception as e:
        print(f"Whisper Transcription Error: {e}")
        return ""

def extract_skills(text):
    common_skills = [
        "python", "java", "javascript", "react", "node", "sql", "aws", "docker", 
        "communication", "leadership", "html", "css", "c++", "c#", "machine learning",
        "ai", "data analysis", "project management", "git", "linux", "django", "flask",
        "fastapi", "kubernetes", "terraform", "azure", "gcp", "rest api", "graphql",
        "typescript", "angular", "vue", "mongodb", "postgresql", "mysql", "redis",
        "agile", "scrum", "jira", "figma", "pandas", "numpy", "pytorch", "tensorflow",
        "nlp", "opencv", "selenium", "jenkins", "devops"
    ]
    found_skills = []
    text_lower = text.lower()
    for skill in common_skills:
        # Use regex to match whole words
        if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
            found_skills.append(skill.capitalize())
        # Special case for C++ / C#
        elif skill in ["c++", "c#"] and skill in text_lower:
             if skill not in found_skills: found_skills.append(skill.capitalize())
             
    return list(set(found_skills))

def extract_availability(text):
    patterns = [
        r"(\d+)\s*(days?|weeks?|months?)\s*notice",
        r"immediate\s*joiner",
        r"can\s*join\s*immediately",
        r"available\s*from",
        r"notice\s*period\s*is\s*(\d+)\s*(days?|weeks?|months?)",
        r"start\s*working\s*from"
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return "Not mentioned"

def extract_experience(text):
    patterns = [
        r"(\d+)\s*(years?|yrs?)\s*of\s*experience",
        r"(\d+)\s*(years?|yrs?)\s*exp",
        r"fresher",
        r"just\s*graduated",
        r"working\s*for\s*(\d+)\s*years",
        r"final\s*year\s*student"
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return "Not mentioned"

def extract_name(text):
    # Basic patterns to find introduction
    patterns = [
        r"my name is ([A-Z][a-z]+(?: [A-Z][a-z]+)?)",
        r"i am ([A-Z][a-z]+(?: [A-Z][a-z]+)?)"
    ]
    for p in patterns:
        match = re.search(p, text, re.IGNORECASE)
        if match:
             name = match.group(1)
             # Basic filter to avoid common false positives
             if name.lower() not in ["a", "an", "the", "developer", "student", "engineer", "working", "interested", "looking"]:
                 return name.title()
    return "Not mentioned"

def extract_education_details(text):
    degrees = ["bachelor", "master", "b.tech", "m.tech", "bca", "mca", "phd", "diploma", "degree", "computer science", "engineering"]
    colleges = ["university", "college", "institute", "school", "iit", "nit", "bits"]
    
    found_edu = []
    found_college = []
    
    sentences = sent_tokenize(text)
    for sent in sentences:
        sent_lower = sent.lower()
        if any(d in sent_lower for d in degrees):
            found_edu.append(sent.strip())
        if any(c in sent_lower for c in colleges):
            found_college.append(sent.strip())
            
    edu_str = "; ".join(list(set(found_edu))) if found_edu else "Not mentioned"
    col_str = "; ".join(list(set(found_college))) if found_college else "Not mentioned"
    
    # Clean up trailing periods
    if edu_str.endswith('.'): edu_str = edu_str[:-1]
    if col_str.endswith('.'): col_str = col_str[:-1]
    
    return edu_str, col_str

def extract_projects(text, all_skills):
    keywords = ["project", "built", "created", "developed", "designed", "implemented", "application", "website", "system"]
    sentences = sent_tokenize(text)
    projects = []
    
    # Simple heuristic: If a sentence contains project keywords, it might be a project description.
    for i, sent in enumerate(sentences):
        sent_lower = sent.lower()
        if any(k in sent_lower for k in keywords):
            # Check if it's a generic statement like "I have done many projects"
            if "many projects" in sent_lower or "various projects" in sent_lower:
                continue
                
            # Attempt to extract a title (very hard without NER), so we use the sentence as description
            desc = sent
            # Append next sentence if it exists, as it often contains details
            if i + 1 < len(sentences):
                 desc += " " + sentences[i+1]
            
            # Find skills used in this project
            project_skills = [s for s in all_skills if s.lower() in desc.lower()]
            
            projects.append({
                "title": "Project Mention", 
                "description": desc,
                "technologies": project_skills
            })
            
    # Deduplicate based on description similarity? For now, just return top 3 to avoid noise
    return projects[:5]

def extract_achievements(text):
    keywords = ["award", "certified", "certificate", "rank", "won", "achievement", "completed course", "first prize", "hackathon"]
    sentences = sent_tokenize(text)
    achievements = []
    for sent in sentences:
        if any(k in sent.lower() for k in keywords):
            achievements.append(sent.strip())
    return list(set(achievements))

def extract_hobbies(text):
    keywords = ["hobby", "hobbies", "like to play", "love to", "interest in", "free time", "pastime"]
    sentences = sent_tokenize(text)
    hobbies = []
    for sent in sentences:
        if any(k in sent.lower() for k in keywords):
             # Filter out "interest in coding" if we want non-tech hobbies?
             # User asked for "Extra activities / hobbies".
            hobbies.append(sent.strip())
    return list(set(hobbies))

def generate_summary(text):
    """
    Processes the English text from Whisper to extract structured data.
    Returns:
        structured_data (dict): The full JSON object
        text (str): The raw English text (passed through)
    """
    if not text:
        empty_data = {
            "summary": "No content detected.",
            "name": "Not mentioned",
            "education": "Not mentioned",
            "college": "Not mentioned",
            "projects": [],
            "skills": [],
            "achievements": [],
            "hobbies": [],
            "experience": "Not mentioned",
            "availability": "Not mentioned"
        }
        return empty_data, "None"
    
    # 1. Extract Details
    name = extract_name(text)
    skills = extract_skills(text)
    availability = extract_availability(text)
    experience = extract_experience(text)
    education, college = extract_education_details(text)
    projects = extract_projects(text, skills)
    achievements = extract_achievements(text)
    hobbies = extract_hobbies(text)
    
    # 2. Generate Summary Paragraph
    summary_paragraph = f"Candidate: {name}."
    
    if experience != "Not mentioned":
        summary_paragraph += f" Experience: {experience}."
        
    if education != "Not mentioned":
        summary_paragraph += f" Educational background: {education}."
    if college != "Not mentioned" and college != education:
        summary_paragraph += f" Institution: {college}."
    
    if skills:
        summary_paragraph += f" Key technical skills include {', '.join(skills[:5])}."
        
    if projects:
        summary_paragraph += f" They have worked on {len(projects)} projects, involving technologies like {', '.join(projects[0]['technologies'][:3])}."
        
    if availability != "Not mentioned":
        summary_paragraph += f" Availability: {availability}."
        
    # 3. Construct JSON
    structured_data = {
        "summary": summary_paragraph,
        "name": name,
        "education": education,
        "college": college,
        "projects": projects,
        "skills": skills,
        "achievements": achievements,
        "hobbies": hobbies,
        "experience": experience,
        "availability": availability
    }
    
    return structured_data, text
