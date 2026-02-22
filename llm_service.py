import requests
import json
from config import Config

SYSTEM_PROMPT = """You are an expert scholarship eligibility evaluator.
You will be given a user's profile and a scholarship's eligibility criteria.
Your job is to:
1. Reason step-by-step over every criterion.
2. Decide if the user is ELIGIBLE, PARTIALLY ELIGIBLE, or NOT ELIGIBLE.
3. Return a structured JSON response with:
   - verdict: "ELIGIBLE" | "PARTIALLY_ELIGIBLE" | "NOT_ELIGIBLE"
   - confidence_score: float between 0 and 1 (e.g. 0.73 means 73% eligible)
   - eligibility_percentage: integer between 0 and 100 (e.g. 73)
   - matched_criteria: list of criteria the user meets
   - unmatched_criteria: list of criteria the user does not meet
   - unclear_criteria: list of criteria that cannot be determined from the profile
   - explanation: a human-readable paragraph explaining the outcome
   - recommendations: list of suggestions the user can act on to improve eligibility

Always return ONLY valid JSON. No markdown, no prose outside the JSON."""


def evaluate_eligibility(user_profile: dict, scholarship: dict) -> dict:
    """
    Calls MegaLLM to evaluate user eligibility for a scholarship.

    Args:
        user_profile: dict of user fields from the `users` table
        scholarship: dict of scholarship fields from the `scholarships` table

    Returns:
        Parsed JSON dict with verdict, scores, and explanation.
    """
    user_context = f"""
USER PROFILE:
- Name: {user_profile.get('name')}
- Gender: {user_profile.get('gender')}
- Category: {user_profile.get('category')}
- Family Income: {user_profile.get('family_income')}
- State: {user_profile.get('state')}
- Course: {user_profile.get('course')}
- Degree Level: {user_profile.get('degree_level')}
- CGPA: {user_profile.get('cgpa')}
- Ethnicity: {user_profile.get('ethnicity')}
"""

    scholarship_context = f"""
SCHOLARSHIP DETAILS:
- Name: {scholarship.get('scholarship_name')}
- Amount: {scholarship.get('amount')}
- Deadline: {scholarship.get('deadline')}
- Description: {scholarship.get('description')}
- Location: {scholarship.get('location')}
- Min GPA: {scholarship.get('min_gpa')}
- Max GPA: {scholarship.get('max_gpa')}
- Eligible Majors: {scholarship.get('eligible_majors')}
- Eligible Years: {scholarship.get('eligible_years')}
- Ethnicity Requirement: {scholarship.get('ethnicity')}
- Gender Requirement: {scholarship.get('gender')}
- Citizenship: {scholarship.get('citizenship')}
- Age Limit: {scholarship.get('age_limit')}
- Membership Required: {scholarship.get('membership_required')}
- Min Income: {scholarship.get('min_income')}
- Max Income: {scholarship.get('max_income')}
- Restrictions: {scholarship.get('restrictions')}
- Additional Raw Guidelines: {scholarship.get('raw_json')}
"""

    payload = {
        "model": Config.MEGALLLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_context + scholarship_context}
        ],
        "temperature": 0.2,
        "max_tokens": 1500
    }

    headers = {
        "Authorization": f"Bearer {Config.MEGALLLM_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(Config.MEGALLLM_API_URL, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    raw_content = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw_content)


def parse_unstructured_guidelines(raw_text: str) -> dict:
    """
    Converts unstructured scholarship guideline text into structured eligibility fields.
    Useful when admin uploads a PDF or raw description.
    """
    system = """You are an expert at extracting structured eligibility criteria from unstructured scholarship guideline text.
Return ONLY valid JSON with these keys (use null if unknown):
min_gpa, max_gpa, eligible_majors (list), eligible_years (list), ethnicity, gender, citizenship,
age_limit (int), membership_required, min_income (int), max_income (int), restrictions (string), summary (string)"""

    payload = {
        "model": Config.MEGALLLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Extract eligibility criteria from:\n\n{raw_text}"}
        ],
        "temperature": 0.1,
        "max_tokens": 800
    }

    headers = {
        "Authorization": f"Bearer {Config.MEGALLLM_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(Config.MEGALLLM_API_URL, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    raw_content = response.json()["choices"][0]["message"]["content"]
    return json.loads(raw_content)
