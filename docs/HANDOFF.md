# HANDOFF - AnalyticSEI

## 1. Objetivo do projeto

Este projeto e o AnalyticSEI, uma plataforma de Business Intelligence para acompanhamento de processos administrativos exportados do SEI em CSV.

Ele cobre quatro frentes principais:

- autenticacao de usuarios da aplicacao
- importacao diaria de snapshots CSV do SEI
- armazenamento e organizacao dos dados em banco relacional
- visualizacao gerencial em dashboards, tabelas e graficos

O uso esperado e:

1. um usuario faz login no sistema
2. envia um CSV exportado do SEI
3. o backend importa esse snapshot para o banco
4. o frontend consome a API analitica
5. o usuario acompanha visao executiva, fluxo, produtividade, processos parados, processos em multiplos setores e indicadores mensais


## 2. Visao geral da arquitetura

O projeto esta organizado em tres camadas:

- codigo versionado no GitHub
- backend FastAPI publicado no Render
- frontend React/Vite publicado no Vercel

Fluxo online:

1. o usuario acessa `https://bi-copag.vercel.app`
2. o Vercel entrega o frontend React ja buildado
3. chamadas para `/api/*` sao reescritas pelo Vercel para a API publica do Render
4. o backend no Render processa autenticacao, upload, consultas administrativas e analytics
5. o backend fala com o banco atraves de `DATABASE_URL`

Ponto importante:

- o codigo nao depende de um provedor especifico de banco
- localmente ele usa SQLite se `DATABASE_URL` nao estiver definida
- em producao ele usa o banco apontado por `DATABASE_URL`
- atualmente o `DATABASE_URL` de producao aponta para o PostgreSQL da Aiven
- isso nao fica hardcoded no codigo


## 3. Repositorio GitHub

Repositorio remoto observado no workspace:

- `https://github.com/copag-progep/bi-copag.git`

Branch principal observada:

- `main`

Historico recente do repositorio mostra manutencoes iterativas em:

- UX da sidebar
- paginacao de tabelas
- compatibilidade do historico de uploads
- ajustes de performance no restore de sessao
- endurecimento da atualizacao da data dos uploads


## 4. Backend

O backend esta em `backend/`.

Tecnologias:

- Python
- FastAPI
- SQLAlchemy ORM
- Pandas
- JWT
- Passlib/Bcrypt

Arquivo de entrada:

- `backend/main.py`

Responsabilidades do backend:

- expor a API HTTP
- autenticar usuarios
- importar CSVs
- persistir snapshots e processos
- consolidar atribuicoes com base no DE-PARA de usuarios SEI
- calcular os dados analiticos dos dashboards
- servir dados de administracao
- servir indicadores mensais


## 5. Banco de dados

### 5.1 Camada de conexao

Arquivo:

- `backend/database.py`

Esse arquivo faz:

- define `Base`
- cria `engine`
- cria `SessionLocal`
- define `get_db()`
- inicializa schema e indices

Comportamento:

- se `DATABASE_URL` nao existir, usa SQLite em `backend/data/sei_bi.db`
- se existir `DATABASE_URL`, usa essa conexao
- se a URL vier no formato `postgres://`, converte para `postgresql://`

Detalhes importantes:

- para SQLite usa `check_same_thread=False`
- para bancos nao-SQLite usa `pool_pre_ping=True`
- para bancos nao-SQLite usa `pool_recycle` configuravel por `SQLALCHEMY_POOL_RECYCLE`
- para bancos nao-SQLite usa `SQLALCHEMY_POOL_SIZE`, `SQLALCHEMY_MAX_OVERFLOW` e `pool_timeout=30`

### 5.2 Evolucao de schema

O projeto usa Alembic para migracoes formais e mantem uma camada pragmatica de compatibilidade.

Na inicializacao, `init_db()` executa:

- `run_migrations()`
- `Base.metadata.create_all(...)`
- `ensure_schema_updates()`
- `ensure_indexes()`

`run_migrations()` executa `alembic upgrade head`. Em bancos existentes sem a tabela `alembic_version`, o sistema sela automaticamente no baseline `0001` antes de aplicar migracoes novas.

Hoje, `ensure_schema_updates()` ainda garante pelo menos a existencia de:

- coluna `atribuicao_normalizada` em `processos`

Isso significa que a evolucao de schema e formalizada por Alembic, mas preserva compatibilidade com bancos antigos por meio das rotinas auxiliares.


## 6. Modelo de dados

Arquivo:

- `backend/models.py`

### 6.1 Tabela `users`

Responsabilidade:

- usuarios do sistema

Campos principais:

- `id`
- `name`
- `email`
- `password_hash`
- `is_admin`
- `created_at`

### 6.2 Tabela `uploads`

Responsabilidade:

- metadados de cada snapshot enviado

Campos principais:

- `id`
- `setor`
- `data_relatorio`
- `data_upload`
- `original_filename`
- `file_hash`
- `total_records`

Restricao importante:

- unicidade por `setor + data_relatorio + file_hash`

### 6.3 Tabela `processos`

Responsabilidade:

- linhas efetivamente importadas do CSV

Campos principais:

- `protocolo`
- `atribuicao`
- `atribuicao_normalizada`
- `tipo`
- `especificacao`
- `ponto_controle`
- `data_autuacao`
- `data_recebimento`
- `data_envio`
- `unidade_envio`
- `observacoes`
- `setor`
- `data_relatorio`
- `upload_id`

Restricao importante:

- unicidade por `protocolo + setor + data_relatorio`

### 6.4 Tabela `sei_users`

Responsabilidade:

- DE-PARA entre nomes do servidor, nome do SEI e usuario do SEI

Campos principais:

- `nome`
- `nome_sei`
- `usuario_sei`
- `nome_key`
- `nome_sei_key`
- `usuario_sei_key`

### 6.5 Tabela `monthly_stats`

Responsabilidade:

- indicadores mensais por setor e periodo

Campos principais:

- `setor`
- `indicador`
- `valor`
- `mes_ano`
- `mes`
- `num_mes`
- `ano`
- `periodo`

Restricao importante:

- unicidade por `setor + indicador + ano + num_mes`


## 7. Inicializacao da API

No `startup` do FastAPI, o backend faz:

1. `init_db()`
2. `ensure_default_user()`
3. `auto_import_workspace_data()`
4. sincronizacao condicional das atribuicoes normalizadas

Detalhes importantes:

- o admin padrao e criado se nao existir
- a importacao automatica de CSVs do workspace depende da flag `AUTO_IMPORT_SAMPLE_DATA`
- a sincronizacao pesada de atribuicoes so roda se houver processos com `atribuicao` preenchida e `atribuicao_normalizada` vazia

Esse ultimo ponto foi importante para reduzir lentidao no boot da API e, por consequencia, no primeiro acesso/login quando o servico acorda.


## 8. Autenticacao

Arquivo:

- `backend/auth.py`

Tecnica usada:

- hash de senha com `bcrypt`
- autenticacao com JWT
- `OAuth2PasswordBearer`

Fluxo:

1. o frontend chama `POST /api/auth/login`
2. o backend localiza o usuario por email
3. valida a senha com bcrypt
4. gera JWT com `sub=email`
5. retorna token + dados do usuario

Rotas relevantes:

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

Protecoes:

- `get_current_user`
- `get_current_admin_user`

Detalhes:

- o token expira conforme `ACCESS_TOKEN_EXPIRE_MINUTES`
- a chave usada para assinar JWT vem de `JWT_SECRET_KEY`


## 9. Importacao dos CSVs do SEI

Arquivo:

- `backend/csv_importer.py`

### 9.1 Setores aceitos

Os setores hoje sao fixos:

- `DIAPE`
- `DICAT`
- `DIJOR`
- `DICAF`
- `DICAF-CHEFIA`
- `DICAF-REPOSICOES`

### 9.2 Colunas esperadas do CSV

As colunas principais mapeadas sao:

- `ID`
- `Protocolo`
- `Atribuicao`
- `Tipo`
- `Especificacao`
- `Ponto_Controle`
- `Data_Autuacao`
- `Data_Recebimento`
- `Data_Envio`
- `Unidade_Envio`
- `Observacoes`

### 9.3 Logica de importacao

O importador:

- tenta ler CSV em `utf-8-sig`, `utf-8` e `latin-1`
- usa `sep=";"`
- normaliza texto vazio, `-` e `nan`
- converte datas com `dayfirst=True`
- remove linhas sem `protocolo`
- elimina duplicatas internas do arquivo por `protocolo`
- calcula hash SHA-256 do arquivo

### 9.4 Regras de negocio do upload

Se o mesmo arquivo for enviado de novo:

- retorna status `duplicate`

Se um novo arquivo diferente for enviado para o mesmo `setor + data_relatorio`:

- o snapshot anterior e substituido

Isso e implementado assim:

- apaga `processos` antigos do mesmo setor/data
- apaga o `upload` antigo do mesmo setor/data
- grava o novo snapshot

### 9.5 Importacao automatica inicial

Funcao:

- `bootstrap_workspace_csvs()`

Procura arquivos no root do projeto com padrao:

- `ListaProcessos_SEIPro_YYYYMMDD_setor.csv`

Em producao, `AUTO_IMPORT_SAMPLE_DATA` esta configurado como `false` no `render.yaml`, entao esse bootstrap nao deve tentar reimportar dados locais a cada startup.


## 10. DE-PARA de usuarios SEI

Arquivo:

- `backend/sei_users.py`

Objetivo:

- consolidar atribuicoes de usuarios que podem aparecer de formas diferentes no CSV

Exemplo pratico:

- um servidor pode aparecer com nome completo
- com nome abreviado
- ou com usuario do SEI

O sistema transforma tudo isso em um nome canonico.

Principais funcoes:

- normalizacao de texto e identidade
- importacao de planilhas `.xls`, `.xlsx` ou `.csv`
- upsert de usuarios SEI
- resolucao da atribuicao canonica
- sincronizacao de `atribuicao_normalizada` nos processos ja importados

Impacto funcional:

- filtros por atribuicao ficam mais consistentes
- rankings e produtividade por atribuicao ficam mais corretos


## 11. Camada analitica

Arquivo:

- `backend/analytics.py`

Essa e a camada mais importante para entendimento do produto.

### 11.1 Filtros

Todos os paineis analiticos usam `AnalyticsFilters` com:

- `data_referencia`
- `data_inicial`
- `data_final`
- `setor`
- `tipo`
- `atribuicao`

### 11.2 Estrategia geral

Os calculos funcionam sobre snapshots diarios.
Como nao ha log transacional do SEI, o sistema infere comportamento historico comparando presencas e ausencias entre snapshots.

### 11.3 Cache

O modulo mantem um cache em memoria com chave formada por:

- nome da consulta
- assinatura dos uploads
- filtros aplicados

A assinatura dos uploads usa:

- quantidade total de uploads
- maior id de upload
- horario do ultimo upload

Quando um upload relevante muda, o cache e limpo via `clear_analytics_cache()`.

### 11.4 Dashboard

`get_dashboard_data()` entrega:

- data de referencia
- total de processos ativos
- total de registros do snapshot
- setores ativos
- processos em multiplos setores
- distribuicao por setor
- distribuicao por tipo
- ranking de atribuicoes
- atribuicoes com mais finalizacoes inferidas
- evolucao diaria

### 11.5 Entradas e saidas

`get_entries_exits_data()` compara a data de referencia com a data anterior disponivel e calcula:

- entradas por setor
- saidas por setor
- saldo por setor
- carga atual
- evolucao diaria de fluxo

### 11.6 Produtividade

`get_productivity_data()` calcula produtividade por atribuicao.

Regra principal:

- producao estimada = processos que estavam na atribuicao no snapshot anterior e nao aparecem mais nela na data de referencia

Entrega:

- kpis do dia
- maior produtor
- resumo por atribuicao
- ranking acumulado no periodo
- serie historica de produtividade

### 11.7 Processos parados

`get_stale_processes_data()` usa spans de permanencia para identificar processos em aberto no setor atual e calcula:

- mais de 10 dias
- mais de 20 dias
- mais de 30 dias
- lista ordenada de processos mais antigos

### 11.8 Processos em multiplos setores

`get_multi_sector_data()` detecta protocolos que aparecem em mais de um setor no mesmo snapshot.

### 11.9 Lead time / tempo de permanencia

`get_lead_time_data()` calcula o tempo estimado de permanencia dos processos que sairam de uma carteira.

Como o SEI exporta snapshots e nao um log transacional completo, o calculo e inferido por spans de presenca:

- o processo aparece em snapshots consecutivos de um setor/atribuicao
- depois deixa de aparecer naquela carteira
- esse intervalo fechado e tratado como um ciclo finalizado

Entrega:

- media de dias
- mediana de dias
- P90, ou percentil 90
- total de processos finalizados usados no calculo
- distribuicao por faixas de duracao
- ranking por setor, tipo e atribuicao

Observacao importante:

- P90 significa que 90% dos processos finalizaram ate aquele prazo e 10% demoraram mais
- esse indicador usa historico completo quando necessario, para nao distorcer duracoes antigas


## 12. Indicadores mensais

Arquivo:

- `backend/monthly_stats.py`

Esse modulo trata uma camada separada do snapshot diario.

Ele permite:

- importar CSV de indicadores mensais
- cadastrar manualmente um conjunto mensal
- editar valores por linha

Indicadores suportados:

- Processos gerados no periodo
- Processos com tramitacao no periodo
- Processos com andamento fechado na unidade ao final do periodo
- Processos com andamento aberto na unidade ao final do periodo
- Documentos gerados no periodo
- Documentos externos no periodo


## 13. Rotas da API

As principais rotas estao em `backend/main.py`.

### 13.1 Saude

- `GET /api/health`

### 13.2 Auth

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### 13.3 Usuarios administrativos

- `GET /api/admin/users`
- `POST /api/admin/users`
- `DELETE /api/admin/users/{user_id}`

### 13.4 Usuarios SEI

- `GET /api/admin/sei-users`
- `POST /api/admin/sei-users`
- `POST /api/admin/sei-users/import`
- `POST /api/admin/sei-users/import-rows`
- `DELETE /api/admin/sei-users/{sei_user_id}`

### 13.5 Indicadores mensais

- `GET /api/monthly-stats`
- `POST /api/admin/monthly-stats/import`
- `POST /api/admin/monthly-stats/month-entry`
- `PATCH /api/admin/monthly-stats/{stat_id}`

### 13.6 Uploads

- `GET /api/uploads`
- `POST /api/uploads`
- `PATCH /api/uploads/{upload_id}`
- `DELETE /api/uploads/{upload_id}`

### 13.7 Metadata de filtros

- `GET /api/meta/options`

### 13.8 Analytics

- `GET /api/analytics/dashboard`
- `GET /api/analytics/entries-exits`
- `GET /api/analytics/productivity`
- `GET /api/analytics/stale`
- `GET /api/analytics/multi-sector`
- `GET /api/analytics/attributions`
- `GET /api/analytics/workload-balance`
- `GET /api/analytics/server-profile`
- `GET /api/analytics/lead-time`
- `GET /api/alerts/summary`


## 14. Regras importantes do endpoint de uploads

O endpoint `GET /api/uploads` hoje retorna payload paginado:

- `items`
- `page`
- `page_size`
- `total`
- `total_pages`

O frontend de uploads foi adaptado para aceitar tambem o formato antigo em lista simples, por compatibilidade.

O endpoint `PATCH /api/uploads/{upload_id}` hoje:

- impede conflito com outro `upload` do mesmo setor/data
- impede conflito com `processos` existentes do mesmo setor/data
- retorna mensagem mais clara em vez de erro generico de banco


## 15. Frontend

O frontend esta em `frontend/src`.

Tecnologias:

- React 18
- React Router 6
- Axios
- Recharts
- Vite
- XLSX

### 15.1 Bootstrap da aplicacao

Arquivo:

- `frontend/src/main.jsx`

A aplicacao e montada com:

- `BrowserRouter`
- `AuthProvider`
- `FiltersProvider`

### 15.2 Rotas

Arquivo:

- `frontend/src/App.jsx`

Rotas principais:

- `/login`
- `/executivo`
- `/`
- `/enviar-relatorio`
- `/entradas-saidas`
- `/produtividade`
- `/processos-parados`
- `/multiplos-setores`
- `/atribuicoes`
- `/servidores`
- `/busca`
- `/indicadores-mensais`
- `/usuarios-sei`
- `/administracao`
- `/minha-conta`
- `/documentacao`
- `/logout`

As rotas internas usam `ProtectedRoute`.


## 16. Sessao no frontend

Arquivos:

- `frontend/src/context/AuthContext.jsx`
- `frontend/src/components/ProtectedRoute.jsx`
- `frontend/src/api/client.js`

Fluxo:

1. login chama `POST /auth/login`
2. token vai para `localStorage` em `sei-bi-token`
3. usuario vai para `localStorage` em `sei-bi-user`
4. Axios injeta `Authorization: Bearer ...` automaticamente
5. no reload, o frontend tenta restaurar a sessao por `GET /auth/me`

Detalhe de performance:

- se ja existir usuario em cache no `localStorage`, o `loading` inicial nao bloqueia a interface desnecessariamente
- o timeout padrao das chamadas analiticas no frontend e de 90 segundos
- endpoints historicos mais pesados podem usar timeout especifico maior, como 120 segundos


## 17. Filtros globais no frontend

Arquivo:

- `frontend/src/context/FiltersContext.jsx`

Esse contexto:

- busca `/meta/options`
- guarda datas, setores, tipos e atribuicoes
- mantem filtros correntes
- converte filtros em query params

As paginas analiticas leem esse contexto para recarregar seus dados.


## 18. Layout e navegacao

Arquivos:

- `frontend/src/components/AppLayout.jsx`
- `frontend/src/components/Sidebar.jsx`
- `frontend/src/styles.css`

Comportamento:

- sidebar lateral com recolhimento
- rolagem propria da sidebar em telas menores
- topbar com identificacao do usuario logado, badge de frescor dos dados, busca global e sino de notificacoes
- barra de filtros visivel apenas em rotas analiticas


## 19. Paginas principais do frontend

### 19.1 Login

Arquivo:

- `frontend/src/pages/LoginPage.jsx`

Responsabilidade:

- formulario de email/senha
- chamada de login
- redirecionamento para dashboard

### 19.2 Central Executiva

Arquivo:

- `frontend/src/pages/ExecutivePage.jsx`

Consome:

- `/analytics/dashboard`
- `/analytics/entries-exits`
- `/analytics/stale`
- `/analytics/lead-time`
- `/health/data-freshness`

Entrega:

- prioridades do dia
- saude/frescor dos dados
- cards de KPI com sparklines
- tempo de permanencia com media, mediana, P90 e faixas
- ranking de lead time por setor
- carregamento escalonado para evitar que endpoints pesados derrubem a tela inteira

### 19.3 Dashboard

Arquivo:

- `frontend/src/pages/DashboardPage.jsx`

Consome:

- `/analytics/dashboard`

Entrega:

- KPIs gerais
- distribuicoes
- ranking de atribuicoes
- evolucao diaria

### 19.4 Entradas e saidas

Arquivo:

- `frontend/src/pages/FlowPage.jsx`

Consome:

- `/analytics/entries-exits`

### 19.5 Produtividade

Arquivo:

- `frontend/src/pages/ProductivityPage.jsx`

Consome:

- `/analytics/productivity`

Observacao:

- nomes longos de atribuicao sao abreviados para iniciais nos graficos
- o nome completo continua acessivel por hover

### 19.6 Processos parados

Arquivo:

- `frontend/src/pages/StaleProcessesPage.jsx`

Consome:

- `/analytics/stale`

Observacao:

- a tabela de processos criticos esta paginada em 50 itens por pagina

### 19.7 Processos em multiplos setores

Arquivo:

- `frontend/src/pages/MultiSectorPage.jsx`

Consome:

- `/analytics/multi-sector`

### 19.8 Enviar relatorio

Arquivo:

- `frontend/src/pages/UploadPage.jsx`

Consome:

- `GET /uploads`
- `POST /uploads`
- `PATCH /uploads/{id}`
- `DELETE /uploads/{id}`

Recursos:

- formulario de upload
- historico recente paginado
- edicao de data do snapshot
- exclusao de snapshot

### 19.9 Administracao

Arquivo:

- `frontend/src/pages/AdminPage.jsx`

Consome:

- `GET /admin/users`
- `POST /admin/users`
- `DELETE /admin/users/{id}`
- `GET /uploads`

### 19.10 Usuarios SEI

Arquivo:

- `frontend/src/pages/SeiUsersPage.jsx`

Consome:

- `GET /admin/sei-users`
- `POST /admin/sei-users`
- `POST /admin/sei-users/import-rows`
- `DELETE /admin/sei-users/{id}`

### 19.11 Indicadores mensais

Arquivo:

- `frontend/src/pages/MonthlyStatsPage.jsx`

Consome:

- `GET /monthly-stats`
- `POST /admin/monthly-stats/import`
- `POST /admin/monthly-stats/month-entry`
- `PATCH /admin/monthly-stats/{id}`


## 20. Graficos

Arquivos:

- `frontend/src/charts/BarChartCard.jsx`
- `frontend/src/charts/LineChartCard.jsx`
- `frontend/src/charts/PieChartCard.jsx`

Baseados em Recharts.

Existem customizacoes importantes:

- abreviacao de nomes em alguns eixos/legendas usando `frontend/src/utils/userNameFormatter.js`
- tooltip e hover preservam a identificacao completa quando aplicavel


## 21. Configuracao de ambiente

### 21.1 Backend

Arquivo:

- `.env.example`

Variaveis relevantes:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `DEFAULT_ADMIN_NAME`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`
- `AUTO_IMPORT_SAMPLE_DATA`
- `SQLALCHEMY_POOL_RECYCLE`
- `ANALYTICS_LOOKBACK_DAYS`
- `DISABLE_STARTUP_PRECOMPUTE`
- `PRECOMPUTE_HEAVY_ANALYTICS`
- `PRECOMPUTE_COOLDOWN_SECS`
- `APP_TIMEZONE`
- `DATA_FRESHNESS_OK_MAX_DAYS`
- `DATA_FRESHNESS_CRITICAL_DAYS`
- `DATA_QUALITY_DROP_RATIO`

Observacao:

- o comentario do arquivo menciona uso com Postgres externo/Aiven

### 21.2 Frontend

Arquivo:

- `frontend/.env.example`

Variavel:

- `VITE_API_URL=http://localhost:8000/api`


## 22. Desenvolvimento local

### 22.1 Backend

Com ambiente virtual:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 22.2 Frontend

```bash
cd frontend
npm install
npm run dev
```

### 22.3 Proxy local do Vite

Arquivo:

- `frontend/vite.config.js`

No desenvolvimento, `/api` e proxyado para:

- `http://127.0.0.1:8000`

ou para o host definido em `VITE_PROXY_TARGET`.


## 23. Deploy no Render

Arquivo:

- `render.yaml`

O blueprint versionado descreve:

- um web service Python
- plano gratuito
- regiao `virginia`
- healthcheck em `/api/health`
- variaveis de ambiente da API

Variaveis declaradas:

- `DATABASE_URL`
- `PYTHON_VERSION`
- `JWT_SECRET_KEY`
- `API_UPLOAD_KEY`
- `DEFAULT_ADMIN_NAME`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ORIGINS`
- `AUTO_IMPORT_SAMPLE_DATA=false`
- `ANALYTICS_LOOKBACK_DAYS=120`
- `DISABLE_STARTUP_PRECOMPUTE=false`
- `PRECOMPUTE_HEAVY_ANALYTICS=false`
- `PRECOMPUTE_COOLDOWN_SECS=120`

Importante para manutencao:

- o banco de producao atual e externo ao Render
- `DATABASE_URL` deve apontar para o PostgreSQL da Aiven
- `DATABASE_URL`, `API_UPLOAD_KEY` e `DEFAULT_ADMIN_PASSWORD` usam `sync: false`, portanto precisam existir no painel do Render
- sempre validar no painel qual `DATABASE_URL` esta efetivamente em uso antes de qualquer migracao ou troca de banco


## 24. Deploy no Vercel

Arquivos:

- `vercel.json`
- `frontend/vercel.json`

O arquivo realmente relevante para a raiz do projeto e `vercel.json`.

Ele faz:

- define `buildCommand`
- define `outputDirectory`
- reescreve `/api/*` para a API no Render
- reescreve todas as demais rotas para `index.html`

Isso transforma o frontend em SPA com backend proxado sem CORS adicional no navegador.

Atencao operacional:

- o `vercel.json` versionado usa `buildCommand: "npm run build"`
- o `package.json` da raiz nao define script `build`
- o repositorio da raiz define `build:frontend`

Entao existem duas possibilidades:

- ou o painel da Vercel esta sobrescrevendo o comando de build
- ou existe outra configuracao operacional fora do repositorio

Isso deve ser validado pelo proximo mantenedor no painel da Vercel.


## 25. Docker

Arquivo:

- `Dockerfile`

Ele sobe apenas o backend:

- imagem base `python:3.12-slim`
- instala dependencias de `requirements.txt`
- copia `backend/`
- inicia `uvicorn backend.main:app`

Isso serve como alternativa de execucao containerizada da API.


## 26. Scripts auxiliares

### 26.1 Migracao de banco

Arquivo:

- `scripts/migrate_postgres.py`

Objetivo:

- copiar dados entre bancos compativeis via SQLAlchemy

Casos de uso:

- SQLite local -> Postgres
- banco antigo -> Aiven
- banco Render -> banco externo

### 26.2 Publicacao automatizada no GitHub

Arquivo:

- `scripts/publish-github.ps1`

Objetivo:

- publicar arquivos do projeto diretamente via API do GitHub

### 26.3 Automacoes do GitHub Actions

Arquivos principais:

- `.github/workflows/daily-upload.yml`
- `.github/workflows/daily-report.yml`
- `.github/workflows/weekly-report.yml`
- `.github/workflows/critical-alerts.yml`
- `.github/workflows/keep-alive.yml`

Regras atuais:

- `daily-upload` roda de segunda a sexta as 19:00 BRT
- `daily-report` roda de segunda a sexta as 19:30 BRT
- antes de enviar o e-mail diario, `daily-report` executa `scripts/check_daily_upload_success.py`
- se o upload automatico do dia nao concluiu com sucesso, o e-mail diario nao e enviado
- `weekly-report` roda sexta as 20:00 BRT
- `critical-alerts` roda sexta as 21:00 BRT e evita envio quando nao ha criticos
- `keep-alive` chama `/api/ping`, endpoint leve sem banco


## 27. Pontos criticos para manutencao

### 27.1 Migracoes de schema

O projeto usa Alembic para migracoes versionadas.

Na inicializacao da API, o backend executa `alembic upgrade head`. Em bancos existentes sem historico Alembic, o sistema faz auto-stamp do baseline antes de aplicar migracoes novas.

Mudancas estruturais ainda precisam ser bem pensadas para nao quebrar bases ja existentes.

### 27.2 Coerencia entre repositorio e ambiente

O repositorio declara a API no Render, mas o banco real fica fora do Render.
O mantenedor deve validar:

- `DATABASE_URL` no Render
- credenciais e host do banco Aiven
- comando de build no Vercel
- variaveis de ambiente do Render, Vercel e GitHub Actions

### 27.3 Performance

Os calculos usam Pandas e carregam historico para inferencia de spans e comparacoes.
Se o volume crescer muito, os gargalos provaveis serao:

- startup da API
- analises historicas
- consultas sem agregacao precomputada

### 27.4 Cache analitico

O cache e em memoria do processo.
Nao e compartilhado entre instancias.

### 27.5 Regras de upload

O modelo de negocio e snapshot diario.
Se no futuro houver necessidade de trilha transacional real, a arquitetura analitica tera de mudar.


## 28. Resumo operacional do ambiente online

Configuracao descrita pelo codigo e pela documentacao do projeto:

- GitHub hospeda o codigo
- Render hospeda a API FastAPI
- Render fornece variaveis de ambiente da API
- Aiven hospeda o banco PostgreSQL de producao
- Vercel hospeda o frontend React
- Vercel faz rewrite de `/api` para o Render
- o banco em runtime e o que estiver em `DATABASE_URL`

Na operacao atual:

- o banco principal e Aiven for PostgreSQL
- o Neon foi substituido apos limite de transferencia mensal
- a aplicacao nao depende de codigo especifico da Aiven; a troca e feita pela `DATABASE_URL`


## 29. Estrutura completa do projeto

```text
bi-copag/
├── .github/
│   └── workflows/
│       ├── critical-alerts.yml
│       ├── daily-report.yml
│       ├── daily-upload.yml
│       ├── keep-alive.yml
│       └── weekly-report.yml
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 0001_baseline.py
│       └── 0002_add_audit_logs.py
├── .dockerignore
├── .env.example
├── .env.local.example
├── .gitignore
├── Dockerfile
├── README.md
├── package.json
├── render.yaml
├── requirements.txt
├── vercel.json
├── docs/
│   ├── AMBIENTE_LOCAL.md
│   ├── DEPLOY-MINIMO.md
│   ├── HANDOFF.md
│   └── SEI_ANALYTICS_APRESENTACAO_EQUIPE.md
├── backend/
│   ├── __init__.py
│   ├── analytics.py
│   ├── auth.py
│   ├── csv_importer.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   ├── monthly_stats.py
│   ├── schemas.py
│   └── sei_users.py
├── frontend/
│   ├── .env.example
│   ├── .env.local.example
│   ├── index.html
│   ├── package.json
│   ├── vercel.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── styles.css
│       ├── api/
│       │   └── client.js
│       ├── charts/
│       │   ├── BarChartCard.jsx
│       │   ├── LineChartCard.jsx
│       │   └── PieChartCard.jsx
│       ├── components/
│       │   ├── AppLayout.jsx
│       │   ├── ChartPanel.jsx
│       │   ├── DataFreshnessBadge.jsx
│       │   ├── DataTable.jsx
│       │   ├── ErrorBlock.jsx
│       │   ├── FilterBar.jsx
│       │   ├── LoadingBlock.jsx
│       │   ├── NotificationBell.jsx
│       │   ├── ProtectedRoute.jsx
│       │   ├── Sidebar.jsx
│       │   ├── SparklineCard.jsx
│       │   └── StatCard.jsx
│       ├── context/
│       │   ├── AuthContext.jsx
│       │   └── FiltersContext.jsx
│       ├── hooks/
│       │   └── useAnalyticsData.js
│       ├── pages/
│       │   ├── AccountPage.jsx
│       │   ├── AdminPage.jsx
│       │   ├── AttributionsPage.jsx
│       │   ├── DashboardPage.jsx
│       │   ├── DocumentacaoPage.css
│       │   ├── DocumentacaoPage.jsx
│       │   ├── ExecutivePage.jsx
│       │   ├── FlowPage.jsx
│       │   ├── LoginPage.jsx
│       │   ├── LogoutPage.jsx
│       │   ├── MonthlyStatsPage.jsx
│       │   ├── MultiSectorPage.jsx
│       │   ├── ProcessSearchPage.jsx
│       │   ├── ProductivityPage.jsx
│       │   ├── SeiUsersPage.jsx
│       │   ├── ServidoresPage.jsx
│       │   ├── StaleProcessesPage.jsx
│       │   ├── UploadPage.jsx
│       │   └── documentacao/
│       └── utils/
│           ├── attributionsExcel.js
│           ├── attributionsPdf.js
│           ├── uploadsPayload.js
│           └── userNameFormatter.js
└── scripts/
    ├── alerts_email.py
    ├── check_daily_upload_success.py
    ├── daily_report.py
    ├── dev_backend.sh
    ├── dev_frontend.sh
    ├── migrate_postgres.py
    ├── publish-github.ps1
    ├── sei_uploader.py
    └── weekly_report.py
```


## 30. Recomendacoes para a proxima manutencao

Recomendacoes praticas:

1. validar no painel do Render qual `DATABASE_URL` esta realmente em uso
2. validar no painel da Vercel qual comando de build esta configurado
3. confirmar periodicamente os limites e consumo do banco Aiven
4. manter migracoes Alembic para qualquer alteracao estrutural de banco
5. manter `PRECOMPUTE_HEAVY_ANALYTICS=false` salvo necessidade operacional clara
6. considerar materializacao ou precomputacao seletiva se o volume historico crescer muito
7. manter testes locais cuidadosos em upload, filtros, analytics e administracao, porque sao os fluxos mais sensiveis do produto
