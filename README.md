# Multi-Agent AI Interview Panel Simulator

A web application that simulates a hiring panel using multiple AI agents. Built with Python, FastAPI, and the Groq API (using `llama-3.3-70b-versatile`).

## Features

- **Multi-Agent Evaluation**: Independent evaluations by 4 distinct personas (Technical, HR/Culture, Hiring Manager, Skeptic).
- **Interactive Debate Engine**: Agents debate each other's points, challenge assumptions, and track opinion changes over multiple rounds.
- **Evidence-Based Decisions**: The final hiring decision is a synthesized, weighted consensus rather than a simple average, backed by quotes from the candidate's transcript and resume.
- **Customizable Agents**: Add, edit, or remove agents with custom personas, criteria, and strictness levels.
- **Real-Time Streaming UI**: Built with a sleek dark glassmorphism design, featuring SSE streaming for real-time progress updates.

## Architecture

- **Backend**: FastAPI
- **Frontend**: Vanilla HTML/CSS/JS
- **LLM**: Groq API (fast inference)

## Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the server:**
   ```bash
   python server.py
   ```
   (Alternatively, use `uvicorn server:app --reload`)

3. **Access the application:**
   Open your browser and navigate to `http://localhost:8000`.

4. **API Key:**
   You will need a free Groq API key to run the simulator. You can enter it directly in the web UI.

## Data

The `data/` directory contains pre-extracted text from the provided PDFs:
- Job Description
- Resumes (Candidate A & B)
- Interview Transcripts (Candidate A & B)
