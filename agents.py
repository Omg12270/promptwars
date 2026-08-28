"""
Agent definitions — base class + 4 default agents + custom agent support.
Each agent evaluates independently via a separate LLM call.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from groq_client import call_groq

CUSTOM_AGENTS_FILE = "custom_agents.json"


@dataclass
class AgentConfig:
    """Configuration for an AI interview panel agent."""
    id: str
    name: str
    role: str
    system_prompt: str
    evaluation_criteria: list[str]
    strictness: int = 5  # 1-10 scale
    weight: float = 1.0  # weight in final decision
    color: str = "#6366f1"  # accent color for UI
    icon: str = "🤖"  # emoji icon
    is_default: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ─── Default Agent Definitions ────────────────────────────────────────────────

TECHNICAL_AGENT = AgentConfig(
    id="technical",
    name="Technical Evaluator",
    role="Evaluates technical skills, system design depth, and hands-on engineering ability",
    icon="⚙️",
    color="#3b82f6",
    system_prompt="""You are a Senior Technical Interviewer with 15+ years of experience in AI/ML engineering.
Your job is to evaluate the candidate's TECHNICAL ability ONLY. You care about:
- Depth of technical knowledge (not just buzzwords)
- System design thinking and architecture decisions
- Hands-on coding and debugging ability
- Understanding of AI/ML concepts (RAG, multi-agent systems, prompt engineering)
- Whether their technical claims hold up under scrutiny

You are {strictness_desc}. 

CRITICAL RULES:
- Every score MUST reference a specific quote from the transcript or fact from the resume
- If you can't find evidence for something, score it as "insufficient data" — do NOT guess
- Focus ONLY on technical aspects — leave culture/teamwork to other agents""",
    evaluation_criteria=[
        "Technical depth & system design",
        "AI/LLM practical experience",
        "Problem-solving approach",
        "Architecture decisions & trade-offs",
        "Production engineering skills",
    ],
    strictness=6,
)

HR_CULTURE_AGENT = AgentConfig(
    id="hr_culture",
    name="HR & Culture Analyst",
    role="Evaluates communication skills, teamwork, honesty, and cultural fit",
    icon="🤝",
    color="#8b5cf6",
    system_prompt="""You are a Senior HR Director specializing in culture assessment and behavioral interviewing.
Your job is to evaluate the candidate's SOFT SKILLS and CULTURE FIT. You care about:
- Communication clarity and style
- Honesty and self-awareness (do they acknowledge weaknesses?)
- Teamwork and collaboration signals
- Growth mindset vs. fixed mindset
- How they handle conflict and disagreement
- Red flags in how they describe past colleagues/employers

You are {strictness_desc}.

CRITICAL RULES:
- Every assessment MUST reference a specific quote from the transcript or fact from the resume
- Pay close attention to HOW they answer, not just WHAT they answer
- Look for patterns across multiple answers, not just individual responses
- If information is insufficient to judge something, say so explicitly""",
    evaluation_criteria=[
        "Communication clarity",
        "Honesty & self-awareness",
        "Teamwork & collaboration",
        "Growth mindset",
        "Conflict handling",
    ],
    strictness=5,
)

HIRING_MANAGER_AGENT = AgentConfig(
    id="hiring_manager",
    name="Hiring Manager",
    role="Evaluates overall fit for the specific role, ROI of hiring, and long-term potential",
    icon="📋",
    color="#10b981",
    system_prompt="""You are the Hiring Manager for this specific role. You've been running this team for 3 years.
Your job is to evaluate whether this candidate is WORTH HIRING for THIS SPECIFIC ROLE. You care about:
- Direct relevance of their experience to the job description
- How quickly they could become productive (ramp-up time)
- Long-term retention risk (will they stay?)
- Whether they'd actually improve the team or just be another body
- Cost-benefit: is this person worth the investment of onboarding?

You are {strictness_desc}.

CRITICAL RULES:
- Every assessment MUST reference the job description requirements AND the candidate's specific evidence
- Compare what the role NEEDS vs. what the candidate OFFERS — don't just list strengths
- Be explicit about gaps between role requirements and candidate capabilities
- Consider both short-term productivity and long-term growth potential""",
    evaluation_criteria=[
        "Role-specific experience match",
        "Ramp-up time estimate",
        "Retention risk",
        "Team impact potential",
        "Cost-benefit assessment",
    ],
    strictness=5,
)

SKEPTIC_AGENT = AgentConfig(
    id="skeptic",
    name="Devil's Advocate",
    role="Looks for contradictions, exaggerations, red flags, and unstated risks",
    icon="🔍",
    color="#ef4444",
    system_prompt="""You are a professional Skeptic and Devil's Advocate on hiring panels.
Your job is to CHALLENGE everything and find what others might miss. You care about:
- Contradictions between the resume and transcript
- Exaggerated claims or inflated titles
- Vague answers that dodge the actual question
- Missing context or suspiciously absent details
- Patterns that suggest the candidate is hiding something
- Whether impressive-sounding achievements are actually their work

You are {strictness_desc}.

CRITICAL RULES:
- Every concern MUST be backed by a specific quote or factual inconsistency
- Don't be contrarian for its own sake — only flag REAL concerns with evidence
- If the candidate IS being honest and transparent, acknowledge that too
- Cross-reference resume claims with transcript answers for consistency
- Pay special attention to ownership claims — "I built" vs "the team built" """,
    evaluation_criteria=[
        "Resume-transcript consistency",
        "Claim verification",
        "Red flag detection",
        "Honesty assessment",
        "Risk identification",
    ],
    strictness=8,
)

DEFAULT_AGENTS = [TECHNICAL_AGENT, HR_CULTURE_AGENT, HIRING_MANAGER_AGENT, SKEPTIC_AGENT]


def get_strictness_description(level: int) -> str:
    """Convert strictness number to a natural language description for the prompt."""
    descriptions = {
        1: "extremely lenient — you give candidates every benefit of the doubt",
        2: "very lenient — you focus mostly on positives",
        3: "lenient — you lean toward favorable interpretations",
        4: "slightly lenient — you're fair but tend to be generous",
        5: "balanced — you weigh positives and negatives equally",
        6: "slightly strict — you hold candidates to a solid standard",
        7: "strict — you expect strong evidence for every claim",
        8: "very strict — you're hard to impress and skeptical by default",
        9: "extremely strict — only exceptional candidates get good scores",
        10: "ruthlessly strict — you find flaws in even the best candidates",
    }
    return descriptions.get(level, descriptions[5])


EVALUATION_PROMPT = """Evaluate this candidate based on your role and criteria.

--- JOB DESCRIPTION ---
{job_description}

--- CANDIDATE PROFILE ---
{profile_json}

--- RESUME ---
{resume_text}

--- INTERVIEW TRANSCRIPT ---
{transcript_text}

Return your evaluation as JSON with this EXACT structure:
{{
    "agent_id": "{agent_id}",
    "agent_name": "{agent_name}",
    "overall_score": <number 1-10>,
    "confidence": <number 0.0-1.0, how confident you are in your assessment>,
    "recommendation": "strong_hire" | "hire" | "lean_hire" | "lean_no_hire" | "no_hire" | "strong_no_hire",
    "criteria_scores": [
        {{
            "criterion": "<criterion name>",
            "score": <number 1-10>,
            "evidence": "<specific quote or fact>",
            "reasoning": "<why this score>"
        }}
    ],
    "key_strengths": [
        {{
            "strength": "<description>",
            "evidence": "<specific quote or fact>"
        }}
    ],
    "key_concerns": [
        {{
            "concern": "<description>",
            "evidence": "<specific quote or fact>"
        }}
    ],
    "insufficient_data": ["<areas where you couldn't make a judgment due to missing info>"],
    "summary": "<2-3 sentence overall assessment>"
}}

REMEMBER: Every score and assessment MUST cite a specific quote or fact. No unexplained numbers."""


async def evaluate_candidate(
    agent_config: AgentConfig,
    profile: dict,
    resume_text: str,
    transcript_text: str,
    job_description: str,
    api_key: str,
) -> dict:
    """
    Run a single agent's independent evaluation of a candidate.
    Each call is a separate LLM invocation — agents don't see each other's results.
    """
    strictness_desc = get_strictness_description(agent_config.strictness)
    system_prompt = agent_config.system_prompt.replace("{strictness_desc}", strictness_desc)

    user_prompt = EVALUATION_PROMPT.format(
        job_description=job_description,
        profile_json=json.dumps(profile, indent=2),
        resume_text=resume_text,
        transcript_text=transcript_text,
        agent_id=agent_config.id,
        agent_name=agent_config.name,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    result = await call_groq(messages, api_key=api_key, temperature=0.5)
    # Ensure agent metadata is present
    result["agent_id"] = agent_config.id
    result["agent_name"] = agent_config.name
    result["agent_icon"] = agent_config.icon
    result["agent_color"] = agent_config.color
    result["agent_weight"] = agent_config.weight
    return result


# ─── Custom Agent Management ─────────────────────────────────────────────────

def load_custom_agents() -> list[AgentConfig]:
    """Load user-defined custom agents from JSON file."""
    if not os.path.exists(CUSTOM_AGENTS_FILE):
        return []
    try:
        with open(CUSTOM_AGENTS_FILE, "r") as f:
            data = json.load(f)
        return [AgentConfig.from_dict(a) for a in data]
    except (json.JSONDecodeError, KeyError):
        return []


def save_custom_agents(agents: list[AgentConfig]):
    """Save custom agent configs to JSON file."""
    with open(CUSTOM_AGENTS_FILE, "w") as f:
        json.dump([a.to_dict() for a in agents], f, indent=2)


def get_all_agents() -> list[AgentConfig]:
    """Get all agents (defaults + custom)."""
    custom = load_custom_agents()
    # Custom agents can override defaults by matching id
    custom_ids = {a.id for a in custom}
    result = [a for a in DEFAULT_AGENTS if a.id not in custom_ids]
    result.extend(custom)
    return result


def update_agent(agent_data: dict) -> AgentConfig:
    """Create or update a custom agent."""
    agent_data["is_default"] = False
    agent = AgentConfig.from_dict(agent_data)
    custom = load_custom_agents()
    # Replace if exists, append if new
    custom = [a for a in custom if a.id != agent.id]
    custom.append(agent)
    save_custom_agents(custom)
    return agent


def delete_custom_agent(agent_id: str) -> bool:
    """Delete a custom agent. Cannot delete default agents."""
    custom = load_custom_agents()
    new_custom = [a for a in custom if a.id != agent_id]
    if len(new_custom) == len(custom):
        return False
    save_custom_agents(new_custom)
    return True


def reset_agent_to_default(agent_id: str) -> Optional[AgentConfig]:
    """Reset a modified default agent back to its original config."""
    defaults = {a.id: a for a in DEFAULT_AGENTS}
    if agent_id not in defaults:
        return None
    # Remove the custom override
    custom = load_custom_agents()
    custom = [a for a in custom if a.id != agent_id]
    save_custom_agents(custom)
    return defaults[agent_id]
