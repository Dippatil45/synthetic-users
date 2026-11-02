"""LLM-based persona name and backstory generation."""

import json
import re
from app.llm.client import generate_text, LLMError


def write_identity(profile: dict) -> dict:
    """
    Generate name and backstory for a persona profile.
    
    Args:
        profile: Dict with keys demographics, professional, behavioral
        
    Returns:
        Dict with keys "name" and "backstory"
        
    Raises:
        LLMError: If LLM returns invalid or incomplete response
    """
    demographics = profile.get("demographics", {})
    professional = profile.get("professional", {})
    behavioral = profile.get("behavioral", {})
    
    # Build prompt
    prompt = f"""Generate a realistic identity for a persona with these attributes:

Demographics:
- Age: {demographics.get('age')}
- Gender: {demographics.get('gender')}
- Location: {demographics.get('location')}
- Education: {demographics.get('education')}
- Income: {demographics.get('income_band')}
- Marital status: {demographics.get('marital_status')}

Professional:
- Occupation: {professional.get('occupation')}
- Industry: {professional.get('industry')}
- Experience: {professional.get('experience_years')} years

Behavioral:
- Tech savviness: {behavioral.get('tech_savviness')}/10
- Shopping habits: {behavioral.get('shopping_habits')}
- Brand loyalty: {behavioral.get('brand_loyalty')}
- Preferred devices: {', '.join(behavioral.get('preferred_devices', []))}
- Spending style: {behavioral.get('spending_style')}

Requirements:
1. The name must fit the person's location and gender (use culturally appropriate names)
2. The backstory must be 80-120 words in third person
3. Cover their daily life, goals, frustrations, and how they use technology and shop
4. Must not contradict any given attribute (age, job, education, income, devices)
5. Do not mention real people or specific brand names
6. Write naturally and realistically

Return ONLY a JSON object with this exact structure:
{{"name": "First Last", "backstory": "..."}}"""

    # Call LLM
    response = generate_text(prompt)
    
    # Parse response robustly
    # Strip markdown code fences if present
    cleaned = response.strip()
    
    # Remove markdown code fences
    if cleaned.startswith("```"):
        # Extract content between code fences
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1).strip()
        else:
            # Try removing just the opening/closing markers
            cleaned = re.sub(r"```(?:json)?", "", cleaned).strip()
    
    # Try to extract JSON object if there's extra text
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)
    
    # Parse JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise LLMError(f"Failed to parse LLM response as JSON: {str(e)}")
    
    # Validate required fields
    if not isinstance(data, dict):
        raise LLMError("LLM response is not a JSON object")
    
    if "name" not in data or not data["name"]:
        raise LLMError("LLM response missing 'name' field")
    
    if "backstory" not in data or not data["backstory"]:
        raise LLMError("LLM response missing 'backstory' field")
    
    return {
        "name": data["name"],
        "backstory": data["backstory"]
    }
