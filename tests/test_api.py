import os
from importlib import reload

from fastapi.testclient import TestClient


def build_client(db_file: str):
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    import app.main as main  # noqa: WPS433

    reload(main)
    return TestClient(main.app)


def test_health_endpoint(tmp_path):
    client = build_client(str(tmp_path / "health.db"))
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_auth_question_exam_flow(tmp_path):
    client = build_client(str(tmp_path / "flow.db"))

    # register + login as admin
    reg = client.post("/auth/register", json={"username": "admin", "password": "secret123", "role": "admin"})
    assert reg.status_code == 200

    login = client.post("/auth/token", data={"username": "admin", "password": "secret123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # create question
    q = client.post(
        "/questions",
        headers=headers,
        json={
            "type": "single_choice",
            "title": "1+1=?",
            "options": ["1", "2", "3", "4"],
            "answer": "2",
            "subject": "数学",
            "tags": ["基础"],
        },
    )
    assert q.status_code == 200
    qid = q.json()["id"]

    # review -> approved
    rv = client.patch(f"/questions/{qid}/review", headers=headers, params={"review_status": "approved"})
    assert rv.status_code == 200

    # start exam and answer
    st = client.post("/exams/start", headers=headers, json={"subject": "数学", "limit": 5})
    assert st.status_code == 200
    exam_id = st.json()["exam_id"]
    questions = st.json()["questions"]
    assert len(questions) >= 1

    ans = client.post(f"/exams/{exam_id}/answer", headers=headers, json={"question_id": qid, "user_answer": "2"})
    assert ans.status_code == 200
    assert ans.json()["is_correct"] is True

    cp = client.post(f"/exams/{exam_id}/complete", headers=headers)
    assert cp.status_code == 200
    assert cp.json()["correct_count"] >= 1
