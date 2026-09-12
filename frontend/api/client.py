import requests
import streamlit as st

from config import API_URL


class _ErrorResponse:
    """Returned when a request exception occurs so callers get a consistent interface."""

    def __init__(self, error: str):
        self.status_code = 0
        self.text = error

    def json(self):
        return {}


class APIClient:
    def _headers(self):
        token = st.session_state.get("token")
        return {"Authorization": f"Bearer {token}"} if token else {}

    def login(self, email: str, password: str) -> bool:
        try:
            response = requests.post(
                f"{API_URL}/auth/login",
                json={"email": email, "password": password},
                timeout=15,
            )
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error during login: {e}")
            return False

        if response.status_code == 200:
            data = response.json()
            st.session_state.token = data["access_token"]
            st.session_state.refresh_token = data.get("refresh_token")
            try:
                user_response = requests.get(
                    f"{API_URL}/auth/me", headers=self._headers(), timeout=15
                )
                if user_response.status_code == 200:
                    st.session_state.user = user_response.json()
            except requests.exceptions.RequestException:
                pass
            return True
        return False

    def register(self, email, username, password, confirm_password, full_name=None):
        try:
            response = requests.post(
                f"{API_URL}/auth/register",
                json={
                    "email": email,
                    "username": username,
                    "password": password,
                    "confirm_password": confirm_password,
                    "full_name": full_name,
                },
                timeout=15,
            )
            return response.status_code == 201
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error during registration: {e}")
            return False

    def get(self, path, **params):
        try:
            return requests.get(
                f"{API_URL}{path}", headers=self._headers(), params=params, timeout=15
            )
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")
            return _ErrorResponse(str(e))

    def post(self, path, json=None):
        try:
            return requests.post(
                f"{API_URL}{path}", headers=self._headers(), json=json, timeout=15
            )
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")
            return _ErrorResponse(str(e))

    def put(self, path, json=None):
        try:
            return requests.put(
                f"{API_URL}{path}", headers=self._headers(), json=json, timeout=15
            )
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")
            return _ErrorResponse(str(e))

    def delete(self, path):
        try:
            return requests.delete(
                f"{API_URL}{path}", headers=self._headers(), timeout=15
            )
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")
            return _ErrorResponse(str(e))
