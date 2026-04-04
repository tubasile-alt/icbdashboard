"""
Script simplificado para obter Dropbox Refresh Token.

Uso:
1. Execute este script
2. Copie a URL gerada
3. Cole em seu navegador e autorize
4. Copie o código da URL para a qual foi redirecionado
5. Cole aqui
6. Receberá o DROPBOX_REFRESH_TOKEN
"""

import json
import sys
from urllib.parse import urlencode

import requests

APP_KEY = "13zvqplys9czp0z"
APP_SECRET = "utd3asnmf59hdam"
REDIRECT_URI = "http://localhost:8000/oauth/callback"

AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"


def main():
    print("\n" + "=" * 70)
    print("OBTER DROPBOX REFRESH TOKEN")
    print("=" * 70)

    params = {
        "client_id": APP_KEY,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "token_access_type": "offline",
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    print("\n1. Copie esta URL e cole em seu navegador:")
    print(f"\n   {auth_url}\n")

    print("2. Você será redirecionado para uma página com a URL assim:")
    print("   http://localhost:8000/oauth/callback?code=YOUR_CODE_HERE&...\n")

    print("3. Cole o VALUE do parâmetro 'code' abaixo:")
    auth_code = input("   Cole o código: ").strip()

    if not auth_code:
        print("❌ Erro: código não fornecido")
        sys.exit(1)

    print("\n⏳ Trocando código por token...")

    token_payload = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "client_id": APP_KEY,
        "client_secret": APP_SECRET,
    }

    try:
        token_response = requests.post(TOKEN_URL, data=token_payload, timeout=10)

        if token_response.status_code != 200:
            print(f"❌ Erro: {token_response.text}")
            sys.exit(1)

        token_data = token_response.json()

        if "error" in token_data:
            print(f"❌ Erro: {token_data.get('error_description', token_data.get('error'))}")
            sys.exit(1)

        refresh_token = token_data.get("refresh_token")

        if not refresh_token:
            print("❌ Erro: refresh token não recebido")
            print(f"Resposta: {json.dumps(token_data, indent=2)}")
            sys.exit(1)

        print("\n" + "=" * 70)
        print("✅ SUCESSO! Copie os valores abaixo:")
        print("=" * 70)
        print(f"\nDROPBOX_APP_KEY=13zvqplys9czp0z")
        print(f"DROPBOX_APP_SECRET=utd3asnmf59hdam")
        print(f"DROPBOX_REFRESH_TOKEN={refresh_token}")
        print("\n" + "=" * 70)
        print("Adicione em Replit Secrets e reinicie o backend!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
