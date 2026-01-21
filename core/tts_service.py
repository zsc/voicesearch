import os
import json
import base64
import logging
import requests
from pathlib import Path
from .config import DASHSCOPE_API_KEY, DATA_DIR

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        if not DASHSCOPE_API_KEY:
            logger.warning("DASHSCOPE_API_KEY (or API_KEY) is not set. TTS generation will fail.")

    def generate_audio(self, text: str, instruct: str, session_id: str, iter_num: int, cand_id: str) -> str:
        """
        Generates audio using DashScope API and saves it to the session data directory.
        Returns the relative path for the web frontend.
        """
        # Prepare Output Path
        output_dir = DATA_DIR / "sessions" / session_id / f"iter_{iter_num}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"cand_{cand_id}.wav"
        output_path = output_dir / filename
        relative_path = f"/data/sessions/{session_id}/iter_{iter_num}/{filename}"

        if output_path.exists():
            return relative_path

        logger.info(f"Generating TTS for {cand_id} via DashScope...")
        
        try:
            url = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DASHSCOPE_API_KEY}"
            }

            data = {
                "model": "qwen-voice-design",
                "input": {
                    "action": "create",
                    "voice_prompt": instruct,
                    "preview_text": text,
                    "target_model": "qwen3-tts-vd-realtime-2025-12-16",
                    "preferred_name": "default"
                },
                "parameters": {
                    "sample_rate": 24000,
                    "response_format": "wav"
                }
            }

            response = requests.post(url, headers=headers, data=json.dumps(data))

            if response.status_code == 200:
                res_json = response.json()
                if 'output' in res_json and 'preview_audio' in res_json['output']:
                    base64_audio = res_json['output']['preview_audio']['data']
                    audio_bytes = base64.b64decode(base64_audio)
                    
                    # Write bytes directly to file
                    with open(output_path, "wb") as f:
                        f.write(audio_bytes)
                        
                    return relative_path
                else:
                    error_msg = f"DashScope Response Error: {res_json}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            else:
                error_msg = f"DashScope API Error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise ValueError(error_msg)

        except Exception as e:
            logger.error(f"TTS Generation failed for {cand_id}: {e}")
            # Generate silent placeholder to prevent UI crash
            try:
                import soundfile as sf
                import numpy as np
                sr = 24000
                silence = np.zeros(sr)
                sf.write(output_path, silence, sr)
            except Exception as e2:
                logger.error(f"Failed to create silence placeholder: {e2}")
            
            return relative_path

tts_service = TTSService()
