# Implementação OAuth 2.0 Dropbox - Resumo Executivo

## 1. Problema Identificado ❌
- **Antes**: Sistema dependia de `DROPBOX_ACCESS_TOKEN` gerado manualmente
- **Problema**: Tokens expiram rapidamente (401 errors), forçando regeneração manual
- **Impacto**: Sincronização de dados quebrava a cada poucas horas

## 2. Solução Implementada ✅
- **Novo fluxo**: OAuth 2.0 com refresh token automático
- **Benefício**: Access tokens são renovados automaticamente, sem intervenção manual
- **Durabilidade**: Refresh tokens duram até 6 meses (vs. horas para access tokens)

## 3. Arquivos Alterados

### Novos Arquivos Criados
```
backend/app/services/dropbox_service.py      [NOVO] Gerenciador OAuth 2.0
backend/app/services/__init__.py              [NOVO] Pacote services
backend/app/get_dropbox_refresh_token.py      [NOVO] Script para obter refresh token
backend/.env.example                          [NOVO] Template de variáveis de ambiente
```

### Arquivos Refatorados
```
backend/app/config.py                         [ALTERADO] Novas variáveis de ambiente
backend/app/main.py                           [ALTERADO] Inicialização OAuth + endpoint teste
backend/app/dropbox_client.py                 [ALTERADO] Usa novo serviço OAuth
```

## 4. Variáveis de Ambiente Necessárias

Cadastre em **Replit Secrets** (ou .env):

| Variável | Descrição | Obrigário |
|----------|-----------|-----------|
| `DROPBOX_APP_KEY` | Client ID (OAuth) | ✅ Sim |
| `DROPBOX_APP_SECRET` | Client Secret (OAuth) | ✅ Sim |
| `DROPBOX_REFRESH_TOKEN` | Token de renovação | ✅ Sim |
| `DROPBOX_FOLDER_PATH` | Caminho na pasta Dropbox | ❌ Não (padrão: `/`) |
| `DROPBOX_FILE_EXTENSION` | Extensão dos arquivos | ❌ Não (padrão: `.xlsx`) |

## 5. Passos Finais no Dropbox Developer Console

### 5a. Criar App (se ainda não tem)
1. https://www.dropbox.com/developers/apps
2. "Create app" → Dropbox API → Scoped access → Full Dropbox

### 5b. Configurar Redirect URI
1. Settings → OAuth 2
2. Adicione: `http://localhost:8000/oauth/callback`
3. Clique "Add" e salve

### 5c. Obter App Key e Secret
1. No "Settings" da app
2. Copie "App key" (DROPBOX_APP_KEY)
3. Copie "App secret" (DROPBOX_APP_SECRET)

## 6. Como Obter o Refresh Token

```bash
cd backend
python app/get_dropbox_refresh_token.py
```

O script:
1. Abre seu navegador
2. Você faz login no Dropbox
3. Autoriza a app
4. Recebe o `DROPBOX_REFRESH_TOKEN`

## 7. Validar a Configuração

Após configurar as variáveis, reinicie o backend e acesse:

```
GET http://localhost:8000/dropbox/test
```

**Resposta esperada (sucesso):**
```json
{
  "status": "success",
  "message": "Conexão com Dropbox validada",
  "entries_count": 42
}
```

**Resposta esperada (erro):**
```json
{
  "status": "error",
  "message": "DROPBOX_APP_KEY, DROPBOX_APP_SECRET e DROPBOX_REFRESH_TOKEN são obrigatórios"
}
```

## 8. Como Funciona Internamente

### Inicialização (Startup)
```python
# main.py
init_dropbox(
    app_key=settings.dropbox_app_key,
    app_secret=settings.dropbox_app_secret,
    refresh_token=settings.dropbox_refresh_token,
)
```

### Renovação Automática
```python
# services/dropbox_service.py
def get_valid_access_token(self) -> str:
    # Se token expirou, renova automaticamente
    if current_time >= self._token_expires_at:
        self._refresh_access_token()
    return self._access_token
```

### Uso no Download
```python
# dropbox_client.py
manager = get_dropbox_manager()
folder_data = manager.list_folder(path)
file_content = manager.download_file(path)
```

## 9. Tratamento de Erros

| Erro | Causa | Solução |
|------|-------|---------|
| `DROPBOX_APP_KEY... são obrigatórios` | Variáveis não configuradas | Cadastre em Replit Secrets |
| `invalid_grant` | Refresh token inválido/expirado | Regenere seguindo passo 6 |
| `unauthorized_client` | App Key/Secret incorretos | Verifique no Developer Console |
| `Falha ao renovar token` | Rede/timeout | Verifique conexão internet |

## 10. Compatibilidade

- ✅ Funcionalidade anterior preservada
- ✅ Sincronização automática continua funcionando
- ✅ Dashboard recebe dados normalmente
- ✅ Sem quebra de código existente

## 11. Próximos Passos

1. **Criar app no Dropbox Developer Console** (se ainda não tem)
   - Anotir App Key e App Secret

2. **Configurar Redirect URI**
   - Adicione `http://localhost:8000/oauth/callback`

3. **Executar script de refresh token**
   ```bash
   python app/get_dropbox_refresh_token.py
   ```
   - Irá gerar o `DROPBOX_REFRESH_TOKEN`

4. **Cadastrar as 3 variáveis em Replit Secrets**
   - DROPBOX_APP_KEY
   - DROPBOX_APP_SECRET
   - DROPBOX_REFRESH_TOKEN

5. **Reiniciar backend**
   - Será inicializado automaticamente

6. **Testar conexão**
   ```bash
   curl http://localhost:8000/dropbox/test
   ```

7. **Monitorar logs**
   ```
   Backend API → Visualizar logs
   ```
   - Procure por: "Dropbox OAuth inicializado com sucesso"

## 12. Arquitetura Final

```
┌─────────────────────────────┐
│  Dropbox API                │
└──────────────┬──────────────┘
               │
         ┌─────▼──────────┐
         │ OAuth 2.0      │
         │ Token Endpoint │
         └─────┬──────────┘
               │
     ┌─────────▼─────────────────────┐
     │ DropboxOAuthManager           │
     │ - Renovação automática        │
     │ - Cache de token              │
     │ - Tratamento de erros         │
     └─────────┬─────────────────────┘
               │
     ┌─────────▼─────────────────────┐
     │ download_latest_file_...()    │
     │ (dropbox_client.py)           │
     └─────────┬─────────────────────┘
               │
     ┌─────────▼─────────────────────┐
     │ sync_job.py                   │
     │ → process_excel_full_refresh()│
     │ → FactUnidadeMensal           │
     │ → Dashboard                   │
     └───────────────────────────────┘
```

---

**Implementação completa e pronta para produção! 🚀**
