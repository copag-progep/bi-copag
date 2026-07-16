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

1. o usuario acessa `https://analyticsei.vercel.app`
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
- `can_upload`
- `created_at`

Observacao:

- `is_admin=True` concede acesso total.
- `can_upload=True` autoriza usuario comum a acessar a tela Enviar Relatorio e executar upload manual, sempre respeitando os setores liberados.

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

### 6.6 Tabela `sei_user_aliases`

Responsabilidade:

- consolidar nomes historicos ou alternativos de um mesmo usuario SEI

Campos principais:

- `sei_user_id`
- `alias`
- `alias_key`
- `created_at`

### 6.7 Tabela `user_sector_access`

Responsabilidade:

- controlar quais setores cada usuario comum pode visualizar

Campos principais:

- `user_id`
- `setor`
- `created_at`

Regra:

- administradores ignoram essa tabela e veem tudo
- usuarios comuns veem apenas os setores cadastrados
- usuario comum sem setor cadastrado nao deve receber dados analiticos

### 6.8 Tabela `sei_user_setor`

Responsabilidade:

- vincular usuarios SEI/atribuicoes aos setores onde atuam

Campos principais:

- `sei_user_id`
- `setor`

Uso:

- limita os filtros de Atribuicao e Servidor para usuarios restritos
- permite vinculo com mais de um setor
- pode ser preenchida manualmente ou por inferencia a partir dos processos historicos

### 6.9 Tabela `process_type_weights`

Responsabilidade:

- configurar pesos por tipo de processo no Score de Risco

Campos principais:

- `tipo`
- `peso`
- `categoria`
- `justificativa`
- `ativo`

Regra:

- peso entre `0.80` e `1.50`
- tipo sem configuracao usa peso neutro `1.00`

### 6.10 Tabela `pauta_sessoes`

Responsabilidade:

- representar uma sessao semanal da Pauta Prioritaria

Campos principais:

- `titulo`
- `data_inicio`
- `data_fim`
- `data_reuniao`
- `observacoes`
- `ativa`
- `criado_por`
- `created_at`
- `updated_at`

Regra:

- sessoes ativas aparecem na tela principal da pauta
- `data_inicio` representa o inicio do acompanhamento
- `data_reuniao` representa a reuniao prevista
- `data_fim` representa o prazo da pauta
- administradores podem editar titulo, datas e observacoes via `PATCH /api/pauta/sessoes/{id}`
- editar uma sessao registra auditoria `pauta.sessao_editada` com valores anteriores e novos
- encerrar uma sessao altera `ativa=false` e registra auditoria `pauta.sessao_encerrada`

### 6.11 Tabela `pauta_itens`

Responsabilidade:

- armazenar os processos selecionados para acompanhamento em cada sessao da Pauta Prioritaria

Campos principais:

- `sessao_id`
- `protocolo`
- `setor`
- `entrada_setor`
- `data_referencia`
- `ultima_presenca`
- `atribuicao`
- `tipo`
- `dias_no_setor`
- `score_risco`
- `nivel_risco`
- `assigned_to`
- `assigned_by`
- `status`
- `nota_admin`
- `nota_responsavel`
- `data_status`
- `resolucao_automatica`

Restricao importante:

- unicidade por `sessao_id + protocolo + setor + entrada_setor`

Status:

- `pendente`: item incluido, aguardando ciencia do responsavel
- `em_acompanhamento`: responsavel confirmou ciencia
- `saiu_do_setor`: resolvido automaticamente porque o protocolo deixou de aparecer no snapshot do setor
- `resolvido_manual`: override excepcional feito por administrador
- `arquivado`: item removido da vista ativa sem apagar historico

Regra de integridade:

- responsaveis nao podem declarar resolucao
- a resolucao operacional padrao vem do upload: se o processo sair da lista do setor no snapshot mais recente valido, o item muda automaticamente para `saiu_do_setor`

## 6A. Controle de acesso por divisao

O controle de acesso tem duas camadas diferentes:

1. Usuario da aplicacao (`users`): pessoa que faz login no AnalyticSEI.
2. Usuario SEI (`sei_users`): servidor/atribuicao que aparece nos processos importados do SEI.

### Usuarios da aplicacao

- Administrador ve todos os setores e acessa telas administrativas.
- Usuario comum ve apenas os setores cadastrados em `user_sector_access`.
- Usuario comum sem setores cadastrados nao deve receber dados analiticos.
- `can_upload=True` libera upload manual, mas apenas para os setores permitidos.

Esse recorte e aplicado no backend. Portanto, nao depende apenas de esconder filtros ou menus no frontend.

Pontos de enforcement importantes:

- `_base_query()` aplica `setores_permitidos` antes dos demais filtros.
- `_effective_filters()` preserva o escopo via `dataclasses.replace()`.
- `_available_dates()` usa a query base com escopo, evitando escolher data de referencia de setor nao autorizado.
- `get_filter_options()` recebe o escopo do usuario e retorna datas, setores, tipos e atribuicoes apenas dos setores permitidos.
- `multi-sector` remove apenas o filtro de setor selecionado, mas preserva `setores_permitidos`.

### Usuarios SEI

`sei_user_setor` informa em quais setores cada atribuicao atua. Essa tabela e usada para montar listas de filtro:

- filtro Atribuicao no FilterBar
- filtro Servidor na pagina Servidores

Um usuario SEI pode estar vinculado a mais de um setor. A pagina Usuarios SEI permite editar manualmente esses vinculos ou inferi-los a partir dos processos historicos.

### Cache e frescor dos dados

- O cache analitico do backend inclui o escopo de setores na chave.
- O cache analitico do backend e LRU, com limite por quantidade de entradas, tamanho total e tamanho maximo por payload.
- O frontend usa prefixo versionado de cache em `sessionStorage`.
- Administradores podem reaproveitar cache persistente por usuario.
- Usuarios restritos aguardam resposta atual do servidor; isso evita exibir dado antigo apos mudanca de permissao.
- Logout, login e sessao invalida limpam o cache local.
- O badge de frescor considera apenas os setores visiveis ao usuario logado.


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

No frontend, `/multiplos-setores` permite exportar a lista visivel em Excel e PDF:

- `frontend/src/utils/multiSectorExcel.js`
- `frontend/src/utils/multiSectorPdf.js`

As exportacoes respeitam os filtros globais ja aplicados ao endpoint e a busca local por protocolo. O PDF usa `jsPDF + jspdf-autotable` com identidade visual AnalyticSEI/PROGEP/UFC; o Excel usa SheetJS.

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

### 11.10 Forecast / tendencias estimadas

`get_forecast_data()` calcula tendencias estimadas para apoiar decisao gerencial na Central Executiva.

Escopo atual:

- projecao de estoque ativo para 15 e 30 dias
- tendencia de saldo por setor
- estimativa de processos que podem cruzar 30 dias em ate 15 dias

Regras metodologicas:

- usa regressao linear simples sobre snapshots recentes
- nao usa bibliotecas estatisticas complexas nem machine learning
- os valores sao arredondados para evitar falsa precisao
- a linguagem de exibicao deve ser cautelosa: "se o ritmo atual se mantiver"
- a estimativa de criticos considera presencas consecutivas ate o snapshot atual, evitando contar processos antigos que ja sairam

Performance:

- o endpoint e cacheado como os demais analytics
- nao entra no `precompute_analytics()`
- no frontend, carrega depois dos blocos principais da Central Executiva para reduzir concorrencia de consultas pesadas

### 11.11 Score de Risco

`get_risk_scores()` calcula uma prioridade de atencao por processo ativo.

O score combina:

- tempo absoluto no setor
- tempo relativo ao P90 historico
- ausencia de atribuicao
- presenca em multiplos setores
- multiplicador de tendencia do setor

Regras metodologicas:

- o score e sobre o processo, nao sobre o servidor atribuido
- o P90 usa fallback setor -> tipo -> global
- o P90 exige amostra minima configuravel por `RISK_MIN_LT_SAMPLE`
- existe piso tecnico `RISK_MIN_P90_DAYS` para evitar que historicos muito curtos, como P90 de 1 dia, superdimensionem o risco relativo
- pesos e thresholds sao configuraveis por variaveis `RISK_WEIGHT_*`, `RISK_TREND_*` e `RISK_*_THRESHOLD`
- o endpoint e sob demanda e so entra em precompute se `PRECOMPUTE_HEAVY_ANALYTICS=true`

### 11.12 Pauta Prioritaria

Modulo de gestao ativa que transforma o diagnostico do Score de Risco em acompanhamento semanal.

Componentes principais:

- sessoes semanais em `pauta_sessoes`
- itens de pauta em `pauta_itens`
- atribuicao a usuarios da plataforma com acesso ao setor do processo
- notas da gestao (`nota_admin`) e notas do responsavel (`nota_responsavel`)
- cronograma com inicio, reuniao e prazo da pauta (`data_fim`)
- situacao derivada da sessao: `a_iniciar`, `em_andamento` ou `encerrada`
- editor inline de titulo, datas e observacoes para administradores
- barra de progresso temporal e progresso de resolucao da sessao
- integracao com `/risco` e `/atribuicoes` pelo botao `+ Pauta`
- sino de notificacoes mostrando tambem itens pendentes da pauta
- exportacao PDF da pauta de reuniao
- metricas administrativas em `/api/pauta/metricas`

Fluxo operacional:

1. Administrador cria uma sessao semanal.
2. Administrador define inicio, data de reuniao e prazo da pauta.
3. Administrador adiciona processos criticos a partir do Score de Risco, da tela Atribuicoes ou do modal em lote da propria pauta.
4. Administrador atribui responsavel e registra uma orientacao.
5. Responsavel confirma ciencia e pode atualizar sua nota.
6. Apos cada upload valido do setor, `_check_pauta_resolution()` verifica se o protocolo ainda aparece no snapshot.
7. Se o protocolo nao aparece mais, o item muda para `saiu_do_setor` com `resolucao_automatica=True`.

Regras de permissao:

- responsavel comum so pode editar `nota_responsavel`
- responsavel comum so pode mudar `pendente -> em_acompanhamento`
- responsavel comum nao pode marcar resolucao manual
- administrador pode forcar `resolvido_manual` em casos excepcionais
- usuario comum so ve uma pauta quando ha itens atribuidos a ele e o setor do item ainda esta liberado em `user_sector_access`
- acesso direto a sessao sem itens visiveis retorna 404 para nao confirmar existencia de pauta alheia
- remover setor de usuario com itens ativos na pauta e bloqueado com 409 ate reatribuicao

Fechamento de ciclo:

- o administrador pode gerar PDF da sessao para reuniao
- PDF inclui periodo, reuniao, prazo da pauta, resumo de status e notas da gestao
- pendencias podem ser copiadas para nova sessao
- se a sessao ainda esta `a_iniciar` ou `em_andamento`, `copy-pending` encerra a origem e copia na mesma transacao
- se a sessao ja esta encerrada por prazo, a UI permite copiar as pendencias para nova sessao, preservando o historico
- encerrar sessao registra auditoria `pauta.sessao_encerrada`
- editar titulo/datas/observacoes registra auditoria `pauta.sessao_editada`

Regra de atribuicao atual na pauta:

- a coluna de atribuicao da pauta mostra a atribuicao atual no SEI quando o processo ainda esta na mesma passagem continua no setor
- a passagem e identificada por protocolo, setor e `entrada_setor`
- se o processo saiu e voltou depois ao mesmo setor, o item antigo usa fallback historico e nao recebe a atribuicao da nova passagem


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
- `GET /api/admin/users/{user_id}/sectors`
- `PUT /api/admin/users/{user_id}/sectors`
- `PATCH /api/admin/users/{user_id}/permissions`

### 13.4 Usuarios SEI

- `GET /api/admin/sei-users`
- `POST /api/admin/sei-users`
- `POST /api/admin/sei-users/import`
- `POST /api/admin/sei-users/import-rows`
- `DELETE /api/admin/sei-users/{sei_user_id}`
- `GET /api/admin/sei-users/{sei_user_id}/sectors`
- `PUT /api/admin/sei-users/{sei_user_id}/sectors`
- `POST /api/admin/sei-users/infer-sectors`

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

Observacao:

- para usuarios restritos, retorna apenas datas, setores, tipos e atribuicoes dos setores permitidos
- atribuicoes e servidores sao filtrados pelos vinculos de `sei_user_setor`
- antes de qualquer vinculo explicito, ha fallback temporario por dados historicos para evitar tela vazia durante a configuracao inicial

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
- `GET /api/analytics/forecast`
- `GET /api/analytics/risk-score`
- `GET /api/alerts/summary`

### 13.9 Pauta Prioritaria

- `GET /api/pauta/sessoes`
- `POST /api/pauta/sessoes`
- `GET /api/pauta/sessoes/{sessao_id}`
- `PATCH /api/pauta/sessoes/{sessao_id}`
- `POST /api/pauta/sessoes/{sessao_id}/itens`
- `POST /api/pauta/sessoes/{sessao_id}/itens/bulk`
- `PATCH /api/pauta/itens/{item_id}`
- `DELETE /api/pauta/itens/{item_id}`
- `GET /api/pauta/minha`
- `POST /api/pauta/sessoes/{sessao_id}/copy-pending`
- `GET /api/pauta/metricas`

Observacoes:

- `PATCH /api/pauta/itens/{item_id}` limita usuario comum a confirmar ciencia e editar sua nota
- `PATCH /api/pauta/sessoes/{sessao_id}` edita titulo, datas e observacoes com `exclude_unset`, valida `data_inicio <= data_fim` e registra auditoria `pauta.sessao_editada`
- `PATCH /api/pauta/sessoes/{sessao_id}` registra auditoria quando encerra sessao (`ativa=false`)
- `POST /api/pauta/sessoes/{sessao_id}/copy-pending` valida `data_inicio <= data_fim`, copia itens `pendente`/`em_acompanhamento` e encerra a origem quando ela ainda esta operavel
- `GET /api/pauta/metricas` e admin-only


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
- `/risco`
- `/pauta`
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
- o cache analitico em `sessionStorage` e isolado por usuario logado, evitando reaproveitar dados de outro perfil apos logout/login
- usuarios restritos nao leem cache persistente antes de receber a resposta atual do servidor, evitando exposicao stale apos mudanca de permissao
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
- auto-seleciona o unico setor disponivel quando o usuario tem acesso a apenas uma divisao

As paginas analiticas leem esse contexto para recarregar seus dados.

Para usuarios restritos, a lista de setores, atribuicoes e servidores ja chega filtrada pelo backend. O frontend apenas reflete esse escopo.


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
- item Enviar Relatorio fica oculto para usuario comum sem permissao de upload


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
- `/analytics/forecast`
- `/health/data-freshness`

Entrega:

- prioridades do dia
- saude/frescor dos dados
- cards de KPI com sparklines
- tempo de permanencia com media, mediana, P90 e faixas
- ranking de lead time por setor
- tendencias estimadas de estoque ativo, saldo por setor e processos em envelhecimento
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

Regra importante:

- a deteccao de multiplos setores usa o snapshot global para saber se o protocolo aparece em mais de uma divisao
- depois disso, a resposta e filtrada para mostrar apenas ocorrencias que envolvem setores visiveis ao usuario logado
- isso permite que um usuario restrito saiba que um processo do seu setor tambem aparece em outro setor, sem receber a carteira completa da outra divisao

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

Restricoes:

- administradores podem enviar qualquer setor
- usuarios comuns precisam de `can_upload=True`
- usuarios comuns so podem enviar CSV de setores liberados em `user_sector_access`
- historico de uploads tambem respeita o escopo de setores do usuario

### 19.9 Administracao

Arquivo:

- `frontend/src/pages/AdminPage.jsx`

Consome:

- `GET /admin/users`
- `POST /admin/users`
- `DELETE /admin/users/{id}`
- `GET /admin/users/{id}/sectors`
- `PUT /admin/users/{id}/sectors`
- `PATCH /admin/users/{id}/permissions`
- `GET /uploads`

Recursos:

- abas de Acessos, Uploads, Auditoria e Score de Risco
- configuracao de divisoes visiveis por usuario
- permissao individual para envio de relatorios
- pesos por tipo de processo usados no Score de Risco

### 19.10 Usuarios SEI

Arquivo:

- `frontend/src/pages/SeiUsersPage.jsx`

Consome:

- `GET /admin/sei-users`
- `POST /admin/sei-users`
- `POST /admin/sei-users/import-rows`
- `DELETE /admin/sei-users/{id}`
- `GET /admin/sei-users/{id}/sectors`
- `PUT /admin/sei-users/{id}/sectors`
- `POST /admin/sei-users/infer-sectors`

Recursos:

- DE-PARA de nomes e usuarios SEI
- aliases historicos para consolidar mudancas de nome
- edicao dos dados cadastrais
- vinculo de cada usuario SEI a um ou mais setores
- inferencia automatica de setores a partir dos processos historicos

### 19.11 Indicadores mensais

Arquivo:

- `frontend/src/pages/MonthlyStatsPage.jsx`

Consome:

- `GET /monthly-stats`
- `POST /admin/monthly-stats/import`
- `POST /admin/monthly-stats/month-entry`
- `PATCH /admin/monthly-stats/{id}`

Regra:

- usuarios restritos veem apenas os setores liberados

### 19.12 Score de Risco

Arquivo:

- `frontend/src/pages/RiscoPage.jsx`

Consome:

- `/analytics/risk-score`

Entrega:

- ranking de processos por score
- filtros por nivel de risco
- indicadores de processos criticos, elevados e moderados
- linha expansivel com contribuicao de cada fator
- aviso explicito de que o score e do processo, nao do servidor

### 19.13 Pauta Prioritaria

Arquivo:

- `frontend/src/pages/PautaPage.jsx`
- `frontend/src/components/AddToPautaMiniModal.jsx`
- `frontend/src/utils/generatePautaPdf.js`

Consome:

- `/pauta/sessoes`
- `/pauta/sessoes/{id}`
- `/pauta/sessoes/{id}/itens`
- `/pauta/sessoes/{id}/itens/bulk`
- `/pauta/itens/{id}`
- `/pauta/sessoes/{id}/copy-pending`
- `/pauta/metricas`
- `/admin/users`
- `/analytics/risk-score`

Entrega:

- criacao de sessoes semanais
- cronograma visivel para todos os perfis: inicio, reuniao e prazo da pauta
- editor inline de titulo, datas e observacoes para administradores
- auditoria `pauta.sessao_editada` ao alterar sessao
- inclusao individual de processos pelo modal `+ Pauta`
- inclusao em lote a partir do Score de Risco
- atribuicao de responsaveis com acesso ao setor
- nota da gestao e nota do responsavel
- confirmacao de ciencia pelo responsavel
- resolucao automatica quando o processo sai do snapshot do setor
- override manual de resolucao apenas para admin
- progresso temporal e progresso de resolucao da sessao
- copia de pendencias para nova sessao
- encerramento de sessao com auditoria
- exportacao PDF da pauta da reuniao
- metricas administrativas de eficiencia

### 19.14 Multiplos setores

Arquivo:

- `frontend/src/pages/MultiSectorPage.jsx`
- `frontend/src/utils/multiSectorExcel.js`
- `frontend/src/utils/multiSectorPdf.js`

Consome:

- `/analytics/multi-sector`

Entrega:

- cards de total, ocorrencias em 2 setores, ocorrencias em 3+ setores e setores envolvidos
- busca local por protocolo
- tabela com protocolo, setores, quantidade e data do relatorio
- exportacao Excel da lista visivel
- exportacao PDF da lista visivel com identidade visual AnalyticSEI/PROGEP/UFC


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
- `RISK_WEIGHT_ABS`
- `RISK_WEIGHT_REL`
- `RISK_WEIGHT_UNASSIGNED`
- `RISK_WEIGHT_MULTI_SECTOR`
- `RISK_TREND_UP`
- `RISK_TREND_STABLE`
- `RISK_TREND_DOWN`
- `RISK_CRITICAL_THRESHOLD`
- `RISK_HIGH_THRESHOLD`
- `RISK_MODERATE_THRESHOLD`
- `RISK_MIN_LT_SAMPLE`
- `RISK_MIN_P90_DAYS`

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
	│           ├── generatePautaPdf.js
	│           ├── multiSectorExcel.js
	│           ├── multiSectorPdf.js
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
