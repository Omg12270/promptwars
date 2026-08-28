"""
FastAPI server — serves the frontend + API for the Multi-Agent Interview Panel Simulator.
"""
import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from profile_builder import build_candidate_profile
from agents import (
    AgentConfig,
    get_all_agents,
    evaluate_candidate,
    update_agent,
    delete_custom_agent,
    reset_agent_to_default,
    DEFAULT_AGENTS,
)
from debate import run_full_debate
from decision import make_final_decision

app = FastAPI(title="AI Interview Panel Simulator")

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Data directory
DATA_DIR = Path(__file__).parent / "data"

# In-memory job store for SSE streaming
jobs: dict[str, dict] = {}


def load_data_file(filename: str) -> str:
    """Load a text file from the data directory."""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Data file not found: {filepath}")
    return filepath.read_text(encoding="utf-8")


# ─── Frontend ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main HTML page."""
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ─── Agent Management API ────────────────────────────────────────────────────

@app.get("/api/agents")
async def get_agents():
    """Get all agent configurations (defaults + custom)."""
    agents = get_all_agents()
    return [a.to_dict() for a in agents]


@app.get("/api/agents/defaults")
async def get_default_agents():
    """Get default agent configurations."""
    return [a.to_dict() for a in DEFAULT_AGENTS]


@app.post("/api/agents")
async def save_agent(request: Request):
    """Create or update a custom agent."""
    data = await request.json()
    agent = update_agent(data)
    return agent.to_dict()


@app.delete("/api/agents/{agent_id}")
async def remove_agent(agent_id: str):
    """Delete a custom agent."""
    success = delete_custom_agent(agent_id)
    if success:
        return {"status": "deleted"}
    return JSONResponse(status_code=404, content={"error": "Agent not found or is a default agent"})


@app.post("/api/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset a default agent to its original configuration."""
    agent = reset_agent_to_default(agent_id)
    if agent:
        return agent.to_dict()
    return JSONResponse(status_code=404, content={"error": "Not a default agent"})


# ─── Evaluation Pipeline API ─────────────────────────────────────────────────

@app.post("/api/evaluate")
async def start_evaluation(request: Request):
    """
    Start the full evaluation pipeline for a candidate.
    Returns a job_id for SSE streaming.
    """
    data = await request.json()
    api_key = data.get("api_key", "")
    candidate = data.get("candidate", "a")  # "a" or "b"
    agent_ids = data.get("agent_ids", None)  # None = use all agents

    if not api_key:
        return JSONResponse(status_code=400, content={"error": "API key is required"})

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "events": [],
        "result": None,
        "candidate": candidate,
    }

    # Start pipeline in background
    asyncio.create_task(
        run_pipeline(job_id, api_key, candidate, agent_ids)
    )

    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
async def stream_status(job_id: str):
    """SSE stream for real-time pipeline progress."""
    if job_id not in jobs:
        return JSONResponse(status_code=404, content={"error": "Job not found"})

    async def event_generator():
        last_index = 0
        while True:
            job = jobs.get(job_id)
            if not job:
                break

            # Send new events
            events = job["events"]
            while last_index < len(events):
                event = events[last_index]
                yield f"data: {json.dumps(event)}\n\n"
                last_index += 1

            if job["status"] in ("completed", "error"):
                # Send final result
                if job["result"]:
                    yield f"data: {json.dumps({'type': 'result', 'data': job['result']})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'status': job['status']})}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def run_pipeline(job_id: str, api_key: str, candidate: str, agent_ids: list[str] | None):
    """
    Full evaluation pipeline:
    1. Build candidate profile
    2. Independent agent evaluations
    3. Multi-round debate
    4. Final decision
    """
    job = jobs[job_id]

    def emit(event_type: str, message: str, data: dict | None = None):
        event = {"type": event_type, "message": message}
        if data:
            event["data"] = data
        job["events"].append(event)

    try:
        job["status"] = "running"

        # Load data
        if candidate.lower() not in ("a", "b"):
            raise ValueError("candidate must be 'a' or 'b'")
        suffix = candidate.lower()
        resume_text = load_data_file(f"resume_{suffix}.txt")
        transcript_text = load_data_file(f"transcript_{suffix}.txt")
        job_description = load_data_file("job_description.txt")

        # Step 1: Build profile
        emit("stage", "📋 Building candidate profile...", {"stage": "profile"})
        profile = await build_candidate_profile(
            resume_text, transcript_text, job_description, api_key
        )
        emit("profile", "✅ Candidate profile built", {"profile": profile})

        # Step 2: Independent evaluations
        all_agents = get_all_agents()
        if agent_ids:
            all_agents = [a for a in all_agents if a.id in agent_ids]

        if len(all_agents) < 2:
            raise ValueError("At least 2 agents are required for a debate")

        emit("stage", f"🤖 Running {len(all_agents)} independent evaluations...", {"stage": "evaluation"})

        evaluations = []
        for agent in all_agents:
            emit("agent_start", f"{agent.icon} {agent.name} is evaluating...", {"agent_id": agent.id})
            evaluation = await evaluate_candidate(
                agent, profile, resume_text, transcript_text, job_description, api_key
            )
            evaluations.append(evaluation)
            emit("agent_done", f"{agent.icon} {agent.name} completed evaluation", {
                "agent_id": agent.id,
                "evaluation": evaluation,
            })

        emit("evaluations_complete", "✅ All agents completed independent evaluations", {
            "evaluations": evaluations,
        })

        # Step 3: Debate
        emit("stage", "💬 Starting multi-round debate...", {"stage": "debate"})

        async def debate_progress(stage, msg):
            emit("debate_progress", msg, {"stage": stage})

        debate_result = await run_full_debate(
            all_agents, evaluations, api_key, num_rounds=1, progress_callback=debate_progress
        )
        emit("debate_complete", "✅ Debate completed", {"debate": debate_result})

        # Step 4: Final decision
        emit("stage", "⚖️ Making final decision...", {"stage": "decision"})
        final_decision = await make_final_decision(
            profile,
            debate_result["final_evaluations"],
            debate_result,
            job_description,
            api_key,
        )
        emit("decision", "✅ Final decision reached", {"decision": final_decision})

        # Compile full result
        full_result = {
            "candidate": candidate.upper(),
            "profile": profile,
            "evaluations": evaluations,
            "debate": debate_result,
            "final_decision": final_decision,
        }

        job["result"] = full_result
        job["status"] = "completed"
        emit("complete", "🎉 Evaluation complete!")

    except Exception as e:
        job["status"] = "error"
        emit("error", f"❌ Error: {str(e)}", {"error": str(e)})


# ─── Comparison Endpoint (Bonus) ─────────────────────────────────────────────

@app.post("/api/compare")
async def compare_candidates(request: Request):
    """Compare two candidates side-by-side (bonus feature)."""
    data = await request.json()
    result_a = data.get("result_a")
    result_b = data.get("result_b")

    if not result_a or not result_b:
        return JSONResponse(status_code=400, content={"error": "Both candidate results are required"})

    comparison = {
        "candidate_a": {
            "name": result_a.get("profile", {}).get("name", "Candidate A"),
            "score": result_a.get("final_decision", {}).get("overall_score", "N/A"),
            "recommendation": result_a.get("final_decision", {}).get("final_recommendation", "N/A"),
            "confidence": result_a.get("final_decision", {}).get("confidence", "N/A"),
        },
        "candidate_b": {
            "name": result_b.get("profile", {}).get("name", "Candidate B"),
            "score": result_b.get("final_decision", {}).get("overall_score", "N/A"),
            "recommendation": result_b.get("final_decision", {}).get("final_recommendation", "N/A"),
            "confidence": result_b.get("final_decision", {}).get("confidence", "N/A"),
        },
    }

    return comparison


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
