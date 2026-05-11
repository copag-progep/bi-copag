# BI COPAG — Business Intelligence para Processos do SEI

Plataforma web de Business Intelligence desenvolvida para a **COPAG (Coordenadoria de Cadastro e Pagamento)** da **UFC / Pró-Reitoria de Gestão de Pessoas**. Transforma snapshots CSV exportados do SEI em dashboards gerenciais, análises de produtividade, alertas automáticos e relatórios.

📖 **[Documentação técnica completa](https://bi-copag.vercel.app/documentacao)**  
🚀 **[Acesso ao sistema](https://bi-copag.vercel.app)**

---

## O que a plataforma entrega

| Funcionalidade | Descrição |
|---|---|
| **Dashboard executivo** | KPIs, distribuição por setor/tipo, ranking de atribuições, evolução diária |
| **Entradas e saídas** | Comparativo de fluxo entre snapshots consecutivos |
| **Produtividade** | Processos recebidos, finalizados e tempo médio por servidor |
| **Atribuições** | Carteira completa com flags de criticidade por tempo (6 faixas até 90d+) |
| **Servidores** | Balanceamento de carga, classificação de sobrecarga, perfil longitudinal |
| **Múltiplos setores** | Detecção de processos em mais de um setor no mesmo dia |
| **Indicadores mensais** | Painel histórico com importação de CSV e lançamento manual |
| **Busca global** | Histórico completo de movimentações de qualquer protocolo |
| **Alertas por e-mail** | Notificação semanal de processos críticos (>30, >45, >90 dias), às sextas 21:00 BRT |
| **Notificação in-app** | Sino com contagem em tempo real de processos ≥45 dias |
| **Upload automático** | Script que acessa o SEI e envia dados sem intervenção humana (19h BRT) |
| **Relatório semanal** | E-mail automático toda sexta com resumo dos indicadores |
| **Exportação PDF / Excel** | Relatório de atribuições com identidade visual Progep/UFC |
| **Log de auditoria** | Registro de todas as ações críticas do sistema |

---

## Stack tecnológica

**Backend:** Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · Pandas · JWT · bcrypt  
**Frontend:** React 18 · Vite · React Router 6 · Recharts · Axios · jsPDF · SheetJS  
**Banco de dados:** PostgreSQL (Neon DB)  
**Automação:** Playwright · httpx · GitHub Actions

---

## Infraestrutura de produção

```
GitHub (copag-progep/bi-copag)
    ├── Render     → API FastAPI  (bi-copag-api.onrender.com)
    ├── Vercel     → Frontend     (bi-copag.vercel.app)
    └── Neon DB    → PostgreSQL   (us-east-1 / AWS)
```

Todo push para `main` dispara deploy automático no Render e no Vercel.

---

## Desenvolvimento local

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

---

## Variáveis de ambiente

### Render (backend)

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | String de conexão PostgreSQL (Neon) |
| `JWT_SECRET_KEY` | Chave para assinar tokens JWT |
| `API_UPLOAD_KEY` | Chave para uploads automáticos (scripts) |
| `DEFAULT_ADMIN_EMAIL` | E-mail do admin padrão |
| `DEFAULT_ADMIN_PASSWORD` | Senha inicial do admin |
| `AUTO_IMPORT_SAMPLE_DATA` | `false` em produção |

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
| `keep-alive` | A cada 10 min | Mantém o Render ativo (sem cold start) |
| `daily-upload` | Seg–Sex 19:00 BRT | Upload automático de todos os setores do SEI |
| `weekly-report` | Sex 20:00 BRT | Relatório gerencial por e-mail |
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
