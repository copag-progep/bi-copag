# Deploy com o minimo de cliques

Este projeto foi ajustado para um fluxo simples:

- backend no Render via `render.yaml`
- frontend no Vercel a partir da raiz do repositorio
- proxy do frontend para a API ja configurado em `vercel.json`

## Antes de subir para o GitHub

### Importante sobre os CSVs

Os arquivos `ListaProcessos_SEIPro_*.csv` e a pasta `SEI/` foram adicionados ao `.gitignore` para evitar publicar dados administrativos em um repositorio.

Se esses arquivos ja estiverem versionados no seu Git, remova-os antes de publicar o repositorio.

## Passo 1. Publicar no GitHub

Suba este projeto para um repositorio GitHub.

## Passo 2. Deploy do backend no Render

1. Entre em [Render Blueprints](https://dashboard.render.com/blueprints)
2. Clique em **New Blueprint**
3. Conecte o repositorio
4. Confirme o arquivo `render.yaml`
5. Quando o Render pedir segredos, preencha apenas:
   - `DEFAULT_ADMIN_PASSWORD`
6. Clique em **Deploy Blueprint**

O `render.yaml` cria/configura:

- 1 web service Python
- `DATABASE_URL` como variavel secreta para o banco externo
- `JWT_SECRET_KEY` gerado automaticamente

## Passo 3. Deploy do frontend no Vercel

1. Entre em [Vercel New Project](https://vercel.com/new)
2. Importe o mesmo repositorio
3. Clique em **Deploy**

Nao e necessario:

- escolher pasta `frontend`
- configurar comando de build
- configurar output directory
- configurar URL da API

Tudo isso ja foi preparado por `package.json` na raiz e `vercel.json`.

## Login inicial

- Email: `andersoncfs@ufc.br`
- Senha: a senha que voce informar no campo `DEFAULT_ADMIN_PASSWORD` do Render

## Banco de dados de producao

O banco de producao atual roda no **Aiven for PostgreSQL**, servico `bi-copag-db`, plano `Free-1-1gb`.

Para configurar ou recriar o ambiente, defina no Render:

- `DATABASE_URL`: Service URI do Aiven com `sslmode=require`
- `API_UPLOAD_KEY`: mesma chave usada pelos workflows do GitHub
- `DEFAULT_ADMIN_PASSWORD`: senha inicial para criacao do admin padrao
- `RUN_DB_MAINTENANCE_ON_STARTUP=false`: impede que migrations e criação de índices bloqueiem todo cold start. Ative temporariamente apenas para um deploy controlado com mudança de schema.
- `SQLALCHEMY_CONNECT_TIMEOUT=10`, `SQLALCHEMY_STATEMENT_TIMEOUT_MS=30000` e `SQLALCHEMY_LOCK_TIMEOUT_MS=5000`: fazem operações de banco falharem de forma explícita em vez de aguardarem indefinidamente.
- `DISABLE_STARTUP_PRECOMPUTE=true`: evita aquecer cache durante o boot em planos com pouca RAM.
- `DISABLE_POST_CHANGE_PRECOMPUTE=true`: evita precompute automatico apos uploads/alteracoes; o cache passa a ser populado sob demanda.
- `ANALYTICS_CACHE_MAX_ENTRIES`, `ANALYTICS_CACHE_MAX_TOTAL_MB`, `ANALYTICS_CACHE_MAX_ITEM_MB`: limites do cache LRU analitico.
- `ANALYTICS_BUILD_CONCURRENCY=1`: serializa builds analiticos pesados por processo.

O backend aceita qualquer PostgreSQL compativel via `DATABASE_URL`; localmente, se essa variavel nao existir, usa SQLite.

## Migrações e dados administrativos

Localmente, o backend executa `alembic upgrade head` na inicialização. No Render,
`RUN_DB_MAINTENANCE_ON_STARTUP=false` mantém essa manutenção fora dos cold starts.
Quando houver uma migration nova:

1. confirme que não há locks ou transações longas no PostgreSQL;
2. ative `RUN_DB_MAINTENANCE_ON_STARTUP=true`;
3. faça um deploy controlado e confirme no log `Database startup step completed: alembic_migrations`;
4. volte a variável para `false` e faça o deploy operacional.

Depois que uma migration já foi publicada em produção, não renomeie nem reutilize o mesmo `revision` em outro arquivo.

As migrations recentes criam estruturas administrativas importantes:

- `user_sector_access`: divisões que cada usuário comum pode visualizar.
- `can_upload` em `users`: permissão individual para envio manual de relatórios.
- `sei_user_setor`: vínculo entre usuários SEI/atribuições e setores.
- `process_type_weights`: pesos por tipo de processo no Score de Risco.
- `pauta_sessoes` e `pauta_itens`: sessões, cronogramas, responsáveis e processos acompanhados na Pauta Prioritária.

Após um deploy que crie `sei_user_setor`, entre como administrador em **Usuários SEI** e clique em **Inferir setores**. Isso preenche automaticamente os vínculos iniciais a partir dos processos históricos. Depois, revise manualmente os casos especiais.

## Migracao de banco

Use `scripts/migrate_postgres.py` para copiar dados entre bancos PostgreSQL compativeis.

Exemplo:

```bash
SOURCE_DATABASE_URL='postgresql+psycopg://...' \
TARGET_DATABASE_URL='postgresql+psycopg://...' \
python scripts/migrate_postgres.py --truncate-target
```
