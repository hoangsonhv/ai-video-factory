"""AI provider layer (infrastructure).

The single, vendor-neutral way the system talks to LLM providers. The
``base`` package defines the contract (protocol, request/response models,
errors, retry policy); ``gemini`` is the first concrete implementation;
``factory`` selects the active provider from configuration.

Nothing outside infrastructure imports these symbols directly — provider
selection happens via the ``ProviderFactory`` in the ``factory`` package.
"""
