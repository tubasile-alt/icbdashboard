# ICB Dashboard Evoluído

## Status de implementação por etapas

- ✅ **Etapa 1 concluída**: estrutura de pastas modular.
- ✅ **Etapa 2 concluída**: schema do banco completo para as tabelas fact + metadata + quality report.
- ✅ **Etapa 3 concluída**: limpeza robusta + testes de consistência automatizados.

## 1) Estrutura de pastas (concluída)

```text
backend/
  app/
    api/
      dashboard_service.py      # consultas agregadas e respostas dos endpoints
    etl/
      excel_pipeline.py         # ingestão + limpeza + normalização full refresh
    config.py
    database.py
    dropbox_client.py
    main.py                     # rotas FastAPI
    models.py                   # schema SQLAlchemy
    sync_job.py                 # scheduler de atualização automática
frontend/
  src/
    App.jsx
    components/
    lib/api.js
```

## 2) Schema do banco (concluída)
- `fact_unidade_mensal` (chave: unidade+ano+mes).
- `fact_producao_profissional_mensal` (chave: profissional+unidade+ano+mes).
- `fact_financeiro_mensal` (granularidade por competência, opcional unidade).
- `fact_fiscal_mensal` (granularidade por competência, opcional unidade).
- `metadata` (status e timestamps da atualização).
- `ingestion_quality_report` (métricas de qualidade da carga).

### Chaves e unicidade
- `fact_unidade_mensal`: unique `(unidade, ano, mes)`.
- `fact_producao_profissional_mensal`: unique `(profissional, unidade, ano, mes)`.
- `fact_financeiro_mensal`: unique `(unidade_ref, competencia)` para cobrir cenário consolidado e por unidade.
- `fact_fiscal_mensal`: unique `(unidade_ref, competencia)` para cobrir cenário consolidado e por unidade.

## 3) Módulo ETL da planilha
Arquivo: `backend/app/etl/excel_pipeline.py`

Fluxo:
1. Baixa e lê Excel do Dropbox (via `sync_job.py` + `dropbox_client.py`).
2. Usa apenas abas oficiais:
   - `Base Dados` (operacional)
   - `Despesas 2026` (financeiro)
   - `% Notas fiscais` (fiscal)
3. Remove colunas 100% vazias e normaliza nomes para `snake_case`.
4. Deriva `ano`, `mes`, `competencia`, `trimestre`.
5. Agrega por chave mensal obrigatória.
6. Recalcula KPIs operacionais sem misturar DRE.
7. Marca `mes_incompleto` e `dados_inconsistentes`.
8. Faz `full refresh` (delete + insert) em todas as facts.
9. Registra `metadata` + `ingestion_quality_report`.

### Testes de consistência (Etapa 3)
- Arquivo: `backend/tests/test_etl_consistency.py`
- Casos cobertos:
  - limpeza de quebras/whitespace em campos texto;
  - normalização e mapeamento de aliases de colunas;
  - detecção de `mes_incompleto` e `dados_inconsistentes`;
  - registro de qualidade (`processed_rows`, `empty_columns_removed`).

## 4) Endpoints backend
- `GET /health`
- `GET /last-update`
- `GET /dashboard/summary`
- `GET /dashboard/unidades`
- `GET /dashboard/profissionais`
- `GET /dashboard/financeiro`
- `GET /dashboard/fiscal`

Filtros globais: `anos`, `meses`, `competencias`, `unidades` (e `profissionais` quando aplicável).

## 5) Frontend (após backend)
Frontend permanece consumindo os endpoints acima via `frontend/src/lib/api.js` e exibindo módulos operacional/financeiro/fiscal em cards, gráficos e tabelas.

## Execução local
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
