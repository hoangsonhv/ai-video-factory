"""AI image provider layer (infrastructure).

The vendor-neutral way the system generates images. ``base`` defines the
contract (protocol + request/response models); ``gemini`` implements it with
Google Imagen; ``factory`` selects the active provider from configuration.
Reuses the shared provider error hierarchy, retry policy and health types.
"""
