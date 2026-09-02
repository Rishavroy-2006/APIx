import os
import json
import time
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMExtractionError(Exception):
    """Raised when LLM extraction fails or fails to return valid structured JSON."""
    pass


class LLMClient:
    """
    Thin client wrapper supporting structured JSON extraction via Gemini or Anthropic.
    Selection is driven by environment variable `LLM_PROVIDER` ('gemini' or 'anthropic').
    """

    def __init__(self, provider: Optional[str] = None):
        selected_provider = provider or os.getenv("LLM_PROVIDER", "gemini")
        self.provider = selected_provider.lower().strip()
        if self.provider not in ("gemini", "anthropic"):
            raise ValueError(f"Unsupported LLM_PROVIDER '{self.provider}'. Must be 'gemini' or 'anthropic'.")

    def extract_json(
        self,
        system_prompt: str,
        user_content: str,
        schema_hint: dict,
        max_retries: int = 2,
        initial_backoff: float = 1.0,
    ) -> dict:
        """
        Extracts structured JSON payload using provider's native structured output mode.
        Retries up to max_retries times with backoff.
        Raises typed LLMExtractionError on failure.
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                if self.provider == "gemini":
                    result = self._call_gemini(system_prompt, user_content, schema_hint)
                elif self.provider == "anthropic":
                    result = self._call_anthropic(system_prompt, user_content, schema_hint)
                else:
                    raise ValueError(f"Unknown provider: {self.provider}")

                if not isinstance(result, dict):
                    raise LLMExtractionError(f"Expected dict from LLM, got {type(result).__name__}")

                return result

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM extraction attempt {attempt + 1}/{max_retries + 1} failed ({self.provider}): {e}"
                )
                if attempt < max_retries:
                    sleep_time = initial_backoff * (2 ** attempt)
                    time.sleep(sleep_time)

        raise LLMExtractionError(
            f"Extraction failed after {max_retries + 1} attempts using provider '{self.provider}': {last_exception}"
        ) from last_exception

    def _call_gemini(self, system_prompt: str, user_content: str, schema_hint: dict) -> dict:
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise LLMExtractionError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set.")

        # 1. Try google.genai SDK
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=schema_hint if schema_hint else None,
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_content,
                config=config,
            )
            if not response.text:
                raise LLMExtractionError("Empty response text from Gemini SDK")
            return json.loads(response.text)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Gemini SDK call failed, attempting fallback: {e}")

        # 2. Try google.generativeai SDK
        try:
            import google.generativeai as ggi

            ggi.configure(api_key=api_key)
            model = ggi.GenerativeModel(
                model_name="gemini-2.5-flash",
                system_instruction=system_prompt,
            )
            gen_config = {"response_mime_type": "application/json"}
            if schema_hint:
                gen_config["response_schema"] = schema_hint
            resp = model.generate_content(user_content, generation_config=gen_config)
            if not resp.text:
                raise LLMExtractionError("Empty response text from google.generativeai")
            return json.loads(resp.text)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"google.generativeai SDK call failed, attempting fallback: {e}")

        # 3. HTTP REST API Fallback
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        gen_config = {"response_mime_type": "application/json"}
        if schema_hint:
            gen_config["response_schema"] = schema_hint

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_content}]}],
            "generationConfig": gen_config,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
                candidates = body.get("candidates", [])
                if not candidates:
                    raise LLMExtractionError("No candidates returned from Gemini HTTP API")
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise LLMExtractionError("No content parts in Gemini HTTP API response")
                raw_text = parts[0].get("text", "")
                return json.loads(raw_text)
        except urllib.error.HTTPError as he:
            raise LLMExtractionError(f"Gemini HTTP API error ({he.code}): {he.read().decode('utf-8')}") from he
        except Exception as ex:
            raise LLMExtractionError(f"Gemini API request failed: {ex}") from ex

    def _call_anthropic(self, system_prompt: str, user_content: str, schema_hint: dict) -> dict:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMExtractionError("ANTHROPIC_API_KEY environment variable not set.")

        tools = [
            {
                "name": "extract_data",
                "description": "Output extracted structured JSON matching schema",
                "input_schema": schema_hint or {"type": "object", "properties": {}},
            }
        ]

        # 1. Try anthropic SDK
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                tools=tools,
                tool_choice={"type": "tool", "name": "extract_data"},
            )
            for block in msg.content:
                if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "extract_data":
                    return block.input
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "extract_data":
                    return block.get("input", {})
            raise LLMExtractionError("Anthropic tool call block not found in response")
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Anthropic SDK call failed, attempting fallback: {e}")

        # 2. HTTP REST API Fallback
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_content}],
            "tools": tools,
            "tool_choice": {"type": "tool", "name": "extract_data"},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
                content = body.get("content", [])
                for block in content:
                    if block.get("type") == "tool_use" and block.get("name") == "extract_data":
                        return block.get("input", {})
                raise LLMExtractionError("No matching tool_use block in Anthropic HTTP API response")
        except urllib.error.HTTPError as he:
            raise LLMExtractionError(f"Anthropic HTTP API error ({he.code}): {he.read().decode('utf-8')}") from he
        except Exception as ex:
            raise LLMExtractionError(f"Anthropic API request failed: {ex}") from ex
