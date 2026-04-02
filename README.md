# ICB Performance Dashboard

Dashboard SaaS premium (dark mode) com backend FastAPI + frontend React/Tailwind, ingestão automática de planilha Excel no Dropbox e atualização incremental por verificação de versão do arquivo.

## Arquitetura

- `backend/`: API, job de sincronização, processamento de Excel, camada de dados (SQLite com URL configurável para Postgres).
- `frontend/`: dashboard executivo em React + Recharts + Tailwind (estilo glass/dark).

## Funcionalidades implementadas

- Download automático do arquivo mais recente do Dropbox via `download_latest_file_from_dropbox()`.
- Processamento da planilha com `pandas` e limpeza obrigatória:
  - remove colunas totalmente vazias;
  - separa linhas para tabelas operacionais e de produção;
  - nulos numéricos viram `0`;
  - ignora profissional vazio;
  - força receita/cirurgias não negativas.
- Estratégia de atualização completa (truncate lógico): apaga tabelas e reprocessa tudo (sem append).
- Flags de qualidade de dados:
  - `mes_incompleto`;
  - `dados_inconsistentes`.
- Endpoint `GET /last-update` com status `updated|stale` (stale após 6h por padrão).
- Endpoint `GET /dashboard` para cards, gráficos e tabela.
- Job automático a cada 5 minutos para detectar mudança do arquivo (rev do Dropbox).
- Frontend com:
  - Header global “ICB Performance Dashboard”;
  - Badge visual de atualização (verde/amarelo/vermelho + pulse);
  - cards executivos;
  - gráficos (receita mês, cirurgias mês, receita por unidade);
  - tabela de unidades;
  - regra de negócio respeitada (não exibe receita por profissional).

## Modelagem de dados (chaves únicas)

- `fact_unidade_mensal`: chave única `(unidade, ano, mes)`.
- `fact_producao_profissional`: chave única `(profissional, unidade, ano, mes)`.
- `fact_financeiro`: chave única `(competencia)`.

## Variáveis de ambiente

### Backend (`backend/.env`)

Use `backend/.env.example` como base:

- `DATABASE_URL` (ex.: `sqlite:///./icb_dashboard.db` ou URL Postgres futuramente)
- `DROPBOX_ACCESS_TOKEN`
- `DROPBOX_FOLDER_PATH`
- `DROPBOX_FILE_EXTENSION` (default `.xlsx`)
- `UPDATE_INTERVAL_MINUTES` (default `5`)
- `STALE_THRESHOLD_HOURS` (default `6`)

### Frontend (`frontend/.env`)

Use `frontend/.env.example`:

- `VITE_API_URL` (default `http://localhost:8000`)

## Como executar

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

## Endpoints

- `GET /health`
- `GET /last-update`
  ```json
  {
    "last_update": "2026-04-02 10:32:00",
    "status": "updated"
  }
  ```
- `GET /dashboard`

## Observações

- Receita operacional do dashboard vem de `fact_unidade_mensal`.
- Receita do financeiro (DRE) é mantida separada em `fact_financeiro` e não é misturada nos gráficos operacionais.
