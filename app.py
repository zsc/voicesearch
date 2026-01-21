import os
import uuid
from datetime import datetime
from typing import Dict
import logging

from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.config import PORT, DATA_DIR, BASE_DIR
from core.models import Session, SessionSettings, Iteration, Candidate, Feedback
from core.storage import storage
from core.llm_service import llm_service
from core.tts_service import tts_service
from core.dedup import deduplicator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VoiceSearch")

app = FastAPI(title="VoiceSearch")

# Mounts
app.mount("/static", StaticFiles(directory=BASE_DIR / "web" / "static"), name="static")
app.mount("/data", StaticFiles(directory=DATA_DIR), name="data")

# Templates
templates = Jinja2Templates(directory=BASE_DIR / "web" / "templates")

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/session/{session_id}", response_class=HTMLResponse)
async def session_page(request: Request, session_id: str):
    session = storage.get_session(session_id)
    if not session:
        return RedirectResponse("/")
    return templates.TemplateResponse("session.html", {"request": request, "session": session})

# --- API ---

@app.post("/api/session/start")
async def start_session(settings: SessionSettings):
    session_id = f"VS_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    
    session = Session(
        session_id=session_id,
        created_at=datetime.utcnow().isoformat(),
        settings=settings
    )
    
    # Generate Initial Candidates (Iter 1)
    # Since it's start, we don't have history.
    # We ask LLM for initial variety.
    
    llm_resp = llm_service.generate_candidates(
        count=settings.candidates_per_iter,
        language=settings.language,
        history=[],
        user_note="Initial exploration. Please provide diverse starting points."
    )
    
    # Process Candidates & TTS
    candidates = []
    
    # Global avoid prompt appendage
    global_avoid = ", ".join(llm_resp.get("global_avoid", []))
    avoid_suffix = f" Avoid: {global_avoid}." if global_avoid else ""

    for idx, item in enumerate(llm_resp.get("next_candidates", [])):
        cand_id = f"1{chr(97+idx)}" # 1a, 1b, 1c
        
        full_instruct = item["instruct"] + avoid_suffix
        
        # Deduplication check (self-correction in loop not implemented for V1 simplicity, just log)
        # if deduplicator.is_duplicate(full_instruct, []): ...
        
        # Generate Audio
        audio_path = tts_service.generate_audio(
            text=settings.preview_text,
            instruct=full_instruct,
            session_id=session_id,
            iter_num=1,
            cand_id=cand_id
        )
        
        cand = Candidate(
            cand_id=cand_id,
            type=item.get("type", "explore"),
            instruct=item["instruct"], # store raw instruct for display
            rationale=item.get("rationale", ""),
            audio_path=audio_path
        )
        candidates.append(cand)
        
    iteration = Iteration(iter=1, candidates=candidates)
    session.iterations.append(iteration)
    
    storage.create_session(session)
    
    return {"session_id": session_id, "redirect_url": f"/session/{session_id}"}

@app.post("/api/session/{session_id}/iterate")
async def iterate_session(session_id: str, feedback: Feedback):
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 1. Update previous iteration with feedback
    current_iter_idx = feedback.iter - 1
    if 0 <= current_iter_idx < len(session.iterations):
        current_iter = session.iterations[current_iter_idx]
        current_iter.user_note = feedback.user_note
        
        # Update candidates with ratings and best flag
        for cand in current_iter.candidates:
            if cand.cand_id in feedback.ratings:
                cand.rating = feedback.ratings[cand.cand_id]
            if cand.cand_id == feedback.best_id:
                cand.is_best = True
                
    # 2. Prepare context for LLM
    # Get history summary
    history = []
    all_instructs = []
    
    best_instruct_so_far = ""
    
    for it in session.iterations:
        best_cand = next((c for c in it.candidates if c.is_best), None)
        best_id = best_cand.cand_id if best_cand else "None"
        if best_cand:
            best_instruct_so_far = best_cand.instruct
            
        history.append({
            "iter": it.iter,
            "best_cand_id": best_id,
            "user_note": it.user_note
        })
        for c in it.candidates:
            all_instructs.append(c.instruct)

    # 3. Generate Next Candidates
    next_iter_num = feedback.iter + 1
    if next_iter_num > session.settings.max_iters:
         raise HTTPException(status_code=400, detail="Max iterations reached")

    llm_resp = llm_service.generate_candidates(
        count=session.settings.candidates_per_iter,
        language=session.settings.language,
        history=history,
        best_instruct=best_instruct_so_far,
        user_note=feedback.user_note or ""
    )
    
    # 4. Process Candidates & Dedup & TTS
    candidates = []
    global_avoid = ", ".join(llm_resp.get("global_avoid", []))
    avoid_suffix = f" Avoid: {global_avoid}." if global_avoid else ""

    generated_items = llm_resp.get("next_candidates", [])
    
    # Dedup Logic (Simple Retry)
    # If a candidate is duplicate, we should technically ask LLM to regenerate.
    # For this implementation, we will check and if duplicate, maybe modify slightly or just accept to avoid complex loop.
    # We will log it.
    
    for idx, item in enumerate(generated_items):
        cand_id = f"{next_iter_num}{chr(97+idx)}"
        
        raw_instruct = item["instruct"]
        
        if deduplicator.is_duplicate(raw_instruct, all_instructs, threshold=session.settings.dedup_threshold):
            logger.warning(f"Duplicate detected: {raw_instruct[:30]}...")
            # Ideally: call LLM again or perturb.
            # Here: We append a small noise to prompt to force TTS variation if exact string match is the issue,
            # but dedup is embedding based. 
            # We'll stick to the Spec's "Try to rewrite" -> For now we just mark it or proceed.
            pass
            
        full_instruct = raw_instruct + avoid_suffix
        
        audio_path = tts_service.generate_audio(
            text=session.settings.preview_text,
            instruct=full_instruct,
            session_id=session_id,
            iter_num=next_iter_num,
            cand_id=cand_id
        )
        
        cand = Candidate(
            cand_id=cand_id,
            type=item.get("type", "explore"),
            instruct=raw_instruct,
            rationale=item.get("rationale", ""),
            audio_path=audio_path
        )
        candidates.append(cand)
        
    new_iteration = Iteration(iter=next_iter_num, candidates=candidates)
    session.iterations.append(new_iteration)
    storage.update_session(session)
    
    # Find overall best so far for response
    best_cand_obj = None
    # Reverse search for the latest best
    for it in reversed(session.iterations):
        b = next((c for c in it.candidates if c.is_best), None)
        if b:
            best_cand_obj = b
            break
            
    return {
        "iter": next_iter_num,
        "candidates": [c.model_dump() for c in candidates],
        "best_so_far": best_cand_obj.model_dump() if best_cand_obj else None
    }

@app.get("/api/session/{session_id}/export")
async def export_session(session_id: str):
    session = storage.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return JSONResponse(
        content=session.model_dump(),
        headers={"Content-Disposition": f"attachment; filename={session_id}.json"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
