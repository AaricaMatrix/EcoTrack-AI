import httpx
import json
import os
from app.models.schemas import InsightRequest, InsightResponse, ChatRequest, ChatResponse, CategoryBreakdown

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
_GLOBAL_AVG_KG = 4000.0
_INDIA_AVG_KG = 1800.0

def _get_api_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise ValueError("GEMINI_API_KEY not set")
    return key

def _call_gemini(prompt: str, max_tokens: int = 800) -> str:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7}
    }
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            f"{_GEMINI_URL}?key={_get_api_key()}",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        res.raise_for_status()
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()

def _build_insight_prompt(req: InsightRequest) -> str:
    fp = req.footprint
    dominant = max(
        [("transport", fp.transport), ("home energy", fp.home_energy),
         ("diet", fp.diet), ("shopping", fp.shopping)],
        key=lambda x: x[1]
    )[0]
    name_part = f"for {req.user_name}" if req.user_name else "for this user"
    return f"""You are an expert climate scientist and personal carbon coach.
Analyse this carbon footprint and return ONLY a JSON object — no markdown, no extra text.

USER DATA:
- Transport: {fp.transport:.0f} kg CO2e/year
- Home Energy: {fp.home_energy:.0f} kg CO2e/year
- Diet: {fp.diet:.0f} kg CO2e/year
- Shopping: {fp.shopping:.0f} kg CO2e/year
- TOTAL: {fp.total:.0f} kg CO2e/year
- Global average: {_GLOBAL_AVG_KG:.0f} kg/year
- India average: {_INDIA_AVG_KG:.0f} kg/year
- IPCC 1.5C target: 2300 kg/year

Return EXACTLY this JSON:
{{
  "summary": "2-3 sentence overview {name_part} referencing their actual numbers vs benchmarks",
  "dominant_category": "{dominant}",
  "key_insight": "One non-obvious insight specific to this person's exact numbers",
  "action_plan": [
    "Step 1: concrete action with estimated CO2 saving",
    "Step 2: concrete action with estimated CO2 saving",
    "Step 3: concrete action with estimated CO2 saving"
  ],
  "motivational_close": "One encouraging sentence personalised {name_part}"
}}"""

async def generate_insights(req: InsightRequest) -> InsightResponse:
    fp = req.footprint
    dominant = max(
        [("transport", fp.transport), ("home energy", fp.home_energy),
         ("diet", fp.diet), ("shopping", fp.shopping)],
        key=lambda x: x[1]
    )[0]
    try:
        prompt = _build_insight_prompt(req)
        raw = _call_gemini(prompt)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        return InsightResponse(
            summary=parsed["summary"],
            dominant_category=parsed["dominant_category"],
            key_insight=parsed["key_insight"],
            action_plan=parsed["action_plan"],
            motivational_close=parsed["motivational_close"],
        )
    except Exception as e:
        return InsightResponse(
            summary=f"Your annual footprint of {fp.total:.0f} kg CO2e is {'above' if fp.total > _GLOBAL_AVG_KG else 'below'} the global average of {_GLOBAL_AVG_KG:.0f} kg. Your biggest driver is {dominant}.",
            dominant_category=dominant,
            key_insight=f"Reducing your {dominant} emissions by 30% would save {fp.total * 0.3:.0f} kg CO2e annually.",
            action_plan=[
                f"1. Focus on {dominant} — it drives the most impact.",
                "2. Track monthly changes to measure real progress.",
                "3. Start with the easiest win and build momentum.",
            ],
            motivational_close="Every kilogram reduced matters — small consistent changes compound over time.",
        )

async def chat_with_ecobot(req: ChatRequest) -> ChatResponse:
    fp = req.footprint_context
    context = ""
    if fp:
        context = f"\nUser footprint: Transport {fp.transport:.0f}, Home {fp.home_energy:.0f}, Diet {fp.diet:.0f}, Shopping {fp.shopping:.0f}, Total {fp.total:.0f} kg CO2e/year (India avg: 1800, Global avg: 4000)"

    system = f"""You are EcoBot, an expert carbon footprint coach. 
Keep responses under 150 words, warm and actionable.
Never make up statistics.{context}"""

    last_msg = req.messages[-1].content
    full_prompt = f"{system}\n\nUser: {last_msg}\nEcoBot:"

    try:
        reply = _call_gemini(full_prompt, max_tokens=300)
        return ChatResponse(reply=reply)
    except Exception:
        return ChatResponse(reply="I'm having trouble connecting right now. Please try again in a moment.")
