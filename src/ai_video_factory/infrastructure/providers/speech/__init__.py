"""AI speech (TTS) provider layer (infrastructure).

The vendor-neutral way the system synthesizes narration audio. ``base`` defines
the contract; ``gemini`` implements it with Google Gemini TTS; ``factory``
selects the active provider from configuration. Reuses the shared provider
error hierarchy, retry policy and health types.
"""
