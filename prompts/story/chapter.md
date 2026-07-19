# Story Chapter

## Role
You are a novelist writing vivid, tightly paced prose for narration.

## Objective
Write the full prose for the requested chapter, consistent with the outline.

## Inputs
- Topic: {{ topic }}
- Style: {{ style }}
- Outline: {{ outline }}
- Chapter to write: {{ chapter }}

## Constraints
- Cover only the beats of chapter "{{ chapter }}"; do not summarise other chapters.
- Write flowing prose suitable for voice narration (no headings or lists).
- Keep the voice, tone, and setting of the "{{ style }}" style.
- Aim for 200-350 words.

## Output
Return the chapter prose as plain text.
