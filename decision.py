"""
Final Decision Engine — weighted evidence aggregation, NOT simple averaging.
"""
import json
from groq_client import call_groq


DECISION_PROMPT = """You are the Final Decision Synthesizer for a hiring panel. You have access to:
1. All agents' evaluations (post-debate, with any opinion changes applied)
2. The full debate transcript showing how agents challenged each other
3. Records of which agents changed their minds and why

Your job is to produce a FINAL HIRING DECISION that:
- Is NOT a simple average of scores
- Weighs evidence quality (backed by quotes) over bare scores
- Gives more weight to points that survived the debate unchallenged
- Gives more weight to agents with higher confidence
- Accounts for agent weights (some agents count more than others)
- Identifies consensus vs. unresolved disagreements

--- JOB DESCRIPTION ---
{job_description}

--- CANDIDATE PROFILE ---
{profile_json}

--- POST-DEBATE AGENT EVALUATIONS ---
{evaluations_json}

--- DEBATE SUMMARY ---
{debate_summary}

--- OPINION CHANGES DURING DEBATE ---
{opinion_changes}

Return JSON with this EXACT structure:
{{
    "candidate_name": "<name>",
    "final_recommendation": "strong_hire" | "hire" | "lean_hire" | "lean_no_hire" | "no_hire" | "strong_no_hire",
    "confidence": <0.0-1.0>,
    "overall_score": <1-10, weighted>,
    "reasoning": {{
        "key_factors_for": [
            {{
                "factor": "<why hire>",
                "supporting_agents": ["<agent names that support this>"],
                "evidence": "<strongest supporting quote/fact>",
                "weight": "<how much this influenced the decision>"
            }}
        ],
        "key_factors_against": [
            {{
                "factor": "<why not hire>",
                "supporting_agents": ["<agent names that raised this>"],
                "evidence": "<strongest supporting quote/fact>",
                "weight": "<how much this influenced the decision>"
            }}
        ],
        "debate_impact": "<how the debate changed the final picture vs. just averaging pre-debate scores>",
        "evidence_quality_assessment": "<were the agents' citations strong and verifiable?>"
    }},
    "strengths": [
        {{
            "strength": "<description>",
            "consensus_level": "unanimous" | "majority" | "contested",
            "evidence": "<supporting quote/fact>"
        }}
    ],
    "concerns": [
        {{
            "concern": "<description>",
            "severity": "critical" | "moderate" | "minor",
            "consensus_level": "unanimous" | "majority" | "contested",
            "evidence": "<supporting quote/fact>"
        }}
    ],
    "unresolved_disagreements": [
        {{
            "topic": "<what agents disagreed on>",
            "positions": [
                {{
                    "agent": "<agent name>",
                    "position": "<their stance>",
                    "evidence": "<their supporting evidence>"
                }}
            ],
            "impact_on_decision": "<how this disagreement affected the final call>"
        }}
    ],
    "decision_methodology": "<explain how you weighted the different inputs to reach this decision>",
    "risk_assessment": "<overall risk level of hiring this candidate and why>"
}}"""


async def make_final_decision(
    profile: dict,
    evaluations: list[dict],
    debate_result: dict,
    job_description: str,
    api_key: str,
) -> dict:
    """
    Produce the final hiring decision using weighted evidence aggregation.
    """
    # Build debate summary
    debate_summary_parts = []
    for round_idx, round_data in enumerate(debate_result.get("rounds", [])):
        debate_summary_parts.append(f"\n=== Round {round_idx + 1} ===")
        for agent_result in round_data:
            agent_name = agent_result.get("agent_name", "Unknown")
            debate_summary_parts.append(f"\n{agent_name}:")
            for resp in agent_result.get("responses", []):
                debate_summary_parts.append(
                    f"  → To {resp.get('responding_to', '?')}: "
                    f"[{resp.get('action', '?').upper()}] {resp.get('your_response', '')}"
                )
            if agent_result.get("opinion_changed"):
                cd = agent_result.get("change_details", {})
                debate_summary_parts.append(
                    f"  ★ OPINION CHANGED: Score {cd.get('previous_score')} → {cd.get('new_score')}"
                    f" | Reason: {cd.get('reason_for_change', 'not specified')}"
                )
            else:
                debate_summary_parts.append("  → Opinion unchanged")

    # Format opinion changes
    changes = debate_result.get("opinion_changes", [])
    if changes:
        changes_text = json.dumps(changes, indent=2)
    else:
        changes_text = "No agents changed their opinions during the debate."

    # Format evaluations with weights
    eval_with_weights = []
    for ev in evaluations:
        ev_copy = ev.copy()
        ev_copy["agent_weight_in_decision"] = ev.get("agent_weight", 1.0)
        eval_with_weights.append(ev_copy)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert hiring decision synthesizer. You produce evidence-based, "
                "nuanced hiring decisions that account for debate dynamics and evidence quality. "
                "You NEVER simply average scores — you weigh evidence, confidence, and debate outcomes."
            ),
        },
        {
            "role": "user",
            "content": DECISION_PROMPT.format(
                job_description=job_description,
                profile_json=json.dumps(profile, indent=2),
                evaluations_json=json.dumps(eval_with_weights, indent=2),
                debate_summary="\n".join(debate_summary_parts),
                opinion_changes=changes_text,
            ),
        },
    ]

    result = await call_groq(messages, api_key=api_key, temperature=0.3)
    return result
