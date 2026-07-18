import logging
import os
import time
from typing import Optional

from pydantic import BaseModel
from nemoguardrails import LLMRails, RailsConfig

from agent.config import settings

logger = logging.getLogger(__name__)


class GuardrailsResult(BaseModel):
    safe: bool
    reason: Optional[str] = None
    sanitized: Optional[str] = None
    latency_ms: float = 0.0


class GuardrailsEngine:
    """NeMo Guardrails integration for Compass."""

    def __init__(self):
        self.enabled = settings.get("guardrails.enabled", True)
        self.input_enabled = settings.get("guardrails.input_rails", True)
        self.output_enabled = settings.get("guardrails.output_rails", True)
        self.fail_open = settings.get("guardrails.fail_open", True)
        self._rails: Optional[LLMRails] = None
        self._setup_env()

    def _setup_env(self):
        """Set environment variables for the config.yml to pick up."""
        if not self.enabled:
            return
            
        # Get the model name, defaulting to OpenRouter via config
        guardrails_model = settings.get("model.guardrails", "google/gemma-4-31b-it:free")
        os.environ["COMPASS_MODEL_GUARDRAILS"] = guardrails_model
        
        # Ensure OPENROUTER_API_KEY is available (should be in .env)
        if not os.environ.get("OPENROUTER_API_KEY"):
            logger.warning("OPENROUTER_API_KEY not found. Guardrails may fail.")

    def _get_rails(self) -> LLMRails:
        if self._rails is None:
            # Load config from the current directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config = RailsConfig.from_path(current_dir)
            self._rails = LLMRails(config)
        return self._rails

    async def check_input(self, user_message: str) -> GuardrailsResult:
        """Run input rails on a user message."""
        if not self.enabled or not self.input_enabled:
            return GuardrailsResult(safe=True)

        start_time = time.time()
        try:
            rails = self._get_rails()
            # Generate response from guardrails
            response = await rails.generate_async(messages=[{"role": "user", "content": user_message}])
            
            latency_ms = (time.time() - start_time) * 1000
            
            # If the response indicates refusal, it's blocked
            if "I cannot fulfill this request" in response.get("content", ""):
                return GuardrailsResult(
                    safe=False, 
                    reason="Blocked by input guardrails", 
                    latency_ms=latency_ms
                )
                
            return GuardrailsResult(safe=True, latency_ms=latency_ms)

        except Exception as e:
            logger.exception("Input guardrails failed")
            latency_ms = (time.time() - start_time) * 1000
            if self.fail_open:
                logger.warning(f"Guardrails failed, failing open. Error: {e}")
                return GuardrailsResult(safe=True, latency_ms=latency_ms)
            else:
                return GuardrailsResult(
                    safe=False, 
                    reason=f"Guardrails system error: {str(e)}", 
                    latency_ms=latency_ms
                )

    async def check_output(self, ai_response: str, context: Optional[dict] = None) -> GuardrailsResult:
        """Run output rails on an AI response."""
        if not self.enabled or not self.output_enabled:
            return GuardrailsResult(safe=True, sanitized=ai_response)

        start_time = time.time()
        try:
            rails = self._get_rails()
            # NeMo needs a conversation with a user message for proper context
            messages = [
                {"role": "user", "content": "[Output safety check]"},
                {"role": "assistant", "content": ai_response}
            ]
            
            response = await rails.generate_async(messages=messages)
            latency_ms = (time.time() - start_time) * 1000
            
            if "I cannot fulfill this request" in response.get("content", ""):
                return GuardrailsResult(
                    safe=False,
                    reason="Blocked by output guardrails",
                    sanitized="[Content blocked by safety guardrails]",
                    latency_ms=latency_ms
                )

            return GuardrailsResult(
                safe=True, 
                sanitized=ai_response, # NeMo doesn't currently easily stream back partial sanitization natively in this simple pattern, so if it's safe we return original
                latency_ms=latency_ms
            )

        except Exception as e:
            logger.exception("Output guardrails failed")
            latency_ms = (time.time() - start_time) * 1000
            if self.fail_open:
                return GuardrailsResult(safe=True, sanitized=ai_response, latency_ms=latency_ms)
            else:
                return GuardrailsResult(
                    safe=False,
                    reason=f"Guardrails system error: {str(e)}",
                    sanitized="[Content blocked due to safety system error]",
                    latency_ms=latency_ms
                )

    def is_enabled(self) -> bool:
        """Check if guardrails are enabled in config."""
        return self.enabled
