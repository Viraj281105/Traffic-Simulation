"""AI Copilot module — Groq-backed summary, Q&A and config-patch endpoints.

The Groq API key is read exclusively from the GROQ_API_KEY environment
variable (see groq_client.py). It is never logged, returned in responses or
committed to version control.
"""
