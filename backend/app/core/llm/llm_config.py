import os

class LLMConfig:
    PROVIDER = os.getenv("PLATFORM_LLM_PROVIDER", "hybrid")
    # Central configuration for model name, default to gemini-3.6-flash or qwen2.5-coder:7b
    MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    OLLAMA_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:7b")
    OLLAMA_ENDPOINT = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # Low temperature optimal for code and JSON structured outputs (qwen2.5-coder:7b)
    TEMPERATURE = 0.1
    TOP_P = 0.95
    NUM_CTX = 8192

