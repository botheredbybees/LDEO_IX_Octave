from fastapi.testclient import TestClient

from webapp import main


def test_help_route_renders_user_guide_as_html():
    client = TestClient(main.app)

    response = client.get("/help")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<h1" in response.text
    assert "Cruise/Cast Intake" in response.text
    assert "Quick-convert" in response.text


def test_help_route_gives_headings_anchor_ids_for_deep_linking():
    client = TestClient(main.app)

    response = client.get("/help")

    assert 'id="quick-convert-unvalidated"' in response.text
