# SEI BI COPAG

Aplicação web completa para importação de snapshots CSV do SEI e análise gerencial de processos administrativos em formato de mini BI.

Para o caminho mais rápido de publicação, veja também [DEPLOY-MINIMO.md](./DEPLOY-MINIMO.md).

## O que esta aplicação entrega

- Login com email e senha
- Senha criptografada com `bcrypt`
- Autenticação com `JWT`
- Rotas protegidas no backend
- Upload diário de CSV com separador `;`
- Prevenção de duplicidade do mesmo arquivo
- Substituição do snapshot do mesmo setor/data quando um novo arquivo diferente é reenviado
- Importação automática inicial dos CSVs já presentes na pasta `6 DADOS COPAG`
- Dashboard principal com totais, rankings e evolução
- Página de entradas e saídas por setor
- Página de produtividade e permanência
- Página de processos parados
- Página de processos em múltiplos setores
- Administração com criação de novos logins e senhas dentro da aplicação
- Área administrativa restrita a usuários com perfil de administrador

## Tecnologias

### Backend

- Python
- FastAPI
- SQLAlchemy
- Pandas
- SQLite

### Frontend

- React
- Vite
- Recharts

## Estrutura do projeto

```text
backend/
  main.py
  models.py
  schemas.py
  database.py
  auth.py
  csv_importer.py
  analytics.py

frontend/
  src/
    pages/
    components/
    charts/
    context/
    api/

Dockerfile
requirements.txt
README.md
```

## Regras de negócio implementadas

### Upload e snapshots

- Cada arquivo CSV é associado a um `setor` e a uma `data_relatorio`
- O importador usa `delimiter=";"`
- O sistema lê as colunas:
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
- Campos vazios ou com `-` são normalizados
- O mesmo arquivo não é importado duas vezes porque a aplicação calcula hash do conteúdo
- Se um novo arquivo diferente for enviado para o mesmo setor e a mesma data, o snapshot anterior é substituído

### Entradas e saídas

- Entrada = processo presente na data atual e ausente na data anterior para o mesmo setor
- Saída = processo presente na data anterior e ausente na data atual para o mesmo setor
- Saldo = carga atual menos carga da data anterior

### Permanência e processos parados

Como o SEI exportado aqui é um snapshot diário e não um log transacional, a permanência é inferida a partir da presença contínua do protocolo no setor ao longo das datas importadas.

- Entrada no setor = primeira data da sequência contínua de presença do protocolo no setor
- Saída do setor = primeira data disponível em que o protocolo deixa de aparecer naquele setor
- Tempo médio de permanência = média das durações inferidas por setor e por tipo
- Dias sem movimentação = duração da permanência em aberto no setor atual

## Usuário administrador inicial

Ao iniciar o backend, a aplicação cria automaticamente um usuário administrador padrão:

- Email: `andersoncfs@ufc.br`
- Senha: `admin123`

Depois do primeiro acesso, use a página **Administração** para criar usuários adicionais.
Novos usuários são criados como usuários comuns por padrão, e podem receber perfil administrativo quando necessário.

## Como instalar localmente

### 1. Backend

Pré-requisitos:

- Python 3.11 ou superior

Passos:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

O backend ficará disponível em:

- `http://localhost:8000`
- Documentação interativa: `http://localhost:8000/docs`

### 2. Frontend

Pré-requisitos:

- Node.js 18 ou superior
- npm 9 ou superior

Passos:

```bash
cd frontend
npm install
npm run dev
```

O frontend ficará disponível em:

- `http://localhost:5173`

### 3. Variáveis de ambiente

Backend:

- copie `.env.example` para `.env` se quiser personalizar
- altere `JWT_SECRET_KEY`
- altere a senha padrão do administrador em `DEFAULT_ADMIN_PASSWORD`

Frontend:

- copie `frontend/.env.example` para `frontend/.env`
- ajuste `VITE_API_URL` quando o frontend não estiver usando o proxy local do Vite

## Como rodar o backend

Com ambiente virtual ativo:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Como rodar o frontend

```bash
cd frontend
npm run dev
```

## Como importar os CSVs

### Importação automática inicial

Ao iniciar o backend, a aplicação procura por arquivos com padrão:

```text
ListaProcessos_SEIPro_YYYYMMDD_setor.csv
```

Os arquivos já existentes na pasta conectada `6 DADOS COPAG` são importados automaticamente quando o backend sobe.

### Importação manual diária

1. Faça login
2. Acesse **Enviar Relatório**
3. Selecione o CSV exportado do SEI
4. Escolha o setor
5. Informe a data do relatório
6. Clique em **Enviar**

## Como usar os dashboards

### Dashboard

- total de processos ativos
- total por setor
- total por tipo
- total por atribuição
- evolução diária
- ranking de atribuições

### Entradas e Saídas

- entradas por setor
- saídas por setor
- saldo por setor
- evolução da carga

### Produtividade

- tempo médio por setor
- tempo médio por tipo
- top 10 processos mais antigos
- métricas setoriais

### Processos Parados

- alertas acima de 10, 20 e 30 dias
- tabela de processos críticos

### Processos em Múltiplos Setores

- detecção de protocolos em mais de um setor no mesmo dia
- filtro por data de referência

### Administração

- criação de novos usuários
- visualização dos usuários cadastrados
- histórico recente de uploads

## Banco de dados

O banco padrão é SQLite e é criado automaticamente em:

```text
backend/data/sei_bi.db
```

Tabelas implementadas:

- `users`
- `uploads`
- `processos`

## Deploy gratuito

### Backend no Render

Opção 1 com Docker:

1. envie o projeto para um repositório Git
2. crie um novo Web Service no Render
3. escolha a opção de deploy via Docker
4. configure as variáveis:
   - `JWT_SECRET_KEY`
   - `DEFAULT_ADMIN_EMAIL`
   - `DEFAULT_ADMIN_PASSWORD`
   - `FRONTEND_URL`
5. publique

Comando executado no container:

```text
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### Frontend no Vercel

1. publique a pasta `frontend` em um repositório
2. crie um projeto no Vercel
3. defina:
   - framework: `Vite`
   - build command: `npm run build`
   - output directory: `dist`
4. configure a variável `VITE_API_URL` apontando para `https://SEU-BACKEND.onrender.com/api`
5. publique

O arquivo `frontend/vercel.json` já inclui rewrite para SPA.

## Observações importantes

- Este projeto usa inferência sobre snapshots diários. Se no futuro você tiver logs transacionais completos do SEI, será possível refinar ainda mais as métricas de movimentação e permanência.
- O sistema foi preparado para manutenção simples, sem serviços pagos obrigatórios.
- O banco SQLite atende bem ao início do projeto. Se o volume crescer, a migração para PostgreSQL pode ser feita com poucas mudanças no backend.
