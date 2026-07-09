from probe.credentials import CredentialStore, mask
def test_mask_hides_middle():
    assert mask("sk-abcdefgh1234") == "sk-…1234"
def test_status_never_reveals_plaintext(tmp_path):
    store = CredentialStore(backend="file", store_dir=tmp_path)
    store.set("LLM_API_KEY", "sk-secret-XYZ")
    s = store.status("LLM_API_KEY")
    assert "sk-secret-XYZ" not in s
    assert "XYZ" in s  # 末尾可见
def test_get_returns_plaintext(tmp_path):
    store = CredentialStore(backend="file", store_dir=tmp_path)
    store.set("LLM_API_KEY", "sk-secret-XYZ")
    assert store.get("LLM_API_KEY") == "sk-secret-XYZ"
def test_clear(tmp_path):
    store = CredentialStore(backend="file", store_dir=tmp_path)
    store.set("LLM_API_KEY", "x")
    store.clear("LLM_API_KEY")
    assert store.get("LLM_API_KEY") is None
