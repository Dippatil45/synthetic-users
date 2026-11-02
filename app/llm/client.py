"""Gemini LLM client with retry logic."""

import time
import httpx
from app.config import settings


class LLMError(Exception):
    """Error raised when LLM API call fails or returns invalid response."""
    pass


def generate_text(prompt: str) -> str:
    """
    Generate text using Gemini API with retry logic.
    
    Args:
        prompt: The prompt text to send to the LLM
        
    Returns:
        Generated text response
        
    Raises:
        LLMError: On final failure or bad response
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent"
    
    headers = {
        "x-goog-api-key": settings.LLM_API_KEY,
        "Content-Type": "application/json",
    }
    
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    retry_delays = [2.0, 4.0, 8.0]
    last_error = None
    
    for attempt in range(4):  # 4 total attempts (initial + 3 retries)
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=body)
                
                # Retry on rate limit or server errors
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < 3:  # Don't sleep after last attempt
                        time.sleep(retry_delays[attempt])
                        continue
                    else:
                        raise LLMError(f"LLM API request failed with status {response.status_code}")
                
                # Other error status codes
                if response.status_code != 200:
                    raise LLMError(f"LLM API request failed with status {response.status_code}")
                
                # Parse response
                try:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise LLMError("LLM response missing candidates")
                    
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts:
                        raise LLMError("LLM response missing content parts")
                    
                    # Join all text parts
                    text_parts = [part.get("text", "") for part in parts]
                    result = "".join(text_parts)
                    
                    if not result:
                        raise LLMError("LLM returned empty response")
                    
                    return result
                    
                except (KeyError, IndexError, ValueError) as e:
                    raise LLMError(f"Failed to parse LLM response: {str(e)}")
        
        except httpx.TimeoutException:
            last_error = LLMError("LLM API request timed out")
            if attempt < 3:
                time.sleep(retry_delays[attempt])
                continue
        except httpx.RequestError as e:
            last_error = LLMError(f"LLM API request failed: {str(e)}")
            if attempt < 3:
                time.sleep(retry_delays[attempt])
                continue
    
    # If we got here, all retries failed
    if last_error:
        raise last_error
    raise LLMError("LLM API request failed after all retries")
