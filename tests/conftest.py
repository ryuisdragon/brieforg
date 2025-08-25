import os
import pytest

def pytest_addoption(parser):
    parser.addoption("--host", action="store", default=None, help="Base host, e.g. http://127.0.0.1:8000")

@pytest.fixture(scope="session")
def host(request):
    return request.config.getoption("--host") or os.getenv("TEST_HOST") or "http://127.0.0.1:8000"

@pytest.fixture(scope="session")
def url(host):
    return f"{host.rstrip('/')}/chat/turn"

try:
    from fastapi.testclient import TestClient
    from app_refactored_unified import app

    @pytest.fixture(scope="session")
    def client():
        return TestClient(app)
except Exception:
    import httpx

    @pytest.fixture(scope="session")
    def httpx_client(host):
        return httpx.Client(base_url=host, timeout=10.0)
