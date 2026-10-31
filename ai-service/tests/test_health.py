"""Trivial tests that need no model or backend — enough for CI to do real work."""

from app.main import _format_tasks_for_prompt, app


def test_health():
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["service"] == "ai-service"


def test_summarise_requires_project_id():
    client = app.test_client()
    resp = client.post("/summarise", json={})
    assert resp.status_code == 400


def test_format_tasks_empty():
    assert _format_tasks_for_prompt([]) == "(no tasks)"


def test_format_tasks_lines():
    out = _format_tasks_for_prompt([{"id": 1, "status": "todo", "priority": "high", "title": "X"}])
    assert "#1" in out and "todo/high" in out and "X" in out
