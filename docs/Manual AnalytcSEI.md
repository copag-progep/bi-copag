# Manual AnalytcSEI

Material didático para gestores sobre as telas, funcionalidades, gráficos e indicadores do sistema AnalyticSEI.

> Observação sobre o nome do arquivo: este documento foi salvo como **Manual AnalytcSEI.md**, conforme solicitado. Ao longo do texto, o sistema é tratado pelo nome institucional **AnalyticSEI**.

---

## 1. O que é o AnalyticSEI

O **AnalyticSEI** é uma plataforma de Business Intelligence criada para transformar relatórios CSV exportados do SEI em painéis de gestão para a COPAG/PROGEP/UFC.

Na prática, ele pega fotografias diárias das carteiras de processos de cada divisão e responde perguntas como:

- Quantos processos estão ativos hoje?
- Em quais setores eles estão?
- Quais processos entraram e saíram desde o último snapshot?
- Quais atribuições ou servidores estão com maior carga?
- Quais processos estão há mais tempo sem movimentação?
- Quais processos aparecem em mais de um setor ao mesmo tempo?
- Qual é o tempo médio de permanência dos processos que saíram das carteiras?
- Qual setor tende a acumular mais processos nos próximos dias?
- Quais processos merecem prioridade pela combinação de fatores de risco?

O sistema não substitui o SEI. Ele funciona como uma camada de leitura gerencial sobre os dados exportados do SEI.

---

## 2. Como os dados chegam ao sistema

### 2.1. O que é um snapshot

Um **snapshot** é uma fotografia de uma carteira de processos em uma data específica.

Exemplo:

- Em 19/05/2026, a DIAPE exporta do SEI uma lista CSV com todos os processos que estão naquela unidade.
- Esse CSV é enviado ao AnalyticSEI.
- O sistema grava que, naquela data, aqueles protocolos estavam na DIAPE.

Quando o mesmo processo aparece ou desaparece em snapshots seguintes, o sistema infere entradas, saídas, permanência, produtividade e histórico.

### 2.2. Setores monitorados

O sistema trabalha com os seguintes setores:

- DIAPE
- DICAT
- DIJOR
- DICAF
- DICAF-CHEFIA
- DICAF-REPOSICOES

### 2.3. Campos principais importados do CSV do SEI

O CSV do SEI alimenta principalmente:

- Protocolo do processo
- Atribuição
- Tipo do processo
- Especificação
- Ponto de controle
- Data de autuação
- Data de recebimento
- Data de envio
- Unidade de envio
- Observações
- Setor informado no upload
- Data do relatório informada no upload

### 2.4. Tratamento feito na importação

Ao importar um relatório, o sistema:

- Lê o CSV usando separador `;`.
- Tenta interpretar a codificação do arquivo em `utf-8-sig`, `utf-8` e `latin-1`.
- Remove linhas sem protocolo.
- Remove protocolos duplicados dentro do mesmo CSV, mantendo a primeira ocorrência.
- Converte datas do CSV para o formato interno do banco.
- Normaliza campos vazios, traços e valores inválidos.
- Aplica o DE-PARA de usuários SEI para consolidar nomes de atribuição.
- Calcula um hash do arquivo para evitar importação duplicada do mesmo relatório.

### 2.5. Substituição de snapshot

Se já existir um relatório para o mesmo setor e a mesma data, um novo upload substitui o snapshot anterior daquele setor/data. Isso permite corrigir relatórios importados com erro.

---

## 3. Como entender os filtros globais

As telas analíticas usam a barra **Recorte analítico**.

### 3.1. Data de referência

É a data principal da análise. Se não for escolhida manualmente, o sistema usa a última data disponível.

Exemplo:

- Último snapshot importado: 2026-05-19.
- A data de referência será 2026-05-19.
- Os cards e tabelas mostram a situação daquela data.

### 3.2. Data inicial e data final

Definem o período histórico analisado em gráficos e rankings.

Quando nenhum período é escolhido, a maioria das consultas usa uma janela padrão de histórico para reduzir consumo do banco e acelerar carregamento.

Importante:

- Indicadores de duração, como processos parados, atribuições e lead time, usam histórico completo quando precisam calcular permanência corretamente.
- Indicadores de visão geral e tendência podem usar a janela configurada para manter o sistema leve.

### 3.3. Setor

Filtra as análises para um setor específico.

Exemplo:

- Se o setor selecionado for DICAF-CHEFIA, os gráficos passam a mostrar apenas dados relacionados à DICAF-CHEFIA, quando a tela permite esse recorte.

### 3.4. Tipo de processo

Filtra as análises por tipo do processo informado no CSV do SEI.

### 3.5. Atribuição

Filtra as análises por atribuição normalizada.

Também existe a opção **Sem atribuição**, usada para localizar processos sem responsável definido no snapshot.

---

## 4. Elementos fixos da interface

### 4.1. Menu lateral

O menu lateral dá acesso às principais áreas:

- Central Executiva
- Dashboard
- Enviar Relatório
- Entradas e Saídas
- Produtividade
- Múltiplos Setores
- Atribuições
- Score de Risco
- Pauta Prioritária
- Servidores
- Indicadores Mensais
- Minha Conta
- Documentação
- Usuários SEI, para administradores
- Administração, para administradores

### 4.2. Busca global por protocolo

No topo da plataforma há uma busca por protocolo. Ela permite localizar um processo e ver:

- Setor atual
- Atribuição atual
- Primeira aparição no histórico
- Última aparição
- Histórico de passagens por setor/atribuição
- Duração estimada de cada período

### 4.3. Selo de frescor dos dados

O selo de frescor indica se os dados estão atualizados.

Ele avalia:

- Data global mais recente importada.
- Quantos setores estão em dia nessa data.
- Quais setores estão defasados.
- Quais setores nunca enviaram snapshot.
- Se algum snapshot veio com volume muito abaixo do histórico recente.

Estados possíveis:

- **Dados em dia**: todos os setores esperados estão compatíveis com a referência e a idade dos dados está dentro do limite.
- **Atenção**: há setor defasado, setor ausente, alerta de qualidade ou dados mais antigos que o limite de conforto.
- **Crítico**: dados muito antigos.
- **Sem dados**: nenhum snapshot importado.

### 4.4. Sino de alertas

O sino de alertas mostra processos críticos por tempo sem movimentação.

Ele consulta o resumo de alertas e exibe:

- Quantidade de processos com mais de 30 dias.
- Quantidade de processos com mais de 45 dias.
- Quantidade de processos com mais de 90 dias.
- Lista resumida dos processos mais críticos, priorizando os de 45 dias ou mais.

O badge do sino usa como destaque principal os processos com **45 dias ou mais**.

---

## 5. Tela Login

### O que entrega

Permite entrar na plataforma com e-mail e senha cadastrados pelo administrador.

### O que aparece

- Nome do sistema: AnalyticSEI.
- Subtítulo: painéis, indicadores e alertas para gestão de processos do SEI.
- Formulário de e-mail e senha.
- Cards institucionais sobre dashboards, setores monitorados e integração via CSV.

### Como funciona

Ao informar e-mail e senha, o sistema valida as credenciais no backend. Se estiverem corretas, gera um token de acesso temporário. Esse token é usado para acessar as páginas protegidas.

---

## 6. Tela Central Executiva

### Objetivo da tela

Entregar ao gestor uma visão rápida, acionável e resumida do dia.

Ela foi pensada para responder:

- O que exige atenção hoje?
- O saldo do dia aumentou ou reduziu?
- Os dados estão atualizados?
- Há processos críticos?
- Algum setor está acumulando carga?
- Existe tendência de crescimento ou redução no estoque?

### Indicadores principais

#### Processos ativos

Quantidade de protocolos únicos existentes no snapshot de referência.

Cálculo:

```text
Processos ativos = número de protocolos distintos na data de referência
```

Se o mesmo protocolo aparece em mais de um setor, ele é contado uma vez nesse KPI global.

#### Entradas

Quantidade de processos que aparecem no snapshot atual, mas não apareciam no snapshot anterior no mesmo setor.

Cálculo:

```text
Entradas = protocolos do setor na data atual - protocolos do setor na data anterior
```

#### Saídas

Quantidade de processos que apareciam no snapshot anterior, mas não aparecem mais no snapshot atual no mesmo setor.

Cálculo:

```text
Saídas = protocolos do setor na data anterior - protocolos do setor na data atual
```

#### Saldo

Diferença entre entradas e saídas.

Cálculo:

```text
Saldo = Entradas - Saídas
```

Interpretação:

- Saldo positivo: a carteira cresceu.
- Saldo negativo: a carteira reduziu.
- Saldo zero: entradas e saídas se equilibraram.

### Prioridades do dia

O bloco de prioridades reúne alertas automáticos a partir de diferentes fontes.

Ele pode incluir:

- Dados desatualizados ou incompletos.
- Processos com 30 ou 90 dias ou mais.
- Setores com saldo positivo relevante.
- Processos em múltiplos setores.

Essa lista não é cadastrada manualmente. Ela é montada pelo sistema com base nos indicadores.

### Saúde dos dados

Mostra:

- Se os dados estão em dia.
- Quantos setores estão atualizados.
- Quantos processos estão com mais de 30 dias.
- Quantos estão com 90 dias ou mais.
- Quantos processos aparecem em múltiplos setores.

### Tempo de permanência

É a seção de lead time estimado.

Ela mostra:

- Média de dias.
- Mediana de dias.
- P90.
- Quantidade de processos finalizados.
- Distribuição por faixas de duração.
- Ranking de lead time por setor.

#### Média

É a soma das durações dividida pela quantidade de processos que saíram da carteira.

```text
Média = soma das durações / quantidade de processos finalizados
```

#### Mediana

É o valor central da lista de durações.

Exemplo:

- Durações: 2, 4, 8, 20, 50 dias.
- Mediana: 8 dias.

A mediana ajuda quando existem valores extremos que distorcem a média.

#### P90

P90 significa **percentil 90**.

Ele responde:

> "90% dos processos finalizados ficaram até X dias; 10% demoraram mais que isso."

Exemplo:

- P90 = 44 dias.
- Interpretação: 90% dos processos que saíram ficaram até 44 dias na carteira; os 10% mais demorados passaram desse valor.

O P90 é útil porque mostra o limite superior típico sem deixar que poucos casos extremos dominem a análise.

#### Finalizados

Quantidade de spans fechados, ou seja, processos que estavam em uma carteira e depois deixaram de aparecer nela.

### Estoque ativo: tendências

Essa seção mostra estimativas para os próximos dias.

Importante: o sistema não promete prever o futuro. Ele estima tendência com base no histórico recente.

A frase correta de leitura é:

> "Se o ritmo atual se mantiver..."

#### Atual

Quantidade atual de processos ativos.

#### Estimado em 15 dias e 30 dias

Projeção calculada por regressão linear simples sobre os snapshots recentes.

Resumo do cálculo:

```text
1. O sistema pega a evolução recente do total de processos.
2. Calcula a inclinação da tendência.
3. Converte essa inclinação para variação média diária.
4. Estima o estoque em 15 e 30 dias.
```

Para evitar falsa precisão, o resultado é arredondado.

#### Tendência por setor

Para cada setor, o sistema calcula a variação média diária da carga.

Classificação:

- **Acumulando**: variação média maior que +1 processo por dia.
- **Resolvendo**: variação média menor que -1 processo por dia.
- **Estável**: variação entre -1 e +1 processo por dia.

#### Processos críticos estimados

O sistema estima quantos processos podem cruzar a faixa de 30 dias em breve com base nas presenças consecutivas até o snapshot atual.

Não é a contagem oficial da página Atribuições. É uma estimativa gerencial.

### Carga por setor

Mostra os setores com maior carga atual:

- Setor
- Ativos
- Entradas
- Saídas
- Saldo

### Processos mais críticos

Mostra os cinco processos com maior tempo sem movimentação no setor atual.

---

## 7. Tela Dashboard

### Objetivo da tela

Oferecer uma visão geral da tramitação dos processos no snapshot selecionado.

### Cards principais

#### Processos ativos

Quantidade de protocolos únicos na data de referência.

```text
Processos ativos = contagem distinta de protocolos no snapshot atual
```

#### Registros no snapshot

Quantidade total de linhas importadas no snapshot atual.

```text
Registros no snapshot = total de linhas/processos gravados na data de referência
```

Diferença importante:

- Processos ativos conta protocolos únicos.
- Registros no snapshot conta linhas. Se um protocolo aparece em mais de um setor, pode aumentar a quantidade de registros.

#### Setores ativos

Quantidade de setores com processos no snapshot atual.

```text
Setores ativos = número de setores distintos no snapshot atual
```

#### Em múltiplos setores

Quantidade de protocolos que aparecem em mais de um setor no mesmo snapshot.

```text
Duplicidades multissetor = protocolos com mais de um setor na data de referência
```

### Gráficos

#### Processos por setor

Mostra quantos registros existem em cada setor na data de referência.

```text
Processos por setor = contagem de registros agrupada por setor
```

#### Processos por tipo

Mostra os tipos de processo mais frequentes no snapshot.

```text
Processos por tipo = contagem de registros agrupada por tipo
```

#### Ranking de atribuições

Mostra as atribuições com maior quantidade de processos no snapshot atual.

```text
Ranking de atribuições = contagem de registros agrupada por atribuição normalizada
```

Quando o nome de um usuário é longo, os gráficos exibem iniciais para melhorar a leitura. Ao passar o mouse, o nome completo aparece no tooltip.

#### Evolução diária do total de processos

Mostra a quantidade de protocolos únicos ao longo dos snapshots.

```text
Evolução diária = contagem de protocolos distintos por data de relatório
```

### Tabela: Atribuições com mais finalizações

Mostra quais atribuições tiveram mais saídas inferidas no histórico.

Cálculo:

```text
1. Para cada data, setor e atribuição, o sistema monta a carteira de processos.
2. Compara a carteira anterior com a carteira atual.
3. Se um processo estava antes e não está mais, conta como finalização/saída daquela atribuição.
```

Importante:

- É uma inferência baseada em snapshots.
- Não significa necessariamente que o processo foi finalizado administrativamente no SEI.
- Significa que ele deixou aquela carteira/setor entre um snapshot e outro.

---

## 8. Tela Enviar Relatório

### Objetivo da tela

Permitir a atualização dos dados a partir de arquivos CSV exportados do SEI.

### Quem pode acessar

A tela só fica disponível para:

- Administradores.
- Usuários comuns habilitados pelo administrador com a permissão de envio de relatório.

Usuários comuns também precisam ter acesso ao setor do CSV que desejam enviar. Se o usuário tem acesso apenas a uma divisão, não conseguirá enviar relatório de outra divisão.

### Campos do envio

#### Setor

Setor ao qual o CSV pertence.

#### Data do relatório

Data que representa o snapshot. Deve corresponder ao dia do relatório exportado.

#### Arquivo CSV exportado do SEI

Arquivo que contém a lista de processos do setor.

### O que acontece após o envio

O sistema:

- Valida se o setor é permitido.
- Valida se o arquivo é CSV.
- Lê e trata os dados.
- Salva o upload na tabela de uploads.
- Salva os processos na tabela de processos.
- Atualiza a normalização de atribuições.
- Limpa o cache analítico.
- Dispara pré-cálculo em segundo plano quando configurado.
- Atualiza as opções de filtros.

### Histórico recente de uploads

Lista os relatórios importados, do mais recente para o mais antigo.

Paginação:

- 30 relatórios por página.

Colunas:

- Setor
- Data do relatório
- Importado em
- Arquivo
- Registros
- Ações, para administradores

### Ações administrativas

Administradores podem:

- Corrigir a data de um relatório.
- Excluir um relatório.

Ao excluir um upload, os processos daquele snapshot também são removidos.

---

## 9. Tela Entradas e Saídas

### Objetivo da tela

Mostrar o fluxo de processos entre dois snapshots consecutivos.

### O que a tela compara

Ela compara:

- Data anterior disponível.
- Data de referência.

### Indicadores principais

#### Entradas do dia

Quantidade total de processos que passaram a aparecer no setor.

```text
Entradas = protocolos presentes na data atual - protocolos presentes na data anterior
```

#### Saídas do dia

Quantidade total de processos que deixaram de aparecer no setor.

```text
Saídas = protocolos presentes na data anterior - protocolos presentes na data atual
```

#### Saldo do dia

Diferença entre entradas e saídas.

```text
Saldo = entradas - saídas
```

Interpretação:

- Saldo positivo: aumento de carga.
- Saldo negativo: redução de carga.
- Saldo zero: equilíbrio.

### Gráficos

#### Entradas por setor

Mostra quantos processos novos entraram em cada setor.

#### Saídas por setor

Mostra quantos processos saíram de cada setor.

#### Saldo por setor

Mostra o resultado líquido de cada setor.

#### Evolução diária da carga por setor

Mostra como a quantidade de processos em cada setor variou ao longo do tempo.

### Tabela Resumo setorial

Colunas:

- Setor
- Entradas
- Saídas
- Saldo
- Carga atual

---

## 10. Tela Produtividade

### Objetivo da tela

Estimar a produção diária por atribuição/servidor com base no que saiu da carteira entre snapshots.

### Conceito importante

O sistema não mede "produtividade" por lançamento manual de atividades. Ele infere produção comparando carteiras.

### Cálculo da produção estimada

```text
Produção estimada = processos que estavam atribuídos no snapshot anterior e não estão mais na mesma atribuição na data de referência
```

Exemplo:

- Ontem, um servidor tinha os processos A, B e C.
- Hoje, ele tem B, C e D.
- O processo A saiu da carteira.
- O processo D entrou na carteira.

Resultado:

- Produzidos: 1
- Entradas: 1
- Carga anterior: 3
- Carga atual: 3
- Saldo: 0

### Cards principais

#### Produção estimada do dia

Soma dos processos que saíram das atribuições entre os snapshots comparados.

#### Entradas do dia

Soma dos processos que entraram nas atribuições na data de referência.

#### Maior produtor do dia

Atribuição com maior quantidade de processos que saíram da carteira no dia.

#### Carga atual atribuída

Quantidade total de processos com atribuição na data de referência.

### Destaques do dia

Mostra as três atribuições com maior produção estimada no snapshot atual.

### Gráficos

#### Produção do dia por atribuição

Mostra quantos processos deixaram cada carteira.

#### Entradas do dia por atribuição

Mostra quantos processos passaram a constar em cada carteira.

#### Carga atual por atribuição

Mostra quantos processos estão hoje em cada atribuição.

#### Evolução diária da produção por atribuição

Mostra série histórica das atribuições mais produtivas no período filtrado.

### Tabela Resumo do dia por atribuição

Colunas:

- Atribuição
- Carga anterior
- Carga atual
- Entradas
- Produzidos
- Saldo
- Taxa de produção

#### Taxa de produção

```text
Taxa de produção = (produzidos / carga anterior) × 100
```

Se a carga anterior for zero, a taxa é zero.

### Ranking acumulado no período

Mostra, dentro do período filtrado:

- Produzidos no período.
- Entradas no período.
- Dias com movimento.
- Média diária.

#### Média diária de produção

```text
Média diária = produzidos no período / número de transições entre snapshots
```

---

## 11. Tela Múltiplos Setores

### Objetivo da tela

Identificar protocolos que aparecem em mais de um setor na mesma data de referência.

### Por que isso importa

Um processo em múltiplos setores pode indicar:

- Tramitação compartilhada.
- Transição entre unidades.
- Duplicidade ou inconsistência no snapshot.
- Situação que merece conferência.

### Cards

#### Total de ocorrências

Quantidade de protocolos em múltiplos setores.

#### Em 2 setores

Quantidade de protocolos presentes exatamente em dois setores.

#### Em 3 ou mais setores

Quantidade de protocolos presentes em três ou mais setores.

#### Setores envolvidos

Quantidade de setores distintos que aparecem nessas ocorrências.

### Cálculo

```text
1. O sistema pega todos os registros do snapshot atual.
2. Agrupa por protocolo.
3. Conta quantos setores diferentes cada protocolo possui.
4. Mantém apenas protocolos com mais de um setor.
```

### Como funciona para usuários com acesso restrito

A detecção de múltiplos setores precisa olhar o snapshot completo, porque um processo pode estar no setor permitido do usuário e também em outro setor.

A lógica correta é:

```text
1. Detectar globalmente quais protocolos aparecem em mais de um setor.
2. Depois filtrar a lista para exibir apenas ocorrências que envolvem setores visíveis ao usuário.
```

Assim, o usuário restrito consegue saber que um processo do seu setor também aparece em outro setor, mas não recebe acesso completo aos dados das demais divisões.

### Tabela de ocorrências

Colunas:

- Protocolo
- Setores
- Quantidade
- Data do relatório

A busca da tela filtra por número de protocolo.

### Exportações

A tela possui os botões **Exportar Excel** e **Gerar PDF**, seguindo o mesmo padrão visual da tela Atribuições.

As exportações respeitam:

- filtros globais aplicados no topo da plataforma;
- escopo de setores do usuário logado;
- busca por protocolo feita dentro da própria tela.

O Excel gera uma planilha com resumo e tabela de ocorrências. O PDF gera um relatório com identidade visual AnalyticSEI/PROGEP/UFC, cards de resumo e a lista dos protocolos em múltiplos setores.

---

## 12. Tela Atribuições

### Objetivo da tela

Mostrar a carteira ativa de processos por atribuição, com tempo de permanência.

É uma das telas mais importantes para gestão operacional.

### Cards principais

#### Total de processos

Quantidade de processos ativos no recorte atual da tela.

#### Com atribuição

Quantidade de processos com responsável/atribuição identificada.

#### Sem atribuição

Quantidade de processos sem atribuição definida.

#### Maior tempo registrado

Maior quantidade de dias em que um processo permanece com a mesma atribuição/setor no snapshot atual.

### Como o sistema calcula os dias com atribuição

O sistema procura, para cada processo, setor e atribuição, desde quando ele aparece de forma consecutiva até a data de referência.

Cálculo simplificado:

```text
1. Escolhe o snapshot de referência.
2. Para cada processo ativo, identifica setor e atribuição atuais.
3. Volta no histórico enquanto o processo continuar aparecendo no mesmo setor e na mesma atribuição.
4. Para quando há uma quebra no histórico.
5. Calcula dias = data de referência - primeira data dessa sequência.
```

O cálculo usa índice por setor, porque cada setor pode ter frequência de upload diferente.

### Faixas de tempo

A tela permite filtrar por:

- Todos
- Menos de 15 dias
- 15 a 29 dias
- 30 a 44 dias
- 45 a 59 dias
- 60 a 89 dias
- 90 dias ou mais

Essas faixas ajudam a priorizar processos mais antigos.

### Busca por protocolo

Permite localizar um processo específico dentro da carteira.

### Ordenação

Permite ordenar por:

- Dias
- Atribuição
- Tipo

### Exportações

A tela permite exportar a carteira em:

- Excel
- PDF

### Observação de interpretação

O tempo exibido não é necessariamente o tempo total de vida do processo no SEI. É o tempo inferido de permanência naquela carteira, com base nos snapshots disponíveis.

---

## 13. Tela Score de Risco

### Objetivo da tela

Priorizar processos que merecem atenção.

Enquanto a tela Atribuições mostra tempo e carteira, o Score de Risco combina vários sinais para responder:

> "Onde o gestor deve olhar primeiro?"

### Importante

O score é calculado sobre o **processo**, não sobre o servidor.

Ele não deve ser usado como avaliação individual de desempenho.

### Fatores do score

#### Fator 1: tempo absoluto no setor

Peso padrão: 40%.

```text
D_abs = min(dias_no_setor / 90, 1)
```

Interpretação:

- 30 dias = 33% do fator.
- 60 dias = 67% do fator.
- 90 dias ou mais = 100% do fator.

#### Fator 2: tempo relativo ao histórico

Peso padrão: 35%.

Compara o tempo atual do processo com o P90 histórico.

```text
D_rel = min(dias_no_setor / P90, 2) / 2
```

Se o processo já passou muito do P90, o fator cresce.

Hierarquia usada para buscar o P90:

1. P90 do setor.
2. P90 do tipo.
3. P90 global.

Se não houver histórico suficiente, esse fator não é aplicado.

Existe um piso técnico de P90 para evitar que valores históricos muito baixos criem risco artificial.

#### Fator 3: ausência de atribuição

Peso padrão: 15%.

```text
Sem atribuição = 1
Com atribuição = 0
```

Processo sem responsável definido recebe aumento no score.

#### Fator 4: múltiplos setores

Peso padrão: 10%.

```text
Múltiplos setores = 1
Setor único = 0
```

Processo em mais de um setor recebe aumento no score.

#### Fator 5: tendência do setor

É um multiplicador, não um fator somado.

Padrões:

- Setor acumulando: multiplica por 1,20.
- Setor estável: multiplica por 1,00.
- Setor resolvendo: multiplica por 0,85.

### Fórmula final

```text
Score base =
  0,40 × D_abs
+ 0,35 × D_rel
+ 0,15 × sem_atribuicao
+ 0,10 × multiplos_setores

Score final = min(Score base × multiplicador_tendencia, 1)
```

O score é exibido em escala visual de 0 a 100.

### Níveis de risco

Padrões:

- Crítico: score maior ou igual a 0,70.
- Elevado: score maior ou igual a 0,45.
- Moderado: score maior ou igual a 0,20.
- Normal: score menor que 0,20.

### O que a tabela mostra

Colunas:

- Protocolo
- Setor
- Atribuição
- Tipo
- Dias
- Score
- Nível

Ao clicar em uma linha, a tela mostra o detalhamento dos fatores que contribuíram para aquele score.

### Como usar na gestão

Use essa tela para montar uma fila de atenção:

1. Comece pelos críticos.
2. Veja o motivo do score.
3. Verifique se o processo está sem atribuição.
4. Verifique se está em múltiplos setores.
5. Compare o tempo com o P90.
6. Acesse a carteira completa se precisar de contexto adicional.

---

## 13.1. Tela Pauta Prioritária

### Objetivo da tela

Transformar os processos críticos em acompanhamento semanal. A Pauta Prioritária é usada para montar a lista da reunião, atribuir responsáveis e acompanhar se os processos saíram do setor.

### Quem usa

Administradores:

- criam sessões de pauta;
- definem início, data da reunião e prazo da pauta;
- editam título, datas e observações quando necessário;
- adicionam processos a partir do Score de Risco, da tela Atribuições ou da própria página da pauta;
- escolhem o responsável;
- registram a nota da gestão;
- geram PDF da reunião;
- encerram a sessão e copiam pendências para a próxima semana;
- consultam métricas administrativas.

Responsáveis:

- veem apenas os itens atribuídos a eles e dos setores aos quais ainda possuem acesso;
- visualizam o cronograma da sessão, com início, reunião e prazo da pauta;
- confirmam ciência;
- registram atualização na nota do responsável.

### Cronograma da sessão

Cada pauta possui uma faixa de cronograma com três marcos:

- **Início**: quando começa o acompanhamento da pauta;
- **Reunião**: data prevista para discussão dos processos;
- **Prazo da pauta**: data limite de acompanhamento da sessão.

O sistema mostra mensagens como "faltam 2 dias", "prazo termina hoje" ou "vencido há X dias". Essas datas aparecem tanto para administradores quanto para responsáveis.

O administrador pode usar o ícone de edição do cronograma para alterar título, início, reunião, prazo e observações. As alterações ficam registradas no log de auditoria.

### Situação da pauta

A situação da sessão é calculada automaticamente:

- **A iniciar**: a data de início ainda não chegou;
- **Em andamento**: a pauta já iniciou e o prazo ainda não venceu;
- **Encerrada**: o prazo já passou ou o administrador encerrou manualmente.

Mesmo quando a pauta estiver encerrada, o administrador pode editar datas para corrigir um prazo informado de forma errada. Sessões encerradas não recebem novos processos, mas pendências ainda podem ser copiadas para uma nova sessão.

### Como a resolução funciona

O responsável não marca o processo como resolvido.

A resolução é automática. Depois de cada upload válido do setor, o sistema verifica se o protocolo ainda aparece no snapshot. Se o processo deixar de constar na lista do setor, o item da pauta muda para **Resolvido automaticamente**.

Isso significa que o processo foi concluído naquele setor ou encaminhado para fora dele. Em casos excepcionais, apenas o administrador pode usar a opção **Forçar resolução**, que fica registrada como resolução manual.

### PDF da pauta

O botão **PDF** gera um documento da sessão selecionada com:

- título da sessão;
- período, data da reunião e prazo da pauta;
- resumo de status;
- protocolo, setor, tipo, dias, risco, responsável, status e nota da gestão.

### Métricas

Administradores podem abrir o painel de métricas da pauta para acompanhar:

- tempo médio até resolução automática;
- quantidade de resoluções manuais;
- pendências arrastadas de sessões encerradas;
- eficiência por sessão.

### Progresso da pauta

A tela mostra o progresso da sessão com uma barra de resolução:

- processos resolvidos automaticamente ou manualmente;
- processos em acompanhamento;
- processos pendentes.

Para responsáveis, os números consideram apenas os itens atribuídos a eles.

### Encerramento e cópia de pendências

Quando uma sessão ainda está **A iniciar** ou **Em andamento**, a ação **Encerrar e copiar pendências** encerra a sessão de origem e cria uma nova sessão com os itens pendentes ou em acompanhamento.

Quando a sessão já está **Encerrada** pelo prazo, a ação passa a ser **Copiar pendências**: o sistema cria a nova sessão, preservando o histórico da sessão original.

O sistema impede duplicidade de um mesmo processo na mesma passagem ativa. Para isso, usa a chave formada por protocolo, setor e entrada no setor.

---

## 14. Funcionalidade Processos sem movimentação

### Onde aparece

O indicador de processos sem movimentação aparece em várias partes do sistema:

- Central Executiva.
- Sino de alertas.
- Relatórios por e-mail.
- Score de Risco.
- Tabelas de processos críticos.

Dependendo da versão da interface, pode aparecer como página própria de **Processos Parados** ou como painel integrado nas telas executivas.

### Objetivo

Identificar processos que permanecem no mesmo setor por muitos dias, sem deixar a carteira nos snapshots seguintes.

### Como o cálculo funciona

O sistema monta spans de presença por protocolo e setor.

```text
1. O processo aparece no setor em uma data.
2. O sistema verifica se ele continua aparecendo no mesmo setor nos snapshots seguintes.
3. Enquanto a presença for consecutiva, o período continua aberto.
4. Se o processo deixa de aparecer, o período é encerrado.
5. Se ele ainda aparece no snapshot atual, é considerado processo ativo/parado.
```

### Dias sem movimentação

```text
Dias sem movimentação = data de referência - primeira data da presença consecutiva no setor
```

### Contagens exibidas

O sistema calcula:

- Mais de 10 dias.
- Mais de 20 dias.
- Mais de 30 dias.

Outras telas e alertas também destacam:

- 45 dias ou mais.
- 90 dias ou mais.

### Como interpretar

Um processo com muitos dias sem movimentação não significa, sozinho, erro ou atraso. Pode haver motivo administrativo legítimo. O indicador serve para chamar atenção e apoiar revisão gerencial.

---

## 15. Tela Servidores

### Objetivo da tela

Analisar distribuição de carga entre atribuições/servidores e histórico individual de carteira.

A tela possui duas abas:

- Balanceamento de carteiras.
- Perfil do servidor.

### Aba Balanceamento de carteiras

#### Total distribuído

Quantidade total de processos atribuídos no snapshot atual.

#### Servidores monitorados

Quantidade de atribuições com processos.

#### Média por servidor

```text
Média = total de processos atribuídos / número de servidores monitorados
```

#### Desvio padrão

Mede o quanto as cargas se espalham em relação à média.

Quanto maior o desvio padrão, maior a desigualdade de distribuição.

#### Desvio-Z

Para cada servidor, o sistema calcula:

```text
Desvio-Z = (carga do servidor - média geral) / desvio padrão
```

Interpretação:

- Desvio-Z alto: carteira acima da média.
- Desvio-Z baixo: carteira abaixo da média.

#### Status de carga

Classificação:

- Sobrecarga: desvio-Z maior que 1,5.
- Elevada: desvio-Z maior que 0,5.
- Baixa: desvio-Z menor que -1,0.
- Normal: demais casos.

### Gráfico Carga atual por servidor

Mostra barras horizontais com a carga atual de cada servidor.

A linha pontilhada representa a média.

### Tabela Detalhamento por servidor

Colunas:

- Servidor
- Carga atual
- Percentual do total
- Variação em relação ao snapshot anterior
- Status

#### Percentual do total

```text
% do total = carga do servidor / total distribuído × 100
```

#### Variação vs anterior

```text
Delta = carga atual - carga no snapshot anterior
```

### Aba Perfil do servidor

Permite selecionar um servidor e visualizar:

- Carga atual.
- Total de processos recebidos.
- Total finalizado/saído.
- Processos em aberto.
- Média de permanência.
- Evolução histórica da carteira.

#### Total recebidos

Quantidade de protocolos que já passaram por aquela atribuição no histórico analisado.

#### Total finalizados/saídas

Quantidade de protocolos que estiveram com aquele servidor e não estão mais na data de referência.

#### Média de permanência

```text
Média de permanência = soma das durações dos processos que saíram / quantidade de processos que saíram
```

---

## 16. Tela Indicadores Mensais

### Objetivo da tela

Acompanhar indicadores mensais do SEI por setor.

Essa tela é diferente das telas diárias. Ela trabalha com dados mensais importados ou lançados manualmente.

### Seis indicadores mensais

1. Processos gerados no período.
2. Processos com tramitação no período.
3. Processos com andamento fechado na unidade ao final do período.
4. Processos com andamento aberto na unidade ao final do período.
5. Documentos gerados no período.
6. Documentos externos no período.

### Dashboard mensal

Permite filtrar por:

- Setor.
- Indicador em foco.
- Ano.
- Mês.

### Cards

#### Proc. gerados

Soma do indicador "Processos gerados no período" para o último mês disponível no recorte.

#### Proc. tramitação

Soma do indicador "Processos com tramitação no período".

#### Proc. fechados

Soma do indicador "Processos com andamento fechado na unidade ao final do período".

#### Proc. abertos

Soma do indicador "Processos com andamento aberto na unidade ao final do período".

#### Docs gerados

Soma do indicador "Documentos gerados no período".

#### Docs externos

Soma do indicador "Documentos externos no período".

#### Média histórica

Média do indicador selecionado no recorte filtrado.

```text
Média histórica = soma dos valores do indicador / quantidade de registros do indicador
```

### Gráfico Evolução mensal do indicador em foco

Mostra a série histórica do indicador selecionado.

Se nenhum setor for selecionado, mostra séries por setor.

### Gráfico Indicadores no último mês disponível

Mostra os seis indicadores consolidados no mês mais recente do recorte.

### Tabela Resumo do último mês

Mostra por setor:

- Processos gerados.
- Processos com tramitação.
- Processos fechados.
- Processos abertos.
- Documentos gerados.
- Documentos externos.

### Aba Atualização mensal

Disponível para administradores.

Permite:

- Importar CSV histórico mensal.
- Lançar manualmente os seis indicadores de um setor/mês.
- Editar valores já cadastrados.
- Conferir histórico paginado.

---

## 17. Tela Busca Global

### Objetivo da tela

Localizar um processo pelo número do protocolo e mostrar sua trajetória inferida.

### Como buscar

Digite o protocolo completo ou parte dele.

O sistema procura protocolos que contenham o texto digitado.

### O que o resultado mostra

Para cada protocolo encontrado:

- Protocolo.
- Tipo.
- Setor atual.
- Atribuição atual.
- Primeira aparição.
- Última aparição.
- Histórico de movimentações.

### Histórico de movimentações

O histórico é construído comparando registros do processo ao longo dos snapshots.

Uma nova linha é criada quando muda:

- Setor.
- Atribuição.

Colunas:

- Setor
- Atribuição
- Tipo
- Entrada
- Saída
- Duração
- Status

### Como a duração é calculada

```text
Duração = data de saída - data de entrada
```

Se o processo ainda estiver ativo, o cálculo usa a data atual como referência visual.

---

## 18. Tela Usuários SEI

### Objetivo da tela

Gerenciar o DE-PARA de nomes e usuários do SEI.

Disponível apenas para administradores.

### Por que o DE-PARA é importante

No SEI, uma atribuição pode aparecer com variações:

- Nome completo.
- Nome abreviado.
- Usuário/login.
- Grafia diferente.

O DE-PARA consolida essas variações em um nome canônico.

### O que a tela permite

- Cadastrar vínculo manual.
- Importar planilha em lote.
- Visualizar base atual.
- Editar nomes e usuários cadastrados.
- Vincular cada usuário SEI a um ou mais setores.
- Inferir setores automaticamente a partir dos processos históricos.
- Excluir vínculos.

### Campos

- Nome canônico: nome principal usado nos painéis.
- Nome SEI: forma como aparece no SEI.
- Usuário SEI: login/usuário.

### Como o sistema normaliza

O sistema:

- Remove acentos para comparação.
- Ignora diferença entre maiúsculas e minúsculas.
- Reduz espaços duplicados.
- Compara nome, nome SEI e usuário SEI.

Após alterar o DE-PARA, o sistema sincroniza os processos e limpa o cache analítico.

### Setores dos usuários SEI

Cada usuário SEI pode ser vinculado a uma ou mais divisões.

Esse vínculo é usado para filtrar:

- O filtro **Atribuição** nas páginas analíticas.
- O filtro **Servidor** na página Servidores.

Exemplo conceitual:

- Um usuário com acesso apenas a uma divisão deve ver no filtro apenas atribuições vinculadas àquela divisão.
- Um servidor que atua em duas divisões pode ser vinculado às duas.

### Inferir setores

O botão **Inferir setores** analisa os processos históricos e vincula automaticamente cada usuário SEI aos setores onde ele aparece.

Essa inferência serve como ponto de partida. Depois, o administrador pode revisar e ajustar manualmente.

---

## 19. Tela Administração

### Objetivo da tela

Gerenciar acessos, consultar uploads recentes e acompanhar auditoria.

Disponível apenas para administradores.

### Cards

#### Usuários cadastrados

Total de contas existentes no sistema.

#### Snapshots importados

Quantidade exibida dos uploads recentes carregados na tela administrativa.

#### Eventos de auditoria

Total de registros de auditoria salvos.

### Novo usuário

Permite criar:

- Nome.
- E-mail.
- Senha.
- Perfil administrador ou usuário comum.

### Usuários cadastrados

Lista:

- Nome.
- E-mail.
- Perfil.
- Divisões liberadas.
- Data de criação.
- Ações de divisões, permissões e exclusão.

O sistema impede excluir a própria conta e impede remover o último administrador.

### Divisões por usuário

Permite definir quais setores um usuário comum pode visualizar.

Administradores têm acesso total por padrão. Usuários comuns só devem enxergar dados dos setores liberados.

Esse controle afeta:

- Central Executiva.
- Dashboard.
- Entradas e Saídas.
- Produtividade.
- Múltiplos Setores.
- Atribuições.
- Score de Risco.
- Servidores.
- Indicadores Mensais.
- Histórico de uploads.
- Badge de saúde dos dados.

### Permissão para enviar relatórios

Além das divisões liberadas, o administrador pode marcar se o usuário comum pode enviar relatórios.

Essa permissão controla:

- Exibição da página Enviar Relatório no menu.
- Autorização no backend para aceitar uploads.
- Bloqueio de upload de setor não permitido.

### Últimos uploads

Mostra referência rápida dos 30 snapshots mais recentes.

### Log de auditoria

Registra ações críticas:

- Upload importado.
- Upload substituído.
- Upload excluído.
- Data de upload alterada.
- Usuário criado.
- Usuário excluído.
- Divisões de usuário atualizadas.
- Permissão de upload alterada.
- Senha alterada.
- DE-PARA criado.
- DE-PARA excluído.
- DE-PARA importado.
- Setores de usuário SEI atualizados.
- Setores de usuário SEI inferidos.

Paginação:

- 50 registros por página.

---

## 20. Tela Minha Conta

### Objetivo da tela

Exibir dados básicos do usuário logado.

Mostra:

- Nome.
- E-mail.
- Perfil.

Serve como referência para o próprio usuário verificar com qual conta entrou.

---

## 21. Tela Documentação

### Objetivo da tela

Apresentar documentação técnica e operacional dentro da própria plataforma.

Ela cobre:

- O que é o AnalyticSEI.
- Arquitetura.
- Stack tecnológica.
- Modelo de dados.
- Backend e endpoints.
- Frontend.
- Automações.
- Segurança.
- Configuração.
- Manutenção.
- Histórico de evolução.

Essa tela é mais técnica que este manual, mas é útil para manutenção do projeto.

---

## 22. Relatórios e automações

### 21.1. Upload diário automático

Workflow: **Upload diário SEI → AnalyticSEI**.

Horário:

- Segunda a sexta.
- 19:00 no horário de Fortaleza/Brasília.

O que faz:

- Acessa o SEI com credenciais configuradas nos secrets do GitHub.
- Coleta relatórios dos setores.
- Envia os CSVs para a API do AnalyticSEI.
- Publica diagnóstico se falhar.
- Envia e-mail de falha quando necessário.

### 21.2. Relatório diário por e-mail

Workflow: **Relatório diário AnalyticSEI — e-mail**.

Horário:

- Segunda a sexta.
- 19:30 no horário de Fortaleza/Brasília.

Regra importante:

- O relatório diário só é enviado se o upload diário tiver rodado com sucesso antes, no mesmo dia.

Conteúdo:

- Total de processos ativos.
- Saldo do dia.
- Entradas.
- Saídas.
- Resumo por setor.
- Alertas de processos críticos.

### 21.3. Relatório semanal

Workflow: **Relatório semanal SEI Analytics**.

Horário:

- Sexta-feira.
- 20:00 no horário de Fortaleza/Brasília.

Conteúdo:

- Indicadores consolidados da semana.
- Comparações.
- Alertas.
- Síntese para acompanhamento periódico.

### 21.4. Alertas de processos críticos

Workflow: **Alertas de processos críticos — SEI Analytics**.

Horário:

- Sexta-feira.
- 21:00 no horário de Fortaleza/Brasília.

Regra:

- Envia e-mail apenas se houver processos acima do limite crítico definido.

### 21.5. Keep-alive da API

Workflow: **Keep Render alive**.

Frequência:

- A cada 10 minutos.

O que faz:

- Chama o endpoint `/api/ping`.
- Esse endpoint não consulta o banco.
- Serve para reduzir o tempo de espera causado pelo plano gratuito do Render.

---

## 23. Como interpretar corretamente os indicadores

### 22.1. O sistema trabalha por inferência

Muitos indicadores são inferidos comparando snapshots.

Isso significa:

- O sistema sabe que um processo estava em uma carteira em uma data.
- O sistema sabe que ele não está mais na data seguinte.
- A partir disso, infere saída, produção ou encerramento do span.

Ele não lê diretamente uma "ação concluída" no SEI, a menos que esse dado esteja no CSV.

### 22.2. Entradas e saídas não são necessariamente entrada/saída formal no SEI

No AnalyticSEI:

- Entrada significa apareceu em uma carteira/setor.
- Saída significa deixou de aparecer em uma carteira/setor.

Isso é ótimo para gestão de carteira, mas precisa ser interpretado como leitura operacional do snapshot.

### 22.3. Produtividade é produção estimada

Produção no sistema significa que processos deixaram a carteira de uma atribuição.

Não mede:

- Complexidade do processo.
- Qualidade da análise.
- Tempo gasto.
- Interrupções.
- Demandas fora do SEI.

Por isso, deve ser usada como indicador de fluxo, não como avaliação isolada de pessoas.

### 22.4. Lead time é tempo de permanência na carteira

Não é necessariamente:

- Tempo total do processo desde a autuação.
- Prazo legal.
- Tempo total de vida administrativa.

Ele mede permanência inferida entre snapshots.

### 22.5. Score de risco é priorização, não sentença

O score ajuda o gestor a olhar primeiro para os processos com maior combinação de sinais.

Ele deve apoiar decisão humana, não substituir análise do gestor.

---

## 24. Glossário

### Snapshot

Fotografia da carteira de processos de um setor em uma data.

### Protocolo

Número do processo no SEI.

### Setor

Unidade/divisão responsável pelo snapshot.

### Atribuição

Responsável ou carteira indicada no SEI.

### Atribuição normalizada

Nome consolidado após aplicação do DE-PARA de usuários SEI.

### Carteira

Conjunto de processos sob um setor ou atribuição.

### Entrada

Processo que passou a aparecer em uma carteira entre dois snapshots.

### Saída

Processo que deixou de aparecer em uma carteira entre dois snapshots.

### Saldo

Entradas menos saídas.

### Span

Intervalo contínuo em que um processo permanece em determinada carteira/setor.

### Span aberto

Processo ainda presente na carteira no snapshot atual.

### Span fechado

Processo que deixou a carteira em algum snapshot posterior.

### Lead time

Tempo estimado de permanência de processos que saíram da carteira.

### Média

Soma dos valores dividida pela quantidade de valores.

### Mediana

Valor central de uma lista ordenada.

### P90

Percentil 90. Indica o valor até o qual estão 90% dos casos.

### Desvio padrão

Medida de dispersão dos valores em relação à média.

### Desvio-Z

Medida que indica quanto uma carga está acima ou abaixo da média em unidades de desvio padrão.

### Score de risco

Pontuação composta que combina tempo, histórico, ausência de atribuição, múltiplos setores e tendência do setor.

---

## 25. Boas práticas para gestores

### Antes de interpretar qualquer painel

Verifique o selo de frescor dos dados.

Se houver alerta de dados:

- Confirme se todos os setores enviaram relatório.
- Veja se algum setor está defasado.
- Confira se o volume do snapshot não caiu muito em relação ao histórico.

### Para acompanhamento diário

Use esta ordem:

1. Central Executiva.
2. Score de Risco.
3. Pauta Prioritária.
4. Atribuições.
5. Entradas e Saídas.
6. Produtividade.

### Para análise semanal

Use:

1. Dashboard.
2. Pauta Prioritária.
3. Servidores.
4. Indicadores Mensais, quando aplicável.
5. Relatório semanal por e-mail.

### Para auditoria e manutenção

Use:

1. Enviar Relatório.
2. Administração.
3. Usuários SEI.
4. Documentação.

---

## 26. Limitações conhecidas

### Dependência dos snapshots

Se o CSV não foi enviado, o sistema não tem como saber o que aconteceu naquele dia.

### Finais de semana e feriados

Se não houver upload nesses dias, o sistema trabalha com as datas disponíveis.

### Cadência diferente por setor

Alguns cálculos usam índice por setor para evitar interpretar ausência de upload como saída falsa.

### Campos inconsistentes no CSV

Campos como ponto de controle, observações ou atribuição podem variar conforme o SEI e a forma de exportação.

### Forecasting não é previsão garantida

As tendências são estimativas simples baseadas no ritmo recente.

### Score depende de histórico

O fator de P90 só funciona plenamente quando há histórico suficiente de processos que saíram das carteiras.

---

## 27. Resumo executivo

O AnalyticSEI entrega três camadas de gestão:

### Camada 1: Confiabilidade dos dados

- Uploads.
- Frescor dos snapshots.
- Setores defasados.
- Alertas de qualidade.

### Camada 2: Gestão operacional

- Processos ativos.
- Entradas e saídas.
- Produtividade estimada.
- Atribuições.
- Processos em múltiplos setores.
- Carga por servidor.

### Camada 3: Inteligência gerencial

- Central Executiva.
- Lead time.
- P90.
- Tendências estimadas.
- Score de Risco.
- Alertas por e-mail.

A principal força do sistema está em transformar relatórios estáticos do SEI em uma visão contínua de carteira, fluxo, risco e tendência para apoiar decisões de gestão.
