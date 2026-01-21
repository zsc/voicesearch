import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from huggingface_hub import InferenceClient
from jinja2 import Template

from .config import HF_TOKEN, LLM_MODEL_REPO, BASE_DIR
from .models import Candidate

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        if not HF_TOKEN:
            logger.warning("HF_TOKEN is not set. LLM calls might fail if not authenticated.")
        self.client = InferenceClient(token=HF_TOKEN)
        self.model = LLM_MODEL_REPO
        
        # Load prompt template
        template_path = BASE_DIR / "core" / "prompt_templates" / "next_instruct_v1.txt"
        self.template = Template(template_path.read_text(encoding="utf-8"))

    def generate_candidates(self, 
                            count: int, 
                            language: str, 
                            history: List[Dict[str, Any]], 
                            best_instruct: str = "None",
                            user_note: str = "None") -> Dict[str, Any]:
        
        # Format history for prompt
        history_summary = ""
        for item in history:
            history_summary += f"- Iter {item['iter']}: Best was '{item['best_cand_id']}'. Note: {item.get('user_note', 'None')}\n"
            
        prompt = self.template.render(
            count=count,
            language="Chinese (Simplified)" if language == "zh" else "English",
            best_instruct=best_instruct,
            user_note=user_note,
            history_len=len(history),
            history_summary=history_summary
        )

        messages = [
            {"role": "system", "content": "You are a helpful assistant that outputs JSON only."}, 
            {"role": "user", "content": prompt}
        ]

        logger.info("Calling LLM for new candidates...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
                response_format={"type": "json_object"} # Use structured output if available or just hope
            )
            
            content = response.choices[0].message.content
            # Clean potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
                
            data = json.loads(content)
            return data

        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            # Fallback for error cases
            return {
                "next_candidates": [
                    {
                        "type": "exploit",
                        "instruct": f"Error in generation: {str(e)}. Please retry.",
                        "rationale": "System error fallback."
                    }
                ],
                "global_avoid": []
            }

llm_service = LLMService()
