"""Sign a TestClient in as a real user, through the real /auth endpoints."""
EMAIL = "candidate@example.com"
PASSWORD = "a long enough password"


def sign_in(client, email: str = EMAIL, password: str = PASSWORD) -> str:
    """Register, log in, and send the token on every later request. Returns the user id."""
    registered = client.post("/auth/register", json={"email": email, "password": password})
    assert registered.status_code == 201, registered.text
    login = client.post("/auth/token", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    return registered.json()["id"]