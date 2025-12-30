# cvat_login.py
from src.utils.auth import User

import requests


session = requests.Session()


def login_cvat(login: User, base_url: str) -> requests.Session:
    try:
        # 1. Faz uma chamada GET inicial para obter o cookie CSRF
        session.get(f"{base_url}/api/auth/login", timeout=10)
        
        # 2. Prepara os headers com o token obtido
        headers = {}
        if "csrftoken" in session.cookies:
            headers["X-CSRFToken"] = session.cookies["csrftoken"]
            headers["Referer"] = base_url # Algumas versões exigem o Referer

        # 3. Faz o POST de login com o payload correto
        res = session.post(
            f"{base_url}/api/auth/login",
            json=login.identity_payload(), # Usa sua lógica de username ou email
            headers=headers,
            timeout=10
        )
        
        # Log para debug se falhar
        if res.status_code != 200:
            print(f"Erro no Login: {res.text}")
            
        res.raise_for_status()
        return session

    except Exception as e:
        print(f"Falha na conexão: {e}")
        raise
