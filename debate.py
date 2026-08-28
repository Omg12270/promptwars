"""
Multi-round Debate Engine — agents challenge each other's opinions.
Tracks opinion changes with before/after snapshots.
"""
import json
from groq_client import call_groq
from agents import AgentConfig, get_strictness_description

DEBATE_ROUND_PROMPT = """You are {agent_name} ({agent_role}).

You have already given your independent evaluation of the candidate. Now you are in a panel debate with other agents.

YOUR ORIGINAL EVALUATION:
{own_evaluation}

OTHER AGENTS' EVALUATIONS:
{other_evaluations}

{round_instructions}

Return JSON with this EXACT structure:
{{
    "agent_id": "{agent_id}",
    "agent_name": "{agent_name}",
    "responses": [
        {{
            "responding_to": "<agent name you're responding to>",
            "their_point": "<the specific point they made>",
            "your_response": "<your agreement, disagreement, or challenge>",
            "action": "agree" | "disagree" | "challenge" | "concede",
            "evidence": "<quote or fact supporting your response>"
        }}
    ],
    "opinion_changed": true | false,
    "change_details": {{
        "previous_score": <your original overall score>,
        "new_score": <updated score if changed, same if not>,
        "previous_recommendation": "<original recommendation>",
        "new_recommendation": "<updated recommendation if changed>",
        "reason_for_change": "<specific argument from another agent that convinced you, or why you held firm>",
        "convincing_evidence": "<the specific quote/fact that changed your mind, if applicable>"
    }},
    "final_position": "<your updated 2-3 sentence assessment after this debate round>"
}}

CRITICAL RULES:
- You MUST directly address at least one specific point from another agent
- If you disagree, explain WHY with evidence
- If another agent raises a valid point you missed, ACKNOWLEDGE it and adjust your score
- Don't just repeat your original opinion — engage with the debate
- Every response must reference specific evidence"""


async def run_debate_round(
    round_number: int,
    agent_config: AgentConfig,
    own_evaluation: dict,
    all_evaluations: list[dict],
    previous_debate: list[dict] | None,
    api_key: str,
) -> dict:
    """
    Run one round of debate for a single agent.
    Returns the agent's debate response with opinion change tracking.
    """
    # Format other agents' evaluations (excluding own)
    other_evals = []
    for ev in all_evaluations:
        if ev.get("agent_id") != agent_config.id:
            other_evals.append(
                f"--- {ev.get('agent_name', 'Unknown')} (Score: {ev.get('overall_score', '?')}/10, "
                f"Recommendation: {ev.get('recommendation', '?')}) ---\n"
                f"Summary: {ev.get('summary', 'No summary')}\n"
                f"Key Strengths: {json.dumps(ev.get('key_strengths', []))}\n"
                f"Key Concerns: {json.dumps(ev.get('key_concerns', []))}\n"
            )

    if round_number == 1:
        round_instructions = """This is ROUND 1 of the debate.
Read the other agents' evaluations carefully. You must:
1. Identify at least ONE point you disagree with from another agent and explain why
2. Identify at least ONE point from another agent that you think is valid
3. Decide if any of their arguments should change YOUR score"""
    else:
        prev_debate_text = ""
        if previous_debate:
            for pd in previous_debate:
                prev_debate_text += f"\n--- {pd.get('agent_name', '?')} (Round {round_number - 1}) ---\n"
                for resp in pd.get("responses", []):
                    prev_debate_text += (
                        f"  → To {resp.get('responding_to', '?')}: "
                        f"{resp.get('your_response', '')} [{resp.get('action', '')}]\n"
                    )
                if pd.get("opinion_changed"):
                    cd = pd.get("change_details", {})
                    prev_debate_text += (
                        f"  ★ Changed score: {cd.get('previous_score')} → {cd.get('new_score')} "
                        f"because: {cd.get('reason_for_change', 'not specified')}\n"
                    )

        round_instructions = f"""This is ROUND {round_number} of the debate.

PREVIOUS ROUND'S DEBATE:
{prev_debate_text}

Now respond to what was said in the previous round. You must:
1. Address any challenges directed at YOU specifically
2. Respond to any opinion changes — do you agree with the change?
3. Make your FINAL position clear"""

    strictness_desc = get_strictness_description(agent_config.strictness)
    system_prompt = agent_config.system_prompt.replace("{strictness_desc}", strictness_desc)

    user_prompt = DEBATE_ROUND_PROMPT.format(
        agent_name=agent_config.name,
        agent_role=agent_config.role,
        agent_id=agent_config.id,
        own_evaluation=json.dumps(own_evaluation, indent=2),
        other_evaluations="\n".join(other_evals),
        round_instructions=round_instructions,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    result = await call_groq(messages, api_key=api_key, temperature=0.6)
    result["agent_id"] = agent_config.id
    result["agent_name"] = agent_config.name
    result["round"] = round_number
    return result


async def run_full_debate(
    agent_configs: list[AgentConfig],
    evaluations: list[dict],
    api_key: str,
    num_rounds: int = 2,
    progress_callback=None,
) -> dict:
    """
    Run the full multi-round debate across all agents.
    Returns debate transcript with opinion change tracking.
    """
    debate_rounds = []
    current_evaluations = evaluations.copy()

    for round_num in range(1, num_rounds + 1):
        if progress_callback:
            await progress_callback(f"debate_round_{round_num}", f"Starting debate round {round_num}...")

        round_results = []
        previous_round = debate_rounds[-1] if debate_rounds else None

        for agent_config in agent_configs:
            # Find this agent's evaluation
            own_eval = next(
                (e for e in current_evaluations if e.get("agent_id") == agent_config.id),
                {},
            )

            if progress_callback:
                await progress_callback(
                    f"debate_round_{round_num}",
                    f"{agent_config.icon} {agent_config.name} is responding..."
                )

            result = await run_debate_round(
                round_number=round_num,
                agent_config=agent_config,
                own_evaluation=own_eval,
                all_evaluations=current_evaluations,
                previous_debate=previous_round,
                api_key=api_key,
            )
            round_results.append(result)

            # Update evaluations if opinion changed
            if result.get("opinion_changed"):
                change = result.get("change_details", {})
                for ev in current_evaluations:
                    if ev.get("agent_id") == agent_config.id:
                        if "new_score" in change and change["new_score"] is not None:
                            ev["overall_score"] = change["new_score"]
                        if "new_recommendation" in change and change["new_recommendation"]:
                            ev["recommendation"] = change["new_recommendation"]
                        break

        debate_rounds.append(round_results)

    # Compile opinion change summary
    opinion_changes = []
    for round_idx, round_data in enumerate(debate_rounds):
        for agent_result in round_data:
            if agent_result.get("opinion_changed"):
                change = agent_result.get("change_details", {})
                opinion_changes.append({
                    "agent": agent_result.get("agent_name"),
                    "round": round_idx + 1,
                    "previous_score": change.get("previous_score"),
                    "new_score": change.get("new_score"),
                    "previous_recommendation": change.get("previous_recommendation"),
                    "new_recommendation": change.get("new_recommendation"),
                    "reason": change.get("reason_for_change"),
                    "evidence": change.get("convincing_evidence"),
                })

    return {
        "rounds": debate_rounds,
        "opinion_changes": opinion_changes,
        "final_evaluations": current_evaluations,
        "num_rounds": num_rounds,
    }
