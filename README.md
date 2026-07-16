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
| **Pauta Prioritária** | Sessões semanais para acompanhar processos críticos, atribuir responsáveis, acompanhar prazos/reuniões, registrar notas, gerar PDF, encerrar ciclos e medir eficiência |
| **Atribuições** | Carteira completa com flags de criticidade por tempo (6 faixas até 90d+) |
| **Servidores** | Balanceamento de carga, classificação de sobrecarga, perfil longitudinal |
| **Múltiplos setores** | Detecção de processos em mais de um setor no mesmo dia, com exportação Excel/PDF |
| **Indicadores mensais** | Painel histórico com importação de CSV e lançamento manual |
| **Controle por divisão** | Usuários comuns visualizam apenas os setores liberados pelo administrador |
| **Permissão de upload** | O administrador define quais usuários podem enviar relatórios e de quais setores |
| **Usuários SEI por setor** | Vincula servidores/atribuições aos setores para filtrar listas de Atribuição e Servidor |
| **Busca global** | Histórico completo de movimentações de qualquer protocolo |
| **Alertas por e-mail** | Notificação semanal de processos críticos (>30, >45, >90 dias), às sextas 21:00 BRT |
| **Notificação in-app** | Sino com contagem em tempo real de processos ≥45 dias e itens pendentes da Pauta Prioritária |
| **Saúde dos dados** | Badge de frescor no topo, indicando data de referência, setores ausentes/defasados e alertas de qualidade |
| **Upload automático** | Script que acessa o SEI e envia dados sem intervenção humana (19h BRT) |
| **Relatório diário** | E-mail automático seg–sex às 19:30 BRT com ativos, fluxo por setor e alertas |
| **Relatório semanal** | E-mail automático toda sexta com resumo dos indicadores |
| **Exportação PDF / Excel** | Relatórios de Atribuições e Múltiplos Setores com identidade visual Progep/UFC |
| **Exportação de pauta em PDF** | Documento de reunião com processos priorizados, responsáveis, status e notas da gestão |
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
| `DISABLE_POST_CHANGE_PRECOMPUTE` | `true` desliga o precompute automático após uploads/alterações; útil em instâncias com pouca RAM |
| `ANALYTICS_CACHE_MAX_ENTRIES` | Limite de entradas do cache LRU analítico |
| `ANALYTICS_CACHE_MAX_TOTAL_MB` | Orçamento total de memória do cache analítico em MB |
| `ANALYTICS_CACHE_MAX_ITEM_MB` | Tamanho máximo de payload individual que pode entrar no cache |
| `ANALYTICS_BUILD_CONCURRENCY` | Quantidade de builds analíticos simultâneos por processo. Padrão recomendado: `1` |
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

## Controle de acesso por divisão

Administradores têm visão completa da plataforma. Usuários comuns só visualizam dados dos setores liberados na aba **Acessos** da página Administração. Esse recorte é aplicado no backend e afeta painéis, KPIs, listas, filtros, datas de referência, indicadores mensais, histórico de uploads e badge de saúde dos dados.

A permissão de envio de relatório é independente: além de ter acesso ao setor, o usuário precisa estar marcado como autorizado para upload. A página **Usuários SEI** também permite vincular servidores/atribuições a um ou mais setores, para que filtros como **Atribuição** e **Servidor** respeitem o escopo do usuário logado.

Na métrica de **Múltiplos setores**, a detecção respeita o escopo do usuário. Usuários restritos só consultam e visualizam ocorrências dentro dos setores permitidos, sem revelar metadados de divisões não autorizadas.

Na tela **Múltiplos setores**, os botões **Exportar Excel** e **Gerar PDF** exportam as ocorrências visíveis no momento, respeitando filtros globais e busca por protocolo.

O cache analítico também participa desse isolamento: o backend inclui o escopo de setores na chave e o frontend não reaproveita cache persistente para usuários comuns antes da resposta atual do servidor.

## Pauta Prioritária

A **Pauta Prioritária** transforma o Score de Risco em rotina de acompanhamento semanal. Administradores criam sessões, adicionam processos críticos a partir das páginas **Score de Risco** ou **Atribuições**, atribuem responsáveis da plataforma e registram orientações para reunião.

Cada sessão possui cronograma visível para todos os perfis com **Início**, **Reunião** e **Prazo da pauta** (`data_fim`), além de contador dinâmico e barra temporal. A situação da sessão é derivada das datas: **A iniciar**, **Em andamento** ou **Encerrada**. O administrador pode editar título, datas e observações pelo editor inline da própria página, inclusive para corrigir sessões encerradas por prazo. A edição valida `data_inicio <= data_fim`, permite limpar datas opcionais e registra auditoria `pauta.sessao_editada` com valores anteriores e novos.

Responsáveis não marcam processos como resolvidos manualmente. Eles apenas confirmam ciência e registram atualizações. A resolução é detectada automaticamente após upload válido: se o protocolo deixar de constar no snapshot do setor acompanhado, o item muda para **Resolvido automaticamente** (`saiu_do_setor`). O administrador mantém um override excepcional, registrado como **Resolvido manualmente**.

Usuários comuns veem apenas sessões com itens atribuídos a eles e, de forma cumulativa, apenas se ainda tiverem acesso ao setor do processo. Se o administrador tentar remover de um usuário um setor que possui itens ativos na pauta, a API bloqueia a alteração até que os itens sejam reatribuídos.

O módulo também permite acompanhar progresso de resolução por sessão, copiar pendências para a próxima sessão, encerrar sessões com auditoria, gerar PDF da pauta de reunião e acompanhar métricas administrativas como tempo médio até resolução automática, overrides manuais e pendências arrastadas. A ação de copiar pendências encerra a sessão de origem quando ela ainda está operável; se a sessão já estiver encerrada por prazo, apenas cria a nova sessão com os itens pendentes.

---

## Documentação completa

A documentação técnica detalhada (arquitetura, modelo de dados, endpoints, manutenção, guia de transição) está disponível em:

**[bi-copag.vercel.app/documentacao](https://bi-copag.vercel.app/documentacao)**

---

*COPAG / Pró-Reitoria de Gestão de Pessoas · UFC*
