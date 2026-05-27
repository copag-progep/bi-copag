# Ambiente Local do AnalyticSEI

Este guia descreve como rodar o AnalyticSEI no Mac antes de enviar alterações para GitHub, Render e Vercel.

O objetivo é validar mudanças de tela, API e regras de cálculo em um ambiente seguro, sem tocar no banco de produção da Aiven.

## Visão Geral

| Componente | Produção | Local |
|---|---|---|
| Frontend | Vercel | `http://127.0.0.1:5173` |
| Backend/API | Render | `http://127.0.0.1:8000` |
| Banco | Aiven PostgreSQL | SQLite local em `backend/data/analyticsei-local.db` |
| Login | Usuários reais | Admin local definido em `.env.local` |

## Preparação

O backend local exige Python 3.12 ou superior. No Mac com Homebrew:

```bash
brew install python@3.12
```

Confira se ficou disponível:

```bash
python3.12 --version
```

Copie o exemplo de variáveis locais:

```bash
cp .env.local.example .env.local
```

Opcionalmente, copie o exemplo do frontend:

```bash
cp frontend/.env.local.example frontend/.env.local
```

Não coloque credenciais reais da produção nesses arquivos. Eles são ignorados pelo Git.

Se editar valores com espaço no `.env.local`, use aspas. Exemplo:

```bash
DEFAULT_ADMIN_NAME="Administrador Local"
```

## Rodando o Backend

Em um terminal:

```bash
./scripts/dev_backend.sh
```

O script cria `.venv`, instala dependências se necessário e sobe a API em:

```text
http://127.0.0.1:8000
```

Documentação interativa da API:

```text
http://127.0.0.1:8000/docs
```

Login local padrão, se você não editar `.env.local`:

```text
admin.local@ufc.br
admin123
```

## Rodando o Frontend

Em outro terminal:

```bash
./scripts/dev_frontend.sh
```

O frontend sobe em:

```text
http://127.0.0.1:5173
```

Por padrão, o frontend chama `/api` e o Vite encaminha essas chamadas para `http://127.0.0.1:8000`.

## Banco Local

O banco local padrão fica em:

```text
backend/data/analyticsei-local.db
```

Esse arquivo é ignorado pelo Git e pode ser apagado quando você quiser começar do zero:

```bash
rm backend/data/analyticsei-local.db
```

Ao subir a API novamente, as tabelas serão recriadas e o usuário admin local será criado.

## Como Testar Mudanças Antes Do Push

Fluxo recomendado e padrão do projeto:

```text
1. Fazer alteração no código
2. Rodar backend local
3. Rodar frontend local
4. Alimentar o banco local com CSVs de teste, quando a tela depender de dados
5. Testar tela/fluxo no navegador
6. Rodar validações
7. Fazer commit
8. Fazer push
```

Esse fluxo existe para evitar retrabalho em produção. Sempre que a alteração envolver
interface, upload, filtros, cálculos ou relatórios, primeiro valide em
`http://127.0.0.1:5173` usando o banco SQLite local. Só depois de confirmar o
comportamento no ambiente local a alteração deve ser enviada para o GitHub.

Validações úteis:

```bash
python3 -c "import py_compile; py_compile.compile('scripts/sei_uploader.py', cfile='/private/tmp/sei_uploader.pyc', doraise=True)"
npm run build
git diff --check
```

Para mudanças em scripts específicos, compile o arquivo alterado:

```bash
python3 -c "import py_compile; py_compile.compile('scripts/daily_report.py', cfile='/private/tmp/daily_report.pyc', doraise=True)"
```

## Testando Uploads Localmente

Para testar telas e cálculos com dados, use a tela **Enviar Relatório** no frontend local e envie CSVs de teste.

Esse é o caminho recomendado para simular dados antes de publicar mudanças. Os
uploads feitos em `http://127.0.0.1:5173` ficam apenas no banco SQLite local
`backend/data/analyticsei-local.db` e não alteram o banco de produção da Aiven.

Após os uploads locais, o badge de saúde dos dados no topo da aplicação deve
refletir a simulação: ele mostra a data global mais recente, quantos setores
estão em dia e alerta quando os CSVs usados no teste são antigos, incompletos ou
não cobrem todos os setores esperados.

Evite usar o upload automático real do SEI para testes locais sem necessidade. O objetivo do ambiente local é validar a aplicação, não executar automações contra o SEI.

## Testando Controle de Acesso Localmente

Depois de subir backend e frontend locais, valide também os cenários de acesso por divisão:

1. Entre com o usuário administrador local.
2. Crie um usuário comum na página **Administração → Acessos**.
3. Libere uma ou mais divisões para esse usuário.
4. Habilite ou desabilite a opção **Pode enviar relatórios**, conforme o teste desejado.
5. Saia da conta admin e entre com o usuário comum.
6. Confira se os painéis, filtros, listas, indicadores mensais, histórico de uploads e badge de saúde mostram apenas os setores liberados.
7. Em **Usuários SEI**, use **Inferir setores** ou configure manualmente os setores de cada usuário SEI.
8. Valide se os filtros **Atribuição** e **Servidor** exibem apenas nomes vinculados aos setores permitidos.

Para testar o fluxo de upload restrito, o usuário comum precisa ter a permissão de upload ativa e tentar enviar CSV apenas de setor liberado. Upload de setor não liberado deve ser bloqueado pela API.

## Cuidados Importantes

- Não use `DATABASE_URL` da Aiven produção no `.env.local`.
- Não use senhas reais do SEI em arquivos locais.
- Não commite `.env`, `.env.local`, bancos SQLite ou arquivos CSV reais.
- Use dados de teste ou snapshots previamente autorizados.
- Rode `npm run build` antes de abrir PR, commit final ou push importante.

## Quando Usar Um Banco PostgreSQL De Teste

SQLite é suficiente para validar interface, autenticação, uploads manuais e a maior parte dos cálculos.

Um PostgreSQL separado de teste só vale a pena quando a mudança envolver:

- Migrações Alembic sensíveis.
- Performance de consultas pesadas.
- Comportamento específico de PostgreSQL.
- Testes muito próximos da produção.

Nesse caso, crie outro banco fora da produção e coloque a URL apenas no `.env.local`.
