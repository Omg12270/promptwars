"""
Candidate Profile Builder — extracts structured profile from resume + transcript.
"""
from groq_client import call_groq

PROFILE_SYSTEM_PROMPT = """You are an expert HR analyst. Given a candidate's resume and interview transcript, 
extract a structured profile. Be factual — only include what is explicitly stated or directly inferable.

Return JSON with this exact structure:
{
    "name": "Candidate full name",
    "current_title": "Most recent job title",
    "years_of_experience": number,
    "skills": {
        "technical": ["list of technical skills mentioned"],
        "soft": ["list of soft skills demonstrated"]
    },
    "experience_timeline": [
        {
            "role": "Job title",
            "company": "Company name",
            "duration": "e.g. Jan 2024 - Present, 11 months",
            "key_achievements": ["list of claims/achievements"],
            "technologies_used": ["specific tech mentioned"]
        }
    ],
    "education": "Degree and year",
    "claims_made": [
        {
            "claim": "What the candidate claims",
            "source": "resume or transcript",
            "quote": "Exact supporting quote if from transcript",
            "verifiable": true/false
        }
    ],
    "red_flags": [
        {
            "issue": "Description of potential concern",
            "evidence": "Quote or fact supporting this concern",
            "severity": "low/medium/high"
        }
    ],
    "strengths_observed": [
        {
            "strength": "Description",
            "evidence": "Supporting quote or fact"
        }
    ],
    "missing_info": ["List of things that couldn't be determined from available data"]
}"""


async def build_candidate_profile(
    resume_text: str,
    transcript_text: str,
    job_description: str,
    api_key: str,
) -> dict:
    """
    Build a structured candidate profile from resume and transcript.
    Returns a CandidateProfile dict.
    """
    user_prompt = f"""Analyze this candidate for the following job:

--- JOB DESCRIPTION ---
{job_description}

--- RESUME ---
{resume_text}

--- INTERVIEW TRANSCRIPT ---
{transcript_text}

Extract a complete, evidence-based candidate profile. For every claim, include the exact quote or source.
Flag any contradictions between the resume and transcript.
Note any areas where information is insufficient to make a judgment."""

    messages = [
        {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    profile = await call_groq(messages, api_key=api_key, temperature=0.3)
    return profile
