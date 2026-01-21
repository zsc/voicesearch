import json
from pathlib import Path
from typing import Dict, Optional
from .models import Session
from .config import DATA_DIR, TEMP_DIR

class SessionStorage:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create_session(self, session: Session) -> Session:
        self._sessions[session.session_id] = session
        self.save_session(session.session_id)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def update_session(self, session: Session):
        self._sessions[session.session_id] = session
        self.save_session(session.session_id)

    def save_session(self, session_id: str):
        session = self.get_session(session_id)
        if not session:
            return

        # Prepare JSON content
        json_content = session.model_dump_json(indent=2)

        # 1. Save to Temp (for quick recovery/debug)
        temp_path = TEMP_DIR / f"voicesearch_{session_id}.json"
        try:
            temp_path.write_text(json_content, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Failed to write to temp storage: {e}")

        # 2. Save to Data Dir (Project persistent storage)
        # Create session dir if not exists
        session_dir = DATA_DIR / "sessions" / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        final_path = session_dir / "session.json"
        try:
            final_path.write_text(json_content, encoding="utf-8")
        except Exception as e:
            print(f"Error: Failed to write session to data dir: {e}")

# Global instance
storage = SessionStorage()
