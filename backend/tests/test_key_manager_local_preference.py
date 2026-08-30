from app.core.llm.key_manager import UnifiedKeyManager, AIKey


def test_select_key_prefers_local_ollama_before_cloud_api_keys():
    mgr = UnifiedKeyManager()
    mgr.keys = [
        AIKey(key_id="Cloud Key 1", value="cloud-key-1", api_name="gemini", model_name="gemini-3.6-flash", priority=1),
        AIKey(key_id="Local Ollama", value="http://localhost:11434", api_name="ollama", model_name="qwen2.5-coder:7b", priority=999),
    ]

    selected = mgr.select_key()

    assert selected is not None
    assert selected.api_name == "ollama"
    assert selected.key_id == "Local Ollama"
