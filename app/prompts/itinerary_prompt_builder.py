from app.schemas.ai import ItineraryGenerateRequest


def build_itinerary_generate_prompt(request: ItineraryGenerateRequest) -> str:
    return f"""
You are generating an itinerary draft for Trip-Collab.

Trip details:
- trip_title: {request.trip_title}
- destination: {request.destination}
- start_date: {request.start_date.isoformat()}
- end_date: {request.end_date.isoformat()}
- timezone: {request.timezone}
- travelers_count: {request.travelers_count}
- travel_style: {request.travel_style or "null"}
- budget_level: {request.budget_level or "null"}
- interests: {request.interests}
- must_visit_places: {request.must_visit_places}
- avoid_places: {request.avoid_places}
- notes: {request.notes or "null"}
- language: {request.language}

Return JSON only.
Do not include markdown.

Return exactly this JSON shape:
{{
  "items": [
    {{
      "day_date": "YYYY-MM-DD",
      "title": "...",
      "start_time": "HH:MM:SS or null",
      "end_time": "HH:MM:SS or null",
      "location_name": "... or null",
      "map_url": null,
      "note": "... or null",
      "sort_order": 1
    }}
  ],
  "explanation": "...",
  "warnings": []
}}

Rules:
- Only generate items between start_date and end_date.
- Use HH:MM:SS for time fields.
- Use null if time or location data is unknown.
- sort_order starts from 1 for each day.
- The response language should match request.language.
- Do not invent map_url. Use null unless certain.
""".strip()
