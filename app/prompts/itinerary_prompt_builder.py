from app.schemas.ai import ItineraryGenerateRequest


def _format_existing_itinerary(request: ItineraryGenerateRequest) -> str:
    if not request.existing_itinerary:
        return "Existing itinerary: []"

    lines = [
        "Existing itinerary:",
        f"- avoid_duplicate_places: {request.avoid_duplicate_places}",
    ]
    for item in request.existing_itinerary:
        lines.append(
            "- "
            f"day_date: {item.day_date.isoformat()}; "
            f"title: {item.title}; "
            f"location_name: {item.location_name or 'null'}; "
            f"note: {item.note or 'null'}"
        )
    return "\n".join(lines)


def build_itinerary_generate_prompt(request: ItineraryGenerateRequest) -> str:
    existing_itinerary_section = _format_existing_itinerary(request)
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

{existing_itinerary_section}

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
- Do not force impossible places into the itinerary.
- If must_visit_places or notes include unreasonable places or geographically incompatible places for the destination or trip area, do not include them in items.
- Put geographically incompatible or infeasible requests in warnings, and briefly explain the reason in explanation.
- Do not generate unrealistic transportation. For example, do not describe international or very long-distance travel as walking, taxi, or local bus.
- If a place would require a flight or long-distance rail and does not fit the day, explain that it is not suitable for the day's itinerary instead of adding it.
- If you are uncertain whether a place or route is feasible, be conservative: do not pretend certainty, add a warning, and avoid confident but potentially wrong transportation or timing.
- Avoid recommending places or activities already listed in existing_itinerary when avoid_duplicate_places is true.
- If a must_visit_place already exists in existing_itinerary, do not duplicate it. Mention it in warnings.
- If a recommended place is similar to an existing item, avoid it unless the user explicitly requests it again.
- The selected date may already have items; generate complementary items instead of duplicates.
- If avoiding duplicates makes the itinerary sparse, explain this in warnings.
- If avoid_duplicate_places is false, duplicates are allowed when useful, but still mention likely duplication in warnings.
- Write user-friendly warnings and explanation in natural language for travelers.
- Do not mention internal field names in warnings or explanation, including avoid_duplicate_places, existing_itinerary, must_visit_places, fallback_reason, JSON field, or flag.
- If a place is skipped to avoid duplication, say naturally that it is already arranged on another date, that you avoided adding it again this time, and that the user can manually add it or regenerate with adjusted needs.
- Do not write technical explanations such as "because avoid_duplicate_places is true".
""".strip()
