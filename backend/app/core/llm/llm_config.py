import os

class LLMConfig:
    PROVIDER = "gemini"
    # Central configuration for model name, default to gemini-2.5-flash
    MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    TEMPERATURE = 0.2
