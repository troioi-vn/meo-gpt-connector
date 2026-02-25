def test_privacy_policy_page_renders(client):
    resp = client.get("/privacy")

    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Privacy Policy" in resp.text
    assert "Meo GPT Connector" in resp.text
