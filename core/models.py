from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class Candidate(BaseModel):
    cand_id: str
    type: Literal["exploit", "explore"]
    instruct: str
    rationale: str
    audio_path: Optional[str] = None  # Relative path for frontend
    audio_full_path: Optional[str] = None # Absolute path for server
    rating: Optional[int] = None
    is_best: bool = False

class Iteration(BaseModel):
    iter: int
    candidates: List[Candidate]
    user_note: Optional[str] = None

class SessionSettings(BaseModel):
    language: str = "zh"
    preview_text: str
    candidates_per_iter: int = 3
    lock_text: bool = True
    max_iters: int = 20
    dedup_threshold: float = 0.92

class Session(BaseModel):
    session_id: str
    created_at: str
    settings: SessionSettings
    iterations: List[Iteration] = []
    
    # Metadata for external tools
    tts_space: Dict[str, str] = {"repo": "Qwen/Qwen3-TTS-Voice-Design"}
    llm_model: Dict[str, str] = {"repo": "Qwen/Qwen2.5-72B-Instruct"}

class Feedback(BaseModel):
    iter: int
    ratings: Dict[str, int]  # cand_id -> rating
    best_id: str
    user_note: Optional[str] = None
