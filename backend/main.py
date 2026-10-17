
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# Load the configuration from backend/.env
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

load_dotenv(BASE_DIR / ".env")

# Allow Python to import the sibling AI folder
sys.path.insert(0, str(PROJECT_DIR))

from AI.gemini_service import generate_response

app = FastAPI(title="HackCellence Starter API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AIRequest(BaseModel):
    prompt: str


@app.get("/")
def home():
    return {"message": "HackCellence backend is running!"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/demo")
def demo(payload: dict):
    return {
        "success": True,
        "received": payload,
        "message": "Your first API workflow works!"
    }


@app.post("/api/ai")
def ask_ai(request: AIRequest):
    try:
        answer = generate_response(request.prompt)
        return {"success": True, "answer": answer}

    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    except Exception:
        raise HTTPException(
            status_code=502,
            detail="AI request failed. Check your model ID, API key and quota."
        )
