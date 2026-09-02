from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.main import create_app
from app.proxy import ProxyRuntime, ProxySource
from app.config import Settings

TOKEN = "a" * 32


def test_proxy_runtime_preserves_deployment_default_and_can_switch_modes() -> None:
    runtime = ProxyRuntime(
        {
            "PATH": "/usr/bin",
            "HTTP_PROXY": "http://default-proxy:1080",
            "HTTPS_PROXY": "http://default-proxy:1080",
            "NO_PROXY": "agent-service,db",
            "ALL_PROXY": "http://default-proxy:1080",
        }
    )

    assert runtime.status().enabled is True
    assert runtime.status().source is ProxySource.DEPLOYMENT_DEFAULT
    assert runtime.status().configured is True
    assert runtime.status().masked_proxy_url == "http://default-proxy:1080"

    disabled = runtime.update(enabled=False, source=ProxySource.DEPLOYMENT_DEFAULT)
    disabled_environment = runtime.apply(
        {
            "PATH": "/usr/bin",
            "HTTP_PROXY": "stale",
            "HTTPS_PROXY": "stale",
            "ALL_PROXY": "stale",
            "NO_PROXY": "agent-service,db",
        }
    )
    assert disabled.enabled is False
    assert all(key not in disabled_environment for key in {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    })
    assert disabled_environment["NO_PROXY"] == "agent-service,db"

    custom = runtime.update(
        enabled=True,
        source=ProxySource.CUSTOM,
        proxy_url="http://admin:secret@custom-proxy:8080",
    )
    custom_environment = runtime.apply({"PATH": "/usr/bin", "NO_PROXY": "agent-service"})
    assert custom.enabled is True
    assert custom.source is ProxySource.CUSTOM
    assert custom.masked_proxy_url == "http://****:****@custom-proxy:8080"
    assert custom_environment["HTTP_PROXY"] == "http://admin:secret@custom-proxy:8080"
    assert custom_environment["HTTPS_PROXY"] == "http://admin:secret@custom-proxy:8080"
    assert "secret" not in custom.masked_proxy_url
    assert "ALL_PROXY" not in custom_environment


def test_proxy_runtime_api_requires_internal_auth_and_never_returns_proxy_secret(
    tmp_path: Path,
) -> None:
    settings = Settings(
        agent_service_token=SecretStr(TOKEN),
        agent_workspace_root=tmp_path,
    )
    client = TestClient(create_app(settings))

    assert client.get("/v1/runtime/proxy").status_code == 401

    headers = {"Authorization": f"Bearer {TOKEN}"}
    response = client.put(
        "/v1/runtime/proxy",
        headers=headers,
        json={
            "enabled": True,
            "source": "custom",
            "proxy_url": "http://admin:secret@custom-proxy:8080",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "enabled": True,
        "source": "custom",
        "configured": True,
        "default_configured": False,
        "masked_proxy_url": "http://****:****@custom-proxy:8080",
    }
    assert "admin:secret" not in response.text

    status = client.get("/v1/runtime/proxy", headers=headers)
    assert status.status_code == 200
    assert status.json() == response.json()


def test_proxy_runtime_api_updates_auth_subprocess_environment(tmp_path: Path) -> None:
    settings = Settings(
        agent_service_token=SecretStr(TOKEN),
        agent_workspace_root=tmp_path,
    )
    app = create_app(settings)
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {TOKEN}"}

    response = client.put(
        "/v1/runtime/proxy",
        headers=headers,
        json={"enabled": False, "source": "deployment_default"},
    )

    assert response.status_code == 200, response.text
    environment = app.state.auth_manager.environment
    assert "HTTP_PROXY" not in environment
    assert "HTTPS_PROXY" not in environment
