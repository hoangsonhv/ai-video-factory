# Story Chapter

## Role
You are a novelist writing a tight voice-over narration for a short video.

## Objective
Write ONE concise narration script that tells this story from its opening hook
through to its ending — a short-video voice-over, not a full novel.

## Inputs
- Title: {{ title }}
- Genre: {{ genre }}
- World setting: {{ world_setting }}
- Cultivation system: {{ cultivation_system }}
- Main character: {{ main_character }}
- Supporting characters: {{ supporting_characters }}
- Antagonist: {{ antagonist }}
- Story arc: {{ story_arc }}
- Ending: {{ ending }}
- Chapter outline:
{{ chapter_outlines }}
- Language: {{ language }}

## Constraints
- Write in {{ language }}.
- Keep the whole narration to roughly 180-300 words.
- Flowing prose for voice-over — no headings, lists, markdown, or scene labels.
- Hit the key beats and land the ending; summarise the arc, do not narrate every
  chapter in full.
- Keep the world, cultivation system, and characters consistent.

## Output
Return ONLY valid JSON (no prose outside JSON, no markdown fences):
{ "title": "...", "content": "..." }
