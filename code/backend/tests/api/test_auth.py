"""
Tests for /api/auth routes.
Covers registration, login, token validation, role-based access, and refresh.
"""

from datetime import timedelta

import pytest
from api.routes.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from config.settings import settings
from jose import jwt

pytestmark = pytest.mark.api


# ─── Password helpers ────────────────────────────────────────────────────────


class TestPasswordHelpers:

    def test_hash_and_verify_correct_password(self):
        hashed = hash_password("SuperSecret99!")
        assert verify_password("SuperSecret99!", hashed) is True

    def test_verify_wrong_password_returns_false(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_two_hashes_of_same_password_differ(self):
        """Bcrypt includes a random salt — hashes must be unique."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("plaintext")
        assert "plaintext" not in hashed


# ─── Token creation ──────────────────────────────────────────────────────────


class TestTokenCreation:

    def test_access_token_contains_sub_and_type(self):
        token = create_access_token({"sub": "alice"})
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        assert payload["sub"] == "alice"
        assert payload["type"] == "access"

    def test_refresh_token_type_is_refresh(self):
        token = create_refresh_token({"sub": "alice"})
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        assert payload["type"] == "refresh"

    def test_access_token_expires_in_configured_minutes(self):
        token = create_access_token({"sub": "alice"})
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        issued = payload["exp"] - payload.get(
            "iat", payload["exp"] - settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        # Generous range: exp should be ≈ 60 min from now
        import time

        delta = payload["exp"] - time.time()
        assert 0 < delta <= settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 5

    def test_custom_expiry_is_honoured(self):
        token = create_access_token(
            {"sub": "alice"}, expires_delta=timedelta(seconds=10)
        )
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        import time

        delta = payload["exp"] - time.time()
        assert 0 < delta <= 15  # 10 s + small tolerance


# ─── Registration endpoint ────────────────────────────────────────────────────


class TestRegisterEndpoint:

    def test_register_new_user_returns_201(self, client):
        res = client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "new@qf.local",
                "password": "pass1234",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["username"] == "newuser"
        assert data["role"] == "operator"
        assert "hashed_password" not in data

    def test_register_duplicate_username_returns_400(self, client, make_user):
        make_user(username="existing", email="ex@qf.local")
        res = client.post(
            "/api/auth/register",
            json={
                "username": "existing",
                "email": "other@qf.local",
                "password": "pass1234",
            },
        )
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_register_duplicate_email_returns_400(self, client, make_user):
        make_user(username="orig", email="shared@qf.local")
        res = client.post(
            "/api/auth/register",
            json={
                "username": "newname",
                "email": "shared@qf.local",
                "password": "pass1234",
            },
        )
        assert res.status_code == 400

    def test_register_admin_role(self, client):
        res = client.post(
            "/api/auth/register",
            json={
                "username": "superadmin",
                "email": "sa@qf.local",
                "password": "pass1234",
                "role": "admin",
            },
        )
        assert res.status_code == 201
        assert res.json()["role"] == "admin"


# ─── Login endpoint ───────────────────────────────────────────────────────────


class TestLoginEndpoint:

    def test_login_valid_credentials_returns_tokens(self, client, make_user):
        make_user(username="loginuser", email="login@qf.local", password="password123")
        res = client.post(
            "/api/auth/login",
            data={
                "username": "loginuser",
                "password": "password123",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "loginuser"

    def test_login_wrong_password_returns_401(self, client, make_user):
        make_user(username="wrongpass", email="wp@qf.local", password="correct")
        res = client.post(
            "/api/auth/login",
            data={
                "username": "wrongpass",
                "password": "incorrect",
            },
        )
        assert res.status_code == 401

    def test_login_nonexistent_user_returns_401(self, client):
        res = client.post(
            "/api/auth/login",
            data={
                "username": "ghost",
                "password": "whatever",
            },
        )
        assert res.status_code == 401

    def test_login_inactive_user_returns_400(self, client, make_user):
        make_user(
            username="inactive",
            email="inactive@qf.local",
            password="pass",
            is_active=False,
        )
        res = client.post(
            "/api/auth/login",
            data={
                "username": "inactive",
                "password": "pass",
            },
        )
        assert res.status_code == 400


# ─── /me endpoint ────────────────────────────────────────────────────────────


class TestMeEndpoint:

    def test_me_returns_current_user(self, client, auth_headers, admin_user):
        res = client.get("/api/auth/me", headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["username"] == admin_user.username

    def test_me_without_token_returns_401(self, client):
        res = client.get("/api/auth/me")
        assert res.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        res = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer totally.invalid.token"}
        )
        assert res.status_code == 401


# ─── Token refresh ────────────────────────────────────────────────────────────


class TestTokenRefresh:

    def test_refresh_with_valid_refresh_token(self, client, make_user):
        make_user(username="refuser", email="ref@qf.local", password="pass")
        login_res = client.post(
            "/api/auth/login", data={"username": "refuser", "password": "pass"}
        )
        refresh_token = login_res.json()["refresh_token"]
        res = client.post(f"/api/auth/refresh?refresh_token={refresh_token}")
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_refresh_with_access_token_fails(self, client, admin_token):
        """Providing an access token as refresh token must be rejected."""
        res = client.post(f"/api/auth/refresh?refresh_token={admin_token}")
        assert res.status_code == 401
