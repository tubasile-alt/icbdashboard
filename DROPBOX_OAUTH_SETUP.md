# Configuração OAuth 2.0 Dropbox

## O Problema
O sistema anterior usava **access tokens temporários** gerados manualmente que expiram rapidamente (401 errors). Agora usa **OAuth 2.0 com refresh token** que renovam automaticamente.

## Solução Implementada

### Novos Arquivos
- `backend/app/services/dropbox_service.py` - Gerenciador OAuth 2.0 com renovação automática
- `backend/app/get_dropbox_refresh_token.py` - Script para obter o refresh token

### Alterações nos Arquivos
- `backend/app/config.py` - Novas variáveis de ambiente
- `backend/app/main.py` - Inicialização do OAuth na startup
- `backend/app/dropbox_client.py` - Refatorado para usar o novo serviço

## Passo 1: Criar App no Dropbox Developer Console

1. Acesse https://www.dropbox.com/developers/apps
2. Clique em "Create app"
3. Selecione:
   - **API**: Dropbox API
   - **Access type**: Full Dropbox
   - **Type**: Scoped access
4. Clique "Create"
5. Você receberá:
   - **App Key** (Client ID)
   - **App Secret** (Client Secret)

## Passo 2: Configurar Redirect URI

No Dropbox Developer Console do seu app:

1. Vá para "Settings" → "OAuth 2"
2. Em "Redirect URIs", adicione:
   ```
   http://localhost:8000/oauth/callback
   ```
3. Clique "Add" e salve

## Passo 3: Obter o Refresh Token

Executar no backend:
```bash
cd backend
python app/get_dropbox_refresh_token.py
```

Será solicitado:
- `DROPBOX_APP_KEY`: Cole o App Key obtido no Passo 1
- `DROPBOX_APP_SECRET`: Cole o App Secret obtido no Passo 1

O script abrirá seu navegador para fazer login no Dropbox. Após autorizar:
- Você receberá o `DROPBOX_REFRESH_TOKEN`

## Passo 4: Configurar Variáveis de Ambiente

Adicione em **Replit Secrets** ou `.env`:

```
DROPBOX_APP_KEY=xxxxxxxxxxxxx
DROPBOX_APP_SECRET=xxxxxxxxxxxxx
DROPBOX_REFRESH_TOKEN=xxxxxxxxxxxxx
```

## Passo 5: Testar a Conexão

Reinicie o backend e acesse:
```
GET http://localhost:8000/dropbox/test
```

Resposta esperada (sucesso):
```json
{
  "status": "success",
  "message": "Conexão com Dropbox validada",
  "entries_count": 42
}
```

## Como Funciona

1. **Inicialização** (startup)
   - Backend lê `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`
   - Inicializa o `DropboxOAuthManager`

2. **Renovação Automática**
   - Primeiro access token é gerado via refresh token
   - Token fica em cache (válido por ~1 hora)
   - 1 minuto antes de expirar, novo token é gerado automaticamente
   - Nenhuma ação manual necessária

3. **Chamadas à API**
   - `download_latest_file_from_dropbox()` usa o access token válido
   - Sincronização continua funcionando normalmente

## Variáveis de Ambiente

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `DROPBOX_APP_KEY` | Client ID da app | `j7xq2m9k1p3r` |
| `DROPBOX_APP_SECRET` | Client Secret da app | `a8b2c3d4e5f6` |
| `DROPBOX_REFRESH_TOKEN` | Token de renovação | `sl.u.AGY4...` |
| `DROPBOX_FOLDER_PATH` | Caminho na pasta Dropbox (opcional) | `/Controle` |
| `DROPBOX_FILE_EXTENSION` | Extensão dos arquivos | `.xlsx` |

## Tratamento de Erros

### "DROPBOX_APP_KEY, DROPBOX_APP_SECRET e DROPBOX_REFRESH_TOKEN são obrigatórios"
- As 3 variáveis não foram configuradas
- Revise o Passo 4

### "Erro na renovação do token: invalid_grant"
- O refresh token é inválido ou expirou
- Regenere seguindo o Passo 3

### "Erro na renovação do token: unauthorized_client"
- App Key ou App Secret estão incorretos
- Verifique no Dropbox Developer Console

### "Nenhum arquivo Excel encontrado"
- Nenhum arquivo `.xlsx` no caminho `DROPBOX_FOLDER_PATH`
- Verifique se o arquivo existe no Dropbox

## Testando Localmente

Depois de configurar as variáveis, teste:

```bash
# Teste da conexão
curl http://localhost:8000/dropbox/test

# Teste da sincronização
curl http://localhost:8000/health
```

## Próximas Etapas

1. Configure as 3 variáveis de ambiente
2. Reinicie o backend
3. Acesse `/dropbox/test` para validar
4. A sincronização iniciará automaticamente a cada 5 minutos
