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

O `render.yaml` cria:

- 1 web service Python
- 1 banco Render Postgres gratuito
- `DATABASE_URL` ligado automaticamente ao banco
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

## Limitacao importante do banco gratuito do Render

O Render informa que:

- web services gratuitos usam filesystem efemero
- bancos Postgres gratuitos expiram 30 dias apos a criacao

Isso significa que este fluxo e excelente para subir rapido e gastar zero, mas nao e o ideal para uso institucional continuo sem manutencao.

Se voce criar o banco gratuito em **16 de marco de 2026**, a expiracao esperada sera por volta de **15 de abril de 2026**, salvo mudanca nas regras do Render.

## Caminho recomendado depois do primeiro deploy

Se quiser manter a aplicacao sem essa limitacao de 30 dias, o proximo passo ideal e:

- manter o frontend no Vercel
- manter o backend no Render
- trocar apenas o banco para um Postgres gratuito mais duravel, como Neon Postgres

O backend ja aceita `DATABASE_URL`, entao essa troca exige pouca alteracao.

Arquivos preparados para isso:

- `MIGRAR-PARA-NEON.md`
- `render-external-db.yaml`
- `scripts/migrate_postgres.py`
