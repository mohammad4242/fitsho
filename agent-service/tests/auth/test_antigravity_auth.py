from app.auth.adapters.antigravity import AntigravityAuthAdapter
from app.auth.schemas import AuthSessionStatus


def test_antigravity_is_explicitly_manual_only_after_real_probe() -> None:
    adapter = AntigravityAuthAdapter(executable="agy")

    assert adapter.manual_auth_only is True
    assert adapter.command().executable == "agy"
    assert adapter.command().use_pty is True
    assert adapter.allowed_auth_hosts() == frozenset()
    assert adapter.parse_output("https://evil.example/login").failed is True
    assert adapter.classify_exit(1, "private output") is AuthSessionStatus.FAILED
