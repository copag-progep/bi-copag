# AnalyticSEI — Painéis, indicadores e alertas para gestão de processos do SEI

Plataforma web de Business Intelligence desenvolvida para a **COPAG (Coordenadoria de Cadastro e Pagamento)** da **UFC / Pró-Reitoria de Gestão de Pessoas**. Transforma snapshots CSV exportados do SEI em painéis, indicadores, análises de produtividade, alertas automáticos e relatórios.

📖 **[Documentação técnica completa](https://bi-copag.vercel.app/documentacao)**  
🚀 **[Acesso ao sistema](https://bi-copag.vercel.app)**

---

## O que a plataforma entrega

| Funcionalidade | Descrição |
|---|---|
| **Central Executiva** | Tela única com prioridades do dia, saúde dos dados, KPIs principais e sparklines de tendência |
| **Dashboard executivo** | KPIs, distribuição por setor/tipo, ranking de atribuições, evolução diária |
| **Entradas e saídas** | Comparativo de fluxo entre snapshots consecutivos |
| **Produtividade** | Processos recebidos, finalizados e tempo médio por servidor |
| **Tempo de permanência** | Lead time estimado dos processos que saíram da carteira, com média, mediana, P90, faixas por duração e ranking por setor |
| **Tendências estimadas** | Forecasting simples na Central Executiva: projeção de estoque ativo, tendência por setor e estimativa de críticos |
| **Score de Risco** | Ranking de processos por prioridade de atenção, com explicação dos fatores do score |
| **Atribuições** | Carteira completa com flags de criticidade por tempo (6 faixas até 90d+) |
| **Servidores** | Balanceamento de carga, classificação de sobrecarga, perfil longitudinal |
| **Múltiplos setores** | Detecção de processos em mais de um setor no mesmo dia |
| **Indicadores mensais** | Painel histórico com importação de CSV e lançamento manual |
| **Busca global** | Histórico completo de movimentações de qualquer protocolo |
| **Alertas por e-mail** | Notificação semanal de processos críticos (>30, >45, >90 dias), às sextas 21:00 BRT |
| **Notificação in-app** | Sino com contagem em tempo real de processos ≥45 dias |
| **Saúde dos dados** | Badge de frescor no topo, indicando data de referência, setores ausentes/defasados e alertas de qualidade |
| **Upload automático** | Script que acessa o SEI e envia dados sem intervenção humana (19h BRT) |
| **Relatório diário** | E-mail automático seg–sex às 19:30 BRT com ativos, fluxo por setor e alertas |
| **Relatório semanal** | E-mail automático toda sexta com resumo dos indicadores |
| **Exportação PDF / Excel** | Relatório de atribuições com identidade visual Progep/UFC |
| **Log de auditoria** | Registro de todas as ações críticas do sistema |

---

## Stack tecnológica

**Backend:** Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · Pandas · JWT · bcrypt
**Frontend:** React 18 · Vite · React Router 6 · Recharts · Axios · jsPDF · SheetJS
**Banco de dados:** PostgreSQL (Aiven for PostgreSQL)
**Automação:** Playwright · httpx · GitHub Actions

---

## Infraestrutura de produção

```
GitHub (copag-progep/bi-copag)
    ├── Render     → API FastAPI  (bi-copag-api.onrender.com)
    ├── Vercel     → Frontend     (bi-copag.vercel.app)
    └── Aiven      → PostgreSQL   (bi-copag-db · North America)
```

Todo push para `main` dispara deploy automático no Render e no Vercel.

---

## Desenvolvimento local

Guia completo: **[docs/AMBIENTE_LOCAL.md](docs/AMBIENTE_LOCAL.md)**

Fluxo recomendado para validação antes de commit/push:

```bash
cp .env.local.example .env.local
./scripts/dev_backend.sh
./scripts/dev_frontend.sh
```

Depois acesse `http://127.0.0.1:5173`.

### Backend

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API disponível em `http://localhost:8000` · Docs interativos em `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend disponível em `http://localhost:5173`

Por padrão, o frontend local usa o proxy do Vite para encaminhar `/api` para `http://127.0.0.1:8000`.

---

## Variáveis de ambiente

### Render (backend)

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | String de conexão PostgreSQL (Aiven) |
| `JWT_SECRET_KEY` | Chave para assinar tokens JWT |
| `API_UPLOAD_KEY` | Chave para uploads automáticos (scripts) |
| `DEFAULT_ADMIN_EMAIL` | E-mail do admin padrão |
| `DEFAULT_ADMIN_PASSWORD` | Senha inicial do admin |
| `AUTO_IMPORT_SAMPLE_DATA` | `false` em produção |
| `ANALYTICS_LOOKBACK_DAYS` | Janela máxima de histórico analítico (padrão: 120 dias). `0` = sem limite |
| `DISABLE_STARTUP_PRECOMPUTE` | `false` em produção. `true` desliga o aquecimento de cache na inicialização |
| `PRECOMPUTE_HEAVY_ANALYTICS` | `false` por padrão. `true` inclui endpoints pesados no precompute, como processos parados, atribuições, lead time, forecast e Score de Risco |
| `PRECOMPUTE_COOLDOWN_SECS` | Intervalo mínimo entre precomputes consecutivos (padrão: 120 s) |
| `APP_TIMEZONE` | Fuso usado em checagens operacionais. Padrão: `America/Fortaleza` |
| `DATA_FRESHNESS_OK_MAX_DAYS` | Idade máxima para considerar o dado atualizado. Padrão: `3` |
| `DATA_FRESHNESS_CRITICAL_DAYS` | Idade a partir da qual o dado fica crítico. Padrão: `7` |
| `DATA_QUALITY_DROP_RATIO` | Queda mínima de volume para alerta simples de qualidade. Padrão: `0.6` |
| `RISK_WEIGHT_*` | Pesos do Score de Risco: tempo absoluto, contexto histórico, sem atribuição e múltiplos setores |
| `RISK_TREND_*` | Multiplicadores do Score de Risco conforme tendência do setor |
| `RISK_*_THRESHOLD` | Limiares de classificação do Score de Risco: crítico, elevado e moderado |
| `RISK_MIN_LT_SAMPLE` | Amostra mínima para usar P90 de lead time no Score de Risco. Padrão: `5` |
| `RISK_MIN_P90_DAYS` | Piso técnico do P90 usado no Score de Risco, evitando superpeso de históricos muito curtos. Padrão: `7` |

### GitHub Secrets (automação)

| Secret | Descrição |
|---|---|
| `SEI_URL` | URL base do SEI |
| `SEI_USER` | Login SEI do coordenador |
| `SEI_PASSWORD` | Senha SEI |
| `BI_API_KEY` | Mesma chave que `API_UPLOAD_KEY` |
| `GMAIL_USER` | `copag@progep.ufc.br` |
| `GMAIL_APP_PASSWORD` | Senha de app Google |

---

## Automação (GitHub Actions)

| Workflow | Frequência | Função |
|---|---|---|
| `keep-alive` | A cada 10 min | Pinga `/api/ping` para manter o Render ativo (sem cold start) |
| `daily-upload` | Seg–Sex 19:00 BRT | Upload automático de todos os setores do SEI |
| `daily-report` | Seg–Sex 19:30 BRT | E-mail diário com ativos, fluxo por setor e alertas de críticos. Antes de enviar, confirma se o `daily-upload` do dia concluiu com sucesso |
| `weekly-report` | Sex 20:00 BRT | Relatório gerencial completo por e-mail |
| `critical-alerts` | Sex 21:00 BRT | Alerta de processos críticos (só envia se houver) |

**Troca de coordenador:** atualize apenas `SEI_USER` e `SEI_PASSWORD` nos GitHub Secrets. Nenhum código precisa ser alterado.

---

## Setores monitorados

`DIAPE` · `DICAT` · `DIJOR` · `DICAF` · `DICAF-CHEFIA` · `DICAF-REPOSICOES`

---

## Documentação completa

A documentação técnica detalhada (arquitetura, modelo de dados, endpoints, manutenção, guia de transição) está disponível em:

**[bi-copag.vercel.app/documentacao](https://bi-copag.vercel.app/documentacao)**

---

*COPAG / Pró-Reitoria de Gestão de Pessoas · UFC*
