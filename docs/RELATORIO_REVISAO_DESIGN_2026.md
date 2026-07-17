# Relatório de revisão de design — AnalyticSEI

**Data da análise:** 16/07/2026

**Escopo:** arquitetura de informação, navegação, layout, filtros, tabelas, gráficos, responsividade e consistência visual.

**Premissa:** preservar a identidade central do AnalyticSEI: azul institucional, laranja, amarelo, fundos claros, tipografia Plus Jakarta Sans e caráter operacional.

## 1. Resumo executivo

O AnalyticSEI tem boa identidade, cobertura funcional madura e componentes reconhecíveis. O principal problema atual não é falta de recursos, mas a fragmentação: 15 entradas de menu têm peso visual semelhante, páginas analíticas próximas disputam espaço, o filtro global consome muita altura e várias telas repetem título, hero, KPIs, gráficos e tabela sem uma hierarquia comum.

A recomendação aprovada é **não redesenhar a marca nem transformar o sistema em uma interface decorativa**. A evolução deve concentrar-se em quatro movimentos:

1. Reduzir o menu principal por agrupamento e por abas contextuais.
2. Tornar filtros, títulos e ações mais compactos e orientados ao trabalho diário.
3. Padronizar gráficos e tabelas como instrumentos de decisão.
4. Organizar a jornada operacional: identificar problema → priorizar → atribuir → acompanhar na Pauta.

Foi escolhida a direção **Gestão por Prioridades**, com consolidações conservadoras e preservação das URLs e dos fluxos já conhecidos.

## 2. Arquitetura de informação recomendada

### Menu principal proposto

**Operacional**

- **Área de Trabalho** — visão inicial orientada a exceções e próximos passos.
- **Central Executiva** — permanece como análise gerencial completa.
- **Pauta Prioritária**, **Score de Risco** e **Atribuições** — permanecem independentes.

**Análise**

- **Desempenho** — abas contextuais `Fluxo` e `Produtividade`.
- **Inconsistências** — evolução de Múltiplos Setores.
- **Pessoas** — evolução de Servidores, preservando suas abas internas.
- **Indicadores Mensais** — permanece como módulo próprio.

**Administração** — condicional por permissão

- **Gestão de Dados** — navegação entre novo envio e histórico.
- **Administração** — área integrada com acesso à Base SEI, auditoria e parâmetros de risco.

**Utilidades**, no rodapé ou menu do usuário

- Minha Conta.
- Documentação.
- Sair.

### Consolidações avaliadas

| Páginas atuais | Decisão | Justificativa |
|---|---|---|
| Central Executiva + Dashboard | **Não fundir** | Dashboard evolui para Área de Trabalho; Central Executiva preserva a análise completa. |
| Entradas e Saídas + Produtividade | **Unificar em Desempenho** | São análises temporais complementares e usam os mesmos filtros. |
| Atribuições + Score de Risco | **Manter independentes** | Os fluxos diários são distintos e já estão consolidados no uso. |
| Múltiplos Setores | **Renomear Inconsistências** | Mantém a rota e a função, com nomenclatura orientada ao problema tratado. |
| Pauta Prioritária | **Manter própria** | Possui sessões, prazos, responsáveis, notas, estados e ações transacionais. |
| Servidores | **Manter, renomear Pessoas** | O objeto de análise muda de processo para pessoa; as abas internas já fazem sentido. |
| Indicadores Mensais | **Manter própria** | Cadência, fonte e interpretação diferem dos snapshots diários. |
| Enviar Relatório + histórico | **Consolidar visualmente em Gestão de Dados** | Novo envio e histórico passam a compartilhar a mesma navegação. |
| Usuários SEI + Administração | **Integrar por abas contextuais** | Base SEI fica acessível dentro da área administrativa, preservando a rota. |
| Minha Conta + Documentação | **Mover para perfil/ajuda** | São utilidades, não módulos operacionais. |
| StaleProcessesPage não roteada | **Remover ou integrar** | É código sem destino atual; o conceito cabe em Risco ou Inconsistências. |

## 3. Direção visual recomendada

### Identidade preservada

- Azul principal `#273168`, azul escuro `#1c2350`/`#111840`.
- Laranja `#f39320`, amarelo `#febb12`.
- Azul claro `#81c7ee`, verde `#1a7a50`, vermelho `#bf3535` apenas com função semântica.
- Fundo `#eef0f8`, painéis brancos e Plus Jakarta Sans.

### Ajustes de sistema

- Criar uma escala única de espaçamento, altura de controle, título e densidade de tabela.
- Reduzir heróis repetitivos. O título do topbar e o título do hero não devem dizer a mesma coisa.
- Reservar o hero escuro para páginas com contexto operacional real: Área de Trabalho, Risco e Pauta.
- Padronizar botões com ícones Lucide, tooltips e hierarquia `primário`, `secundário`, `destrutivo`.
- Trocar as abreviações de duas letras do menu recolhido por ícones com tooltip.
- Eliminar estilos inline recorrentes e consolidar variantes nos componentes compartilhados.

## 4. Navegação e topbar

### Sidebar

- Introduzir rótulos de grupo e seções recolhíveis: Análise, Gestão e Administração.
- Exibir no máximo 7 destinos primários para usuários comuns.
- Manter Pauta Prioritária visível e próxima de Processos.
- Usar o rodapé para perfil, ajuda e sair.
- Quando recolhida, mostrar somente ícones consistentes; nunca siglas como `CE`, `DA`, `EN`.
- No mobile, usar drawer temporário com o mesmo agrupamento, sem alterar a ordem mental.

### Topbar

- Tornar a busca um comando compacto (`Buscar processo`) expansível ou acionável por atalho.
- Condensar atualização dos dados em um badge com tooltip para detalhes dos setores.
- Substituir o cartão textual do usuário por avatar/iniciais com menu.
- Evitar quebra em duas linhas: em larguras menores, busca e frescor migram para uma segunda faixa controlada.

## 5. Filtros

O filtro compartilhado é funcional, mas alto e visualmente dominante. A proposta é uma **barra de escopo compacta e sticky**:

- Primeira linha: Referência, Setor, Tipo, Atribuição e ação `Mais filtros`.
- Período inicial/final aparece somente quando o usuário escolhe o modo `Período`.
- Exibir filtros ativos como chips removíveis abaixo da barra.
- Mostrar `Limpar filtros` apenas quando houver alteração.
- Manter Atribuição dependente do Setor e comunicar carregamento/ausência de opções.
- Persistir o escopo ao alternar abas do mesmo módulo; confirmar antes de carregar volume excessivo.
- Em páginas onde um campo não afeta o cálculo, não exibi-lo apenas por uniformidade.

## 6. Tabelas e gráficos

### Tabelas

- Criar um componente único de tabela operacional com cabeçalho sticky, ordenação, paginação, densidade e estado vazio.
- Definir prioridade de colunas para mobile e mover detalhes secundários para painel lateral, evitando rolagem horizontal como única estratégia.
- Manter ações primárias visíveis e agrupar ações raras no menu `…`.
- Oferecer seleção múltipla apenas quando existir ação em lote.
- Fixar protocolo e status em tabelas largas de Pauta, Risco e Atribuições.

### Gráficos

- Manter a paleta semântica já adotada nos gráficos: azul institucional, laranja, amarelo, verde e vermelho conforme o significado.
- Padronizar a função de cada cor entre páginas, sem introduzir novas famílias cromáticas.
- Padronizar eixos, tooltip, legenda, formatação numérica e altura dos painéis.
- Mostrar subtítulo com pergunta respondida pelo gráfico, não apenas o nome da métrica.
- Oferecer tabela acessível para gráficos críticos e respeitar `prefers-reduced-motion`.
- Evitar pizza quando houver muitas categorias; preferir barras ordenadas.

## 7. Revisão página por página

### Login

- Manter a identidade de marca, mas reduzir texto institucional concorrente com o formulário.
- Adicionar mostrar/ocultar senha, mensagem de erro próxima ao campo e estado claro de envio.
- Garantir foco inicial, contraste e navegação completa por teclado.

### Central Executiva

- Permanecer como página própria para admin e gestores.
- Priorizar exceções, atrasos, risco, pauta e capacidade; análises secundárias ficam recolhíveis.
- Cada alerta deve oferecer próximo passo claro: abrir processo, risco, atribuição ou pauta.

### Dashboard

- Evoluir para `Área de Trabalho`, página inicial orientada a prioridades.
- Exibir uma fila de ação com atalhos para Inconsistências, Risco e Pauta antes dos gráficos.
- Reduzir KPIs que repetem o mesmo total; destacar variação e contexto.
- Reordenar gráficos conforme leitura: volume → distribuição → evolução → ranking.

### Enviar Relatório

- Integrar em Gestão de Dados com abas `Novo envio` e `Histórico`.
- Exibir fluxo em etapas: arquivo → validação → resumo → confirmação.
- Antes do envio, mostrar setor/data detectados, linhas válidas e erros bloqueantes.

### Entradas e Saídas

- Virar aba `Fluxo` de Desempenho.
- Destacar saldo, tendência e setores responsáveis pela variação.
- Comparação temporal deve usar a mesma escala e permitir alternar total/setor.

### Produtividade

- Virar aba `Produtividade` de Desempenho.
- Separar claramente volume de saída de eficiência; quantidade sem denominador pode induzir leitura incorreta.
- Ranking deve permitir setor, período e mínimo de casos, com explicação da métrica.

### Múltiplos Setores

- Permanecer como página própria, renomeada `Inconsistências` no menu.
- Tratar a tela como fila de verificação: criticidade, setores envolvidos, idade e ação.
- Manter Excel/PDF, mas agrupar em menu Exportar quando a largura for limitada.

### Atribuições

- Permanecer como página própria e ponto inicial da seleção em lote para a Pauta.
- Tornar filtros por faixa e busca parte do cabeçalho da tabela, não um segundo sistema de filtros desconectado.
- Fixar seleção, protocolo e ação Pauta; indicar claramente o que já está em sessão ativa.

### Score de Risco

- Permanecer como página própria, próxima de Atribuições e Pauta na navegação.
- Mostrar fórmula resumida e componentes do score sob demanda, sem sobrecarregar todas as linhas.
- Usar escala semântica consistente e permitir ordenar por impacto, dias e score.

### Pauta Prioritária

- Permanecer destino próprio e operacional.
- Fixar no topo seletor de sessão, situação, prazo e progresso; ações administrativas no menu `…`.
- Manter a tabela densa, com colunas ordenáveis, cabeçalho sticky e prioridade para Protocolo, Responsável, Prazo, Dias Prazo e Status.
- Em telas estreitas, abrir detalhes/notas em drawer por processo em vez de comprimir todas as colunas.
- Diferenciar visualmente prazo da sessão e prazo individual do item.

### Servidores

- Renomear para `Pessoas` e manter abas `Carga de trabalho` e `Perfis`.
- Na carga, destacar desequilíbrios e capacidade; no perfil, mostrar histórico e composição.
- Evitar usar ranking sem contexto de volume/tipo de processo.

### Indicadores Mensais

- Manter módulo próprio pela cadência mensal.
- Para usuários comuns, mostrar apenas o painel; mover `Gestão` para Administração > Dados mensais.
- Exibir competência, cobertura e data de atualização no cabeçalho.

### Usuários SEI

- Mover para Administração > `Base SEI`.
- Separar em abas: `Base atual`, `Aliases e mesclagem`, `Importação` e `Pendências`.
- Mostrar origem e última atualização de cada pessoa; destacar novos nomes detectados automaticamente.

### Administração

- Reorganizar em `Acessos`, `Dados`, `Base SEI`, `Auditoria` e `Parâmetros de risco`.
- Manter badges com contagem apenas quando indicarem pendência ou mudança, não volume estático.
- Tabelas administrativas devem compartilhar busca, ordenação e paginação.

### Minha Conta

- Remover do menu principal e abrir pelo menu do usuário.
- Separar perfil e segurança; informar requisitos da senha antes da tentativa.

### Busca de Processo

- Manter rota de resultado, mas abrir a busca pela topbar/atalho global.
- Resultado deve começar por situação atual e depois mostrar a linha do tempo.
- Oferecer atalhos para Risco e Pauta quando o processo estiver elegível.

### Documentação

- Manter pública e fora do shell autenticado.
- Adicionar busca no conteúdo, sumário sticky, destaque da versão e changelog.
- Reduzir a altura do cabeçalho e alinhar sua densidade à aplicação.

### Logout

- Não precisa de página visual própria. Deve executar saída e redirecionar, com fallback curto em caso de falha.

## 8. Acessibilidade e responsividade

- Contraste WCAG AA em textos muted, badges e estados desabilitados.
- Foco visível em links, botões, tabs, campos, cabeçalhos ordenáveis e menus.
- Tabs com semântica ARIA e navegação por setas.
- Não depender apenas de cor para risco, prazo ou status; manter texto/ícone.
- Alvos de toque de pelo menos 40–44 px no mobile.
- Tabelas com resumo acessível e alternativa em lista/drawer.
- Testar 1440, 1280, 1024, 768 e 390 px; hoje a estratégia predominante é apenas quebrar grids e rolar tabelas.

## 9. Plano de execução recomendado

### Fase A — Fundação, baixo risco

1. Tokens, ícones e variantes de botão.
2. Sidebar agrupada e topbar compacta.
3. FilterBar v2 com escopo persistente e chips.
4. SmartTable e padrões de gráfico.

### Fase B — Hierarquia Gestão por Prioridades

1. Área de Trabalho orientada a exceções e ações.
2. Desempenho com Fluxo e Produtividade relacionados por abas.
3. Pauta, Risco e Atribuições preservados como destinos próprios.
4. URLs antigas e links internos preservados.

### Fase C — Fluxos operacionais

1. Pauta Prioritária responsiva e com tabela sticky.
2. Gestão de Dados unificada.
3. Administração + Base SEI.
4. Pessoas e Indicadores Mensais.

### Fase D — Qualidade

1. Acessibilidade automatizada e manual.
2. Screenshots de regressão em desktop/mobile.
3. Testes de navegação, filtros persistentes e permissões.
4. Métricas de uso antes/depois: cliques até a Pauta, tempo para localizar processo e taxa de uso dos módulos.

## 10. Protótipos comparativos

- [Reprodução do Dashboard atual](https://p.superdesign.dev/draft/c4c973df-f937-4bdd-83bc-dbe66e027223)
- [Alternativa 1 — Dashboard Analítico Consolidado](https://p.superdesign.dev/draft/1f30417e-bf08-473f-860b-e512b82d9e60)
- [Alternativa 2 — Gestão por Prioridades](https://p.superdesign.dev/draft/435f15c9-5186-4830-85a5-b71a1a59eaa7)
- [Projeto completo no Superdesign](https://superdesign.dev/teams/e05baa88-0e9f-4f2d-bb16-f722a4c31a41/projects/37518582-c258-479a-b256-e0555db7da53)

## 11. Recomendação final

Adotar a **Alternativa 2 — Gestão por Prioridades**, com menu agrupado e consolidações conservadoras. A identidade atual permanece; o ganho vem de aproximar diagnóstico e ação sem obrigar o usuário a reaprender Pauta, Risco e Atribuições.

Implementação aprovada em 16/07/2026, mantendo APIs, permissões e rotas existentes.
