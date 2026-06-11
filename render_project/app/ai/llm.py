"""
LLM service — Gemini primary, Groq fallback.
All calls are async.
"""
from __future__ import annotations

import time
from typing import List, Dict, Any, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.core.exceptions import LLMError


# ── Budget guide ─────────────────────────────────────────────────────────────
def budget_guide(budget: str, people: int) -> str:
    guides = {
        "Budget":  f"Stay ₹800-1000/night | Food ₹100-200/meal/person | ~₹{(1000 + 200*3)*people:,}/day for {people}p",
        "Medium":  f"Stay ₹1100-3500/night | Food ₹400-800/meal/person | ~₹{(2000 + 600*3)*people:,}/day for {people}p",
        "Luxury":  f"Stay ₹5000+/night | Food ₹1000+/meal/person | ~₹{(6000 + 1200*3)*people:,}/day for {people}p",
    }
    return guides.get(budget, guides["Medium"])


# ── Prompt builder ─────────────────────────────────────────────────────────────
def build_prompt(state: Dict[str, Any]) -> str:
    place_text  = state.get("place_text", "")
    weather     = state.get("weather", [])
    source      = state.get("start", "")
    destination = state.get("destination", "")
    days        = state.get("days", 1)
    mode        = state.get("mode", "Road")
    people      = state.get("people", 2)
    budget      = state.get("budget", "Medium")
    interests   = state.get("interests", [])
    is_flight   = mode.lower() == "flight"

    realistic_days = days
    route_string   = f"{source} → {destination}"
    dist_label     = ""
    district_route_str = ""
    src_district_label = source
    external_src = ""
    total_km = 0.0
    odisha_km = 0.0
    flight_info = ""
    airport_to_dest = ""

    for line in place_text.split("\n"):
        if line.startswith("REALISTIC_DAYS_POSSIBLE:"):
            try: realistic_days = int(line.split(":")[1].strip())
            except Exception: pass
        elif line.startswith("ROUTE_STRING:"):
            route_string = line.split(":", 1)[1].strip()
        elif line.startswith("DIST_LABEL:"):
            dist_label = line.split(":", 1)[1].strip()
        elif line.startswith("DISTRICT_ROUTE:"):
            district_route_str = line.split(":", 1)[1].strip()
        elif line.startswith("EXTERNAL_SOURCE:"):
            external_src = line.split(":", 1)[1].strip()
        elif line.startswith("TOTAL_ROUTE_KM:"):
            try: total_km = float(line.split(":")[1].strip())
            except Exception: pass
        elif line.startswith("ODISHA_ROAD_KM:"):
            try: odisha_km = float(line.split(":")[1].strip())
            except Exception: pass
        elif line.startswith("FLIGHT_INFO:"):
            flight_info = line.split(":", 1)[1].strip()
        elif line.startswith("AIRPORT_TO_DEST_ROAD:"):
            airport_to_dest = line.split(":", 1)[1].strip()

    if "source=" in dist_label:
        try: src_district_label = dist_label.split("source=")[1].split("|")[0].strip()
        except Exception: pass

    day_advisory = (
        f"User selected {days} day(s) but needs ≥{realistic_days} days.\n"
        f"Start output with: 'Smart Planner Note: We recommend {realistic_days} days for {source}→{destination}. "
        f"Here is your optimised {days}-day plan:'\n"
        f"Then generate EXACTLY {days} day(s)."
        if days < realistic_days else
        f"Generate EXACTLY {days} day(s). No more, no less."
    )

    has_nature_camps = "NATURE_CAMPS:" in place_text
    nature_camp_note = (
        f"\n\nNATURE CAMP NOTE: User selected Nature Camps. "
        f"After the main itinerary, write a special NATURE CAMP section. "
        f"Each nature camp requires 1 full day minimum (overnight stay). "
        f"Format each camp as: NATURE CAMP DAY — [Camp Name]. "
        f"Inform the user: staying at a nature camp needs advance booking."
        if has_nature_camps else ""
    )

    if weather:
        weather_text = "\n".join([
            f"Day {i+1} ({w['date']}): {w['condition']}, {w['temp_c']}°C "
            f"(feels {w.get('feels_c', w['temp_c'])}°C), "
            f"Humidity {w.get('humidity','?')}%, Wind {w.get('wind_kmh','?')} km/h"
            for i, w in enumerate(weather)
        ])
    else:
        weather_text = "Weather data unavailable."

    bg = budget_guide(budget, people)

    # ── Day 1 rule depends on mode and external source ────────────────────────
    if is_flight and external_src and flight_info:
        # Parse airport details from FLIGHT_INFO
        # Format: "{source} → {iata} | Airport: {name} | City: {city} | Air distance: {km} km"
        parts = {p.strip().split(":")[0].strip(): ":".join(p.strip().split(":")[1:]).strip()
                 for p in flight_info.split("|") if ":" in p}
        airport_name = parts.get("Airport", "Biju Patnaik International Airport")
        airport_city = parts.get("City", src_district_label)
        air_km_str = parts.get("Air distance", "?")
        iata = ""
        if "→" in flight_info:
            seg = flight_info.split("→")[1].strip()
            iata = seg.split("|")[0].strip() if "|" in seg else seg

        day1_rule = (
            f"DAY 1 = FLIGHT DAY from {external_src}.\n"
            f"  - Nearest Odisha airport to {external_src}: {airport_name} [{iata}], {airport_city} ({air_km_str} by air)\n"
            f"  - From airport, drive to first places in {src_district_label} district ({airport_to_dest} road from airport to destination)\n"
            f"  - Start with: 'Fly {external_src} → {iata} ({airport_city}). Then drive by road to explore {src_district_label}.'\n"
            f"  - Use only [DAY1] tagged places. Do NOT mention road distance from {external_src} — show flight info + road from airport."
        )
        # Distance display for header
        day_header_dist = (
            f"Flight: {external_src} ✈ {iata} ({air_km_str}) | "
            f"Road from airport: {airport_to_dest} | "
            f"Odisha road: {odisha_km} km"
        )
        summary_dist = (
            f"Flight: {external_src} ✈ {iata} ~{air_km_str} | "
            f"Road within Odisha: {odisha_km} km | "
            f"Total combined: {total_km} km"
        )
    elif external_src:
        day1_rule = (
            f"DAY 1 = journey day from {external_src}. "
            f"Note: '{external_src}' is outside Odisha — Day 1 covers the travel + arrival at {src_district_label} district. "
            f"Use only [DAY1] tagged places from {src_district_label}. "
            f"Start with a brief note: 'Depart {external_src} by {mode}, enter Odisha via {src_district_label}.'"
        )
        day_header_dist = f"Road within Odisha: {odisha_km} km (+ ~{round(total_km - odisha_km, 0):.0f} km from {external_src} to Odisha border)"
        summary_dist = f"Road within Odisha: {odisha_km} km | {external_src} to Odisha entry: ~{round(total_km - odisha_km, 0):.0f} km | Total: {total_km} km"
    else:
        day1_rule = f"DAY 1 = use only [DAY1] tagged places ({src_district_label} district)."
        day_header_dist = f"Total road distance: {total_km} km"
        summary_dist = f"{total_km} km"

    # Day 1 header format
    if is_flight and external_src:
        d1_header = f"Flight + Road info: [see above]"
    elif days == 1:
        d1_header = "Total time: X hrs"
    else:
        d1_header = "Total road distance: X km | Drive time: X hrs"

    return f"""You are a vivid, expert Indian travel guide writing a day-wise trip itinerary.
Use ONLY the places from PLACE DATA below. Do NOT invent any place.
Write place names in BOLD like **Place Name**. No asterisks (*) anywhere else.
Use - (dash) for bullets. NEVER use asterisks for bullets.

TRIP: {source} → {destination} | {days} days | {mode} | {people} people | {budget}
Interests: {", ".join(interests) if interests else "All"}
{f"NOTE: {source} is outside Odisha. Route: {route_string}" if external_src else ""}
{f"FLIGHT NOTE: Nearest Odisha airport to {external_src}: {flight_info}" if (is_flight and flight_info) else ""}
{f"ROAD FROM AIRPORT TO DESTINATION: {airport_to_dest}" if airport_to_dest else ""}

WEATHER:
{weather_text}

PLACE DATA:
{place_text}

DAY COUNT RULE: {day_advisory}

STRICT RULES — follow exactly, no exceptions:
1. Each day uses ONLY its tagged [DAY1],[DAY2]... places from PLACE DATA. NEVER invent places.
2. EXACTLY 3 PLACES PER DAY. Morning=1, Afternoon=1, Evening=1.
3. [SUGGESTED] places = write normally with "(Suggested)" note after name.
4. Never repeat any place across ALL days — each place appears exactly once.
5. DAY TITLE must be exactly the label from PLACE DATA section header.
6. NEAREST FIRST within each day: morning=nearest, afternoon=middle, evening=farthest.
7. CATEGORY MIX: if 2+ interests selected, put different categories per time slot.
8. DISTANCE: copy "(X km, Y drive from Z)" from PLACE DATA after place name on same line.
9. Each day header must show distance/time info as given in format below.
10. For EVERY place write all 6 lines:
    ✨ Speciality: [rewrite the Speciality field as 1 vivid sentence — max 15 words]
    🗓️ Best time: [copy Best month field exactly]
    🎯 Activities: MAX 3 → act1 (₹X) | act2 (₹X) | act3 (₹X)
    🍜 Must-Try: [pick 2 specific local dishes/foods — keep it short, e.g. "Puri Sabzi, Chhena Poda"]
    💰 Entry: [all tiers]
    🗺️ Map: [URL]
    PLACE_IMAGES:url1,url2,url3
11. TRIP SUMMARY route = use DISTRICT_ROUTE from PLACE DATA exactly.
12. Write ALL {days} days completely before TRIP SUMMARY. Never stop early.
13. Multiply ALL costs × {people} people.
14. TOTAL DISTANCE IN SUMMARY: use exactly: {summary_dist}
    - Do NOT show only Odisha road km as total if source is outside Odisha.
    - Do NOT accumulate per-day distances — use the pre-computed total above.
{nature_camp_note}

BUDGET: {bg}

OUTPUT FORMAT — follow EXACTLY:

DAY 1 - [Use label from PLACE DATA section header for this day]
Route: {route_string}
{day_header_dist}

  🌅 Morning:
    [TIME] - **[Place Name]** ([X] km, [Y] hrs drive from airport/source)
      ✨ Speciality: ...
      🗓️ Best time: ...
      🎯 Activities: [🎯act (₹X)] | [🎯act (₹X)] | [🎯act (₹X)]
      🍜 Must-Try food: [dish1], [dish2]
      💰 Entry: ...
      🗺️ Map: [URL]
      PLACE_IMAGES:url1,url2,url3

  🌤️ Afternoon:
    [TIME] - **[Place Name]** ([X] km, [Y] min drive)
      ...same 6-line structure...
    🍽️ Lunch: [dish] at [place] (~₹X for {people})

  🌆 Evening:
    [TIME] - **[Place Name]** ([X] km, [Y] min drive)
      ...
    🏨 Check in: [hotel] (~₹X/night)
    🍜 Dinner: [dish] (~₹X for {people})

  💰 Day 1 Cost ({people} people): Travel ₹X | Food ₹X | Entry ₹X | Stay ₹X | TOTAL ₹X
  ☁️ Weather: [condition] [temp]°C — [advice]
  💡 Tip: [specific tip for this exact route]

---
(same format for ALL remaining days — do not skip any day)
---

🏁 TRIP SUMMARY
Route: {district_route_str}
Total distance: {summary_dist}
Total cost for {people} people: ₹X

SMART TRAVEL TIPS
- [tip 1: best departure time from {source} and entry into Odisha]
- [tip 2: 1 must-eat dish unique to {destination} with where to find it]
- [tip 3: 1 money-saving or hidden-gem tip specific to this route]
"""


# ── LLM callers ───────────────────────────────────────────────────────────────

async def call_gemini(prompt: str) -> Optional[str]:
    """Call Gemini generateContent API asynchronously (PRIMARY)."""
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning("[Gemini] No API key configured.")
        return None

    url = f"https://generativelanguage.googleapis.com/v1beta/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.error(f"[Gemini] Error: {e}")
        return None


async def call_groq(prompt: str) -> Optional[str]:
    """Call Groq chat completions API asynchronously (FALLBACK)."""
    api_key = settings.GROQ_API_KEY
    if not api_key:
        logger.warning("[Groq] No API key configured.")
        return None

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": settings.LLM_MAX_TOKENS,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"[Groq] Error: {e}")
        return None


async def generate_itinerary(state: Dict[str, Any]) -> str:
    """
    Generate itinerary using Gemini (primary) → Groq (fallback).
    Raises LLMError if both fail.
    """
    prompt = build_prompt(state)
    t0 = time.monotonic()

    # Try Gemini first
    result = await call_gemini(prompt)
    if result and result.strip():
        elapsed = round(time.monotonic() - t0, 2)
        logger.info(f"[LLM] Gemini succeeded in {elapsed}s")
        return result

    # Fallback to Groq
    logger.warning("[LLM] Gemini failed — trying Groq fallback...")
    result = await call_groq(prompt)
    if result and result.strip():
        elapsed = round(time.monotonic() - t0, 2)
        logger.info(f"[LLM] Groq succeeded in {elapsed}s")
        return result

    raise LLMError("Both Gemini and Groq returned empty responses.")
