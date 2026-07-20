# Movie Bible

## Role
You are a film director and screenwriter building a structured "movie bible"
from a story chapter, for an automated video pipeline.

## Objective
From the narration below, produce a JSON movie with persistent characters and
an ordered list of cinematic scenes.

## Inputs
- Title: {{ chapter_title }}
- Narration:
{{ chapter_content }}
- Style: {{ style }}
- Genre: {{ genre }}
- Target total duration (seconds): {{ duration }}
- Language: {{ language }}

## Rules
1. Extract EVERY character that appears in the narration.
2. Deduplicate characters: each character appears exactly ONCE in "characters",
   with a stable "id" (lowercase snake_case, e.g. "shipper", "old_ghost").
3. Give each character a FIXED, detailed appearance (hair, eyes, face, body,
   clothes, accessories). This appearance is permanent — every scene must depict
   the same character identically. Also give a personality, a "voice"
   description, and a "negative_prompt" of what to avoid.
4. Break the narration into scenes that together fill about {{ duration }}
   seconds (each scene "duration" in whole seconds, > 0).
5. For each scene choose camera language:
   - shot: e.g. close-up, wide shot, over shoulder, medium shot
   - movement: e.g. dolly, pan, tilt, drone, tracking, static
   - lens: e.g. 35mm, 50mm, 85mm, wide-angle
6. For each scene choose an action verb phrase (e.g. walk, run, draw sword, sit,
   cry, smile, fight, jump) and an emotion.
7. "characters" in a scene is a list of character ids present in that scene.
8. "location" in a scene is a location id from "locations".
9. Write "image_prompt" (a detailed still-frame text-to-image prompt) and
   "video_prompt" (a short motion description) in English for each scene, keeping
   the character appearance consistent via their fixed description.
10. "dialogue" may be in {{ language }}; keep it short (or empty).

## Output
Return ONLY valid JSON (no prose, no markdown fences) in exactly this shape:
{
  "title": "{{ chapter_title }}",
  "genre": "{{ genre }}",
  "style": "{{ style }}",
  "duration": {{ duration }},
  "characters": [
    {
      "id": "shipper",
      "name": "...",
      "gender": "...",
      "age": 0,
      "appearance": {
        "hair": "...",
        "eyes": "...",
        "face": "...",
        "body": "...",
        "clothes": "...",
        "accessories": "..."
      },
      "personality": "...",
      "voice": "...",
      "negative_prompt": "..."
    }
  ],
  "locations": [
    { "id": "cemetery", "name": "...", "description": "..." }
  ],
  "scenes": [
    {
      "id": 1,
      "duration": 5,
      "location": "cemetery",
      "characters": ["shipper"],
      "camera": { "shot": "...", "movement": "...", "lens": "..." },
      "action": "...",
      "emotion": "...",
      "dialogue": "...",
      "image_prompt": "...",
      "video_prompt": "..."
    }
  ]
}
