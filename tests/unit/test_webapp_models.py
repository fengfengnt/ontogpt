from fastapi.testclient import TestClient

from ontogpt.webapp.main import app


def test_web_homepage_exposes_deepseek_flash():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "deepseek/deepseek-flash" in response.text
