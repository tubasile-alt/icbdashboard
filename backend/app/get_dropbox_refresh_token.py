"""
Script para obter o refresh token do Dropbox.

Passos:
1. Configure seu app no Dropbox Developer Console: https://www.dropbox.com/developers/apps
   - App type: Scoped access
   - Access type: Full Dropbox
   
2. Obtenha:
   - App Key (Client ID)
   - App Secret (Client Secret)
   
3. Configure Redirect URI para: http://localhost:8000/oauth/callback
   
4. Execute este script para abrir o navegador e fazer login

5. Copie o refresh token gerado e adicione às variáveis de ambiente:
   - DROPBOX_APP_KEY
   - DROPBOX_APP_SECRET
   - DROPBOX_REFRESH_TOKEN
"""

import json
import logging
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlencode, urlparse

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_KEY = input("Digite o DROPBOX_APP_KEY: ").strip()
APP_SECRET = input("Digite o DROPBOX_APP_SECRET: ").strip()
REDIRECT_URI = "http://localhost:8000/oauth/callback"

AUTHORIZE_URL = "https://www.dropbox.com/oauth2/authorize"
TOKEN_URL = "https://api.dropboxapi.com/oauth2/token"

auth_code = None
server = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urlparse(self.path).query
        params = parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<h1>Sucesso!</h1><p>Você pode fechar esta janela.</p>"
            )
            logger.info("Authorization code recebido!")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Erro: codigo nao recebido")

    def log_message(self, format, *args):
        pass


def main():
    global auth_code, server

    params = {
        "client_id": APP_KEY,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "token_access_type": "offline",
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"

    logger.info(f"Abrindo navegador para autorizar...\n{auth_url}")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", 8000), OAuthCallbackHandler)
    logger.info("Aguardando redirecionamento...")
    server.handle_request()

    if not auth_code:
        logger.error("Nenhum codigo de autorizacao recebido")
        sys.exit(1)

    logger.info(f"Exchanging code for refresh token...")
    token_payload = {
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "client_id": APP_KEY,
        "client_secret": APP_SECRET,
    }

    token_response = requests.post(TOKEN_URL, data=token_payload)

    if token_response.status_code != 200:
        logger.error(f"Erro ao obter token: {token_response.text}")
        sys.exit(1)

    token_data = token_response.json()
    refresh_token = token_data.get("refresh_token")

    if not refresh_token:
        logger.error("Refresh token nao recebido na resposta")
        logger.info(f"Resposta: {json.dumps(token_data, indent=2)}")
        sys.exit(1)

    logger.info("\n" + "=" * 60)
    logger.info("SUCESSO! Salve estas variáveis de ambiente:")
    logger.info("=" * 60)
    logger.info(f"DROPBOX_APP_KEY={APP_KEY}")
    logger.info(f"DROPBOX_APP_SECRET={APP_SECRET}")
    logger.info(f"DROPBOX_REFRESH_TOKEN={refresh_token}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
