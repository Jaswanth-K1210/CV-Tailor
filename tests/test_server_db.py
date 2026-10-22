from server import db


def test_schema_and_cascade_delete(tmp_path):
    conn = db.connect(str(tmp_path / "t.db"))
    uid = conn.execute("INSERT INTO users(email, created_at) VALUES ('a@x.com', 0)").lastrowid
    jid = conn.execute("INSERT INTO jobs(user_id, kind, created_at, updated_at) "
                       "VALUES (?, 'tailor', 0, 0)", (uid,)).lastrowid
    conn.execute("INSERT INTO events(job_id, ts, type) VALUES (?, 0, 'round')", (jid,))
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    assert conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
