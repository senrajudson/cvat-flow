# src/utils/cvat_auth.py
from __future__ import annotations

from dataclasses import dataclass
import requests

from src.login.auth import User


@dataclass
class CvatAuth:
    base_url: str
    timeout: int = 30

    def login_token(self, user: User, token_name: str = "training-model") -> str:
        """
        Fluxo robusto (CVAT 2.54.x):
        """
        base = self.base_url.rstrip("/")
        s = requests.Session()

        # 1) tenta login direto (se alguma build devolver token)
        r = s.post(
            f"{base}/api/auth/login",
            json=user.identity_payload(),
            headers={"Accept": "application/vnd.cvat+json"},
            timeout=self.timeout,
        )

        if r.status_code >= 400:
            raise RuntimeError(f"Login falhou ({r.status_code}): {r.text}")

        token = self._extract_token_from_response(r)
        if token:
            return token

        # 2) csrftoken
        s.get(f"{base}/api/auth/login", headers={"Accept": "application/vnd.cvat+json"}, timeout=self.timeout)
        csrf = s.cookies.get("csrftoken")

        headers = {
            "Referer": base,
            "Accept": "application/vnd.cvat+json",
        }
        if csrf:
            headers["X-CSRFToken"] = csrf

        # 3) login por sessão com CSRF
        r2 = s.post(
            f"{base}/api/auth/login",
            json=user.identity_payload(),
            headers=headers,
            timeout=self.timeout,
        )
        if r2.status_code >= 400:
            raise RuntimeError(f"Login(sessão) falhou ({r2.status_code}): {r2.text}")

        # 4) criar access token
        r3 = s.post(
            f"{base}/api/auth/access_tokens",
            json={"name": token_name},
            headers=headers,
            timeout=self.timeout,
        )
        if r3.status_code >= 400:
            raise RuntimeError(f"Create token falhou ({r3.status_code}): {r3.text}")

        token = self._extract_token_from_response(r3)
        if not token:
            raise RuntimeError(f"Token criado mas não achei 'key/token' no JSON: {self._safe_json(r3)}")

        return token

    def _safe_json(self, r: requests.Response) -> dict:
        try:
            return r.json()
        except Exception:
            return {}

    def _extract_token_from_response(self, r: requests.Response) -> str | None:
        data = self._safe_json(r)
        if not data:
            return None

        for k in ("key", "token", "auth_token", "access_token"):
            v = data.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

        if isinstance(data.get("result"), dict):
            for k in ("key", "token", "access_token"):
                v = data["result"].get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

        return None
