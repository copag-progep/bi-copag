# HANDOFF - SEI Analytics

## 1. Objetivo do projeto

Este projeto e o SEI Analytics, uma plataforma de Business Intelligence para acompanhamento de processos administrativos exportados do SEI em CSV.

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
- se o ambiente produtivo estiver hoje no Neon, isso acontece porque o `DATABASE_URL` configurado no Render aponta para o Neon
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

### 5.2 Evolucao de schema

Nao existe Alembic ou outro framework formal de migrations.

Em vez disso, o projeto usa:

- `Base.metadata.create_all(...)`
- `ensure_schema_updates()`
- `ensure_indexes()`

Hoje, `ensure_schema_updates()` garante pelo menos a existencia de:

- coluna `atribuicao_normalizada` em `processos`

Isso significa que a evolucao de schema e pragmatica, mas menos formal.
Para manutencao futura, se o projeto crescer muito, vale considerar Alembic.


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
- `/`
- `/enviar-relatorio`
- `/entradas-saidas`
- `/produtividade`
- `/processos-parados`
- `/multiplos-setores`
- `/indicadores-mensais`
- `/usuarios-sei`
- `/administracao`
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
- topbar com identificacao do usuario logado
- barra de filtros visivel apenas em rotas analiticas


## 19. Paginas principais do frontend

### 19.1 Login

Arquivo:

- `frontend/src/pages/LoginPage.jsx`

Responsabilidade:

- formulario de email/senha
- chamada de login
- redirecionamento para dashboard

### 19.2 Dashboard

Arquivo:

- `frontend/src/pages/DashboardPage.jsx`

Consome:

- `/analytics/dashboard`

Entrega:

- KPIs gerais
- distribuicoes
- ranking de atribuicoes
- evolucao diaria

### 19.3 Entradas e saidas

Arquivo:

- `frontend/src/pages/FlowPage.jsx`

Consome:

- `/analytics/entries-exits`

### 19.4 Produtividade

Arquivo:

- `frontend/src/pages/ProductivityPage.jsx`

Consome:

- `/analytics/productivity`

Observacao:

- nomes longos de atribuicao sao abreviados para iniciais nos graficos
- o nome completo continua acessivel por hover

### 19.5 Processos parados

Arquivo:

- `frontend/src/pages/StaleProcessesPage.jsx`

Consome:

- `/analytics/stale`

Observacao:

- a tabela de processos criticos esta paginada em 50 itens por pagina

### 19.6 Processos em multiplos setores

Arquivo:

- `frontend/src/pages/MultiSectorPage.jsx`

Consome:

- `/analytics/multi-sector`

### 19.7 Enviar relatorio

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

### 19.8 Administracao

Arquivo:

- `frontend/src/pages/AdminPage.jsx`

Consome:

- `GET /admin/users`
- `POST /admin/users`
- `DELETE /admin/users/{id}`
- `GET /uploads`

### 19.9 Usuarios SEI

Arquivo:

- `frontend/src/pages/SeiUsersPage.jsx`

Consome:

- `GET /admin/sei-users`
- `POST /admin/sei-users`
- `POST /admin/sei-users/import-rows`
- `DELETE /admin/sei-users/{id}`

### 19.10 Indicadores mensais

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

Observacao:

- o comentario do arquivo ja menciona uso com Postgres externo/Neon

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
- um banco Postgres do proprio Render
- injecao automatica de `DATABASE_URL` a partir desse banco

Variaveis declaradas:

- `DATABASE_URL`
- `PYTHON_VERSION`
- `JWT_SECRET_KEY`
- `DEFAULT_ADMIN_NAME`
- `DEFAULT_ADMIN_EMAIL`
- `DEFAULT_ADMIN_PASSWORD`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `AUTO_IMPORT_SAMPLE_DATA=false`

Importante para manutencao:

- o `render.yaml` versionado ainda descreve banco do Render
- se a producao atual usa Neon, isso deve estar ajustado no painel do Render ou em outra configuracao fora do repositorio
- sempre validar no painel qual `DATABASE_URL` esta efetivamente em uso


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
- banco antigo -> Neon
- banco Render -> banco externo

### 26.2 Publicacao automatizada no GitHub

Arquivo:

- `scripts/publish-github.ps1`

Objetivo:

- publicar arquivos do projeto diretamente via API do GitHub


## 27. Pontos criticos para manutencao

### 27.1 Migracoes de schema

Hoje nao ha Alembic.
Mudancas estruturais precisam ser bem pensadas para nao quebrar bases ja existentes.

### 27.2 Coerencia entre repositorio e ambiente

O repositrio sugere Render DB no `render.yaml`, mas o ambiente real pode estar em Neon.
O mantenedor deve validar:

- `DATABASE_URL` no Render
- comando de build no Vercel
- variaveis de ambiente de ambos

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
- Vercel hospeda o frontend React
- Vercel faz rewrite de `/api` para o Render
- o banco em runtime e o que estiver em `DATABASE_URL`

Se a operacao atual estiver em Neon:

- o Neon nao precisa aparecer explicitamente no codigo
- basta `DATABASE_URL` no Render apontar para o Neon


## 29. Estrutura completa do projeto

```text
bi-copag/
├── .dockerignore
├── .env.example
├── .gitignore
├── DEPLOY-MINIMO.md
├── Dockerfile
├── HANDOFF.md
├── README.md
├── package.json
├── render.yaml
├── requirements.txt
├── vercel.json
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
│       │   ├── DataTable.jsx
│       │   ├── FilterBar.jsx
│       │   ├── LoadingBlock.jsx
│       │   ├── ProtectedRoute.jsx
│       │   ├── Sidebar.jsx
│       │   └── StatCard.jsx
│       ├── context/
│       │   ├── AuthContext.jsx
│       │   └── FiltersContext.jsx
│       ├── pages/
│       │   ├── AdminPage.jsx
│       │   ├── DashboardPage.jsx
│       │   ├── FlowPage.jsx
│       │   ├── LoginPage.jsx
│       │   ├── LogoutPage.jsx
│       │   ├── MonthlyStatsPage.jsx
│       │   ├── MultiSectorPage.jsx
│       │   ├── ProductivityPage.jsx
│       │   ├── SeiUsersPage.jsx
│       │   ├── StaleProcessesPage.jsx
│       │   └── UploadPage.jsx
│       └── utils/
│           └── userNameFormatter.js
└── scripts/
    ├── migrate_postgres.py
    └── publish-github.ps1
```


## 30. Recomendacoes para a proxima manutencao

Recomendacoes praticas:

1. validar no painel do Render qual `DATABASE_URL` esta realmente em uso
2. validar no painel da Vercel qual comando de build esta configurado
3. documentar oficialmente se o banco de producao esta no Neon
4. considerar Alembic para migracoes futuras
5. considerar materializacao ou precomputacao se o volume historico crescer muito
6. manter testes manuais cuidadosos em upload, filtros, analytics e administracao, porque sao os fluxos mais sensiveis do produto
