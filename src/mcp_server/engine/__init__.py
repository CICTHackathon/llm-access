"""Deterministic reasoning core: pure functions over the source of truth and evidence.

Nothing in this package performs I/O or calls an LLM, so every decision it makes is
reproducible from the inputs recorded in the decision log.
"""
