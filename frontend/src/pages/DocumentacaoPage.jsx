import "./DocumentacaoPage.css";
import ArchDiagram from "./documentacao/ArchDiagram";
import Callout from "./documentacao/Callout";
import Checklist from "./documentacao/Checklist";
import DocSection from "./documentacao/DocSection";
import DocTable from "./documentacao/DocTable";
import FeatureCard from "./documentacao/FeatureCard";
import MethodBadge from "./documentacao/MethodBadge";
import PillTag from "./documentacao/PillTag";
import TocSidebar from "./documentacao/TocSidebar";

/* ── Dados ─────────────────────────────────────── */

const DOC_VERSION = "2.4";
const DOC_UPDATED = "Julho 2026";
const CHAPTER_COUNT = 12;
const DATABASE_TABLE_COUNT = 12;

const FEATURES = [
  { icon: "🎯", title: "Central Executiva", desc: "Prioridades do dia, saúde dos dados, KPIs principais, sparklines e tempo de permanência" },
  { icon: "📊", title: "Dashboard principal", desc: "KPIs, distribuição por setor/tipo, rankings e evolução diária" },
  { icon: "↔️", title: "Entradas e saídas", desc: "Comparativo de fluxo entre snapshots consecutivos" },
  { icon: "⚡", title: "Produtividade", desc: "Processos recebidos, finalizados e tempo médio por servidor" },
  { icon: "⏱️", title: "Tempo de permanência", desc: "Lead time estimado com média, mediana, P90, faixas por duração e ranking por setor" },
  { icon: "📈", title: "Tendências estimadas", desc: "Forecasting simples com projeção de estoque ativo, tendência por setor e estimativa de críticos" },
  { icon: "🛡️", title: "Score de Risco", desc: "Ranking de processos por prioridade de atenção, com breakdown dos fatores do score" },
  { icon: "✅", title: "Pauta Prioritária", desc: "Sessões semanais com cronograma, responsáveis, notas, PDF, métricas e resolução automática por snapshot" },
  { icon: "📋", title: "Atribuições", desc: "Carteira completa com flags de criticidade (6 faixas até 90d+)" },
  { icon: "⚖️", title: "Servidores", desc: "Balanceamento de carga, sobrecarga e perfil longitudinal" },
  { icon: "🔀", title: "Múltiplos setores", desc: "Detecção de processos em mais de um setor no mesmo dia, com exportação Excel/PDF" },
  { icon: "📅", title: "Indicadores mensais", desc: "Painel histórico com importação de CSV e lançamento manual" },
  { icon: "🔐", title: "Controle por divisão", desc: "Usuários comuns visualizam apenas os setores liberados pelo administrador" },
  { icon: "📤", title: "Permissão de upload", desc: "Envio manual restrito a usuários habilitados e aos setores permitidos" },
  { icon: "🧭", title: "Usuários SEI por setor", desc: "Atribuições e servidores filtrados conforme vínculos administrativos por divisão" },
  { icon: "🔍", title: "Busca global", desc: "Histórico completo de movimentações de qualquer protocolo" },
  { icon: "🔔", title: "Alertas por e-mail", desc: "Notificação semanal às sextas, 21:00 BRT, para processos críticos (>30, >45, >90 dias)" },
  { icon: "🔔", title: "Notificação in-app", desc: "Sino com badge em tempo real de processos ≥45 dias e itens pendentes da Pauta Prioritária" },
  { icon: "🤖", title: "Upload automático", desc: "Script Playwright que acessa o SEI e envia dados sem intervenção (19h BRT)" },
  { icon: "📨", title: "Relatório diário", desc: "E-mail automático seg–sex às 19:30 BRT com ativos, fluxo do dia por setor e alertas de processos críticos" },
  { icon: "📧", title: "Relatório semanal", desc: "E-mail automático toda sexta com resumo dos indicadores da semana" },
  { icon: "📄", title: "Exportação PDF / Excel", desc: "Relatórios de Atribuições e Múltiplos Setores com identidade visual Progep/UFC" },
  { icon: "🔒", title: "Log de auditoria", desc: "Registro de todas as ações críticas: uploads, exclusões, trocas de senha" },
];

const BACKEND_STACK = {
  headers: ["Tecnologia", "Versão", "Função"],
  rows: [
    ["Python", "3.12", "Linguagem principal"],
    ["FastAPI", "0.115", "Framework web / API REST"],
    ["SQLAlchemy", "2.0", "ORM / camada de banco"],
    ["Alembic", "1.14", "Migrações formais de schema"],
    ["Pandas", "2.2", "Processamento de CSVs e cálculos analíticos"],
    ["Passlib + bcrypt", "1.7 / 4.0", "Hash de senhas"],
    ["python-jose", "3.3", "JWT (tokens de autenticação)"],
    ["psycopg2-binary", "2.9", "Driver PostgreSQL"],
    ["openpyxl + xlrd", "—", "Leitura de planilhas Excel"],
  ],
};

const FRONTEND_STACK = {
  headers: ["Tecnologia", "Versão", "Função"],
  rows: [
    ["React", "18.3", "Framework UI"],
    ["Vite", "5.4", "Build tool"],
    ["React Router", "6.30", "Navegação SPA"],
    ["Recharts", "2.15", "Gráficos (barras, linhas, pizza)"],
    ["Axios", "1.8", "Chamadas HTTP para a API"],
    ["SheetJS (xlsx)", "0.18", "Exportação para Excel"],
    ["jsPDF + jspdf-autotable", "2.5 / 3.8", "Exportação para PDF"],
  ],
};

const SCRIPTS_STACK = {
  headers: ["Tecnologia", "Função"],
  rows: [
    ["Python + Playwright", "Automação do navegador para extração de dados do SEI"],
    ["httpx", "Chamadas HTTP assíncronas (upload e relatório)"],
    ["smtplib", "Envio de e-mails via SMTP (Google Workspace)"],
  ],
};

const WORKFLOWS = [
  { name: "keep-alive.yml", freq: "A cada 10 minutos (24h/dia)", desc: "Pinga /api/ping (endpoint leve sem banco) para manter o Render ativo. Sem isso, o plano gratuito hiberna após 15 min e gera cold start lento." },
  { name: "daily-upload.yml", freq: "Seg–Sex 19:00 BRT", desc: "Playwright headless: login no SEI, troca de setor, coleta todas as páginas (100/pág), gera CSV e faz upload via API key. Notifica por e-mail se falhar." },
  { name: "daily-report.yml", freq: "Seg–Sex 19:30 BRT", desc: "Antes de enviar, executa check_daily_upload_success.py para confirmar sucesso do daily-upload no dia. Se estiver OK, coleta /api/reports/daily-summary e envia e-mail HTML compacto." },
  { name: "weekly-report.yml", freq: "Sexta 20:00 BRT", desc: "Coleta dados do dashboard, balanceamento e alertas via API key e envia e-mail HTML com identidade visual Progep/UFC." },
  { name: "critical-alerts.yml", freq: "Sexta 21:00 BRT", desc: "Verifica processos >30d. NÃO envia e-mail se não houver processos críticos (anti-spam). Destaque especial para situação extrema >90d." },
];

const MANUTENCAO = [
  { title: "Upload manual", desc: "Acessar Enviar Relatório → selecionar setor permitido, data e arquivo CSV exportado do SEI. A tela só aparece para admins ou usuários habilitados para upload." },
  { title: "Corrigir data de upload", desc: "Em Enviar Relatório, clicar em Editar data na linha do upload. O sistema verifica conflitos automaticamente." },
  { title: "Remover snapshot incorreto", desc: "Em Enviar Relatório, clicar em Excluir. Todos os processos daquele snapshot são removidos." },
  { title: "Adicionar servidor ao DE-PARA", desc: "Em Usuários SEI, preencher o formulário. A plataforma sincroniza todos os processos históricos automaticamente." },
  { title: "Editar servidor no DE-PARA", desc: "Em Usuários SEI, clicar em Editar na tabela, ajustar nome canônico, nome SEI ou usuário SEI e salvar. Os processos são ressincronizados automaticamente." },
  { title: "Unir nomes históricos de servidor", desc: "Em Usuários SEI, escolher o usuário principal e informar o nome antigo ou alternativo. O alias passa a consolidar filtros, gráficos e rankings sem alterar o texto bruto importado do SEI." },
  { title: "Vincular usuário SEI a setores", desc: "Em Usuários SEI, abrir o editor de Setores ou usar Inferir setores. Esses vínculos filtram listas de Atribuição e Servidor para usuários restritos." },
  { title: "Criar novo usuário", desc: "Em Administração, preencher o formulário com nome, e-mail, senha e nível de acesso (admin ou não)." },
  { title: "Liberar divisões e upload", desc: "Em Administração → Acessos, configurar quais divisões cada usuário comum pode visualizar e se ele pode enviar relatórios." },
  { title: "Lançar indicadores mensais", desc: "Em Indicadores Mensais → aba Atualização mensal, selecionar setor, ano e mês, preencher os 6 indicadores." },
  { title: "Verificar processos críticos", desc: "O sino na topbar mostra a contagem de processos ≥45d. Clicar abre o resumo. Detalhes completos em /atribuicoes." },
  { title: "Montar pauta prioritária semanal", desc: "Em Pauta Prioritária, criar sessão com início, reunião e prazo, adicionar processos do Score de Risco ou das páginas Risco/Atribuições, atribuir responsável e registrar nota de gestão." },
  { title: "Editar cronograma da pauta", desc: "Administradores podem editar título, início, reunião, prazo da pauta e observações pelo editor inline no cronograma. As alterações ficam registradas na auditoria." },
  { title: "Acompanhar resolução da pauta", desc: "Responsáveis confirmam ciência e atualizam sua nota. A resolução é automática: após upload válido, o item é marcado como resolvido quando o protocolo deixa de constar no snapshot do setor." },
  { title: "Encerrar pauta e exportar reunião", desc: "Administradores podem gerar PDF da sessão, consultar métricas, encerrar a sessão com auditoria e copiar pendências para uma nova pauta semanal. Sessões vencidas por prazo ainda permitem copiar pendências." },
  { title: "Consultar log de auditoria", desc: "Em Administração → seção Log de auditoria. Mostra quem fez o quê e quando, com detalhes JSON." },
];

const CHECKLIST_TRANSICAO = [
  "Novo coordenador adicionado como admin da organização copag-progep no GitHub",
  "SEI_USER e SEI_PASSWORD atualizados nos GitHub Secrets",
  "Workflow daily-upload disparado manualmente e confirmado com sucesso",
  "Acesso ao Render transferido (painel de variáveis de ambiente)",
  "Acesso ao Aiven for PostgreSQL transferido (console.aiven.io)",
  "Acesso ao Vercel transferido",
  "Usuário admin criado no AnalyticSEI para o novo coordenador",
  "Senha de app do copag@progep.ufc.br compartilhada ou gerada nova",
  "Novo coordenador testou login no AnalyticSEI e trocou a própria senha",
  "Antigo coordenador removido da organização GitHub (opcional, por segurança)",
];

const INFO_CRITICAS = {
  headers: ["Item", "Valor"],
  rows: [
    ["URL do sistema", "https://analyticsei.vercel.app"],
    ["URL da API", "https://bi-copag-api.onrender.com"],
    ["Banco de dados", "Aiven for PostgreSQL — console.aiven.io — serviço bi-copag-db"],
    ["Repositório", "github.com/copag-progep/bi-copag (branch: main)"],
    ["E-mail institucional", "copag@progep.ufc.br (Google Workspace)"],
  ],
};

/* ── Componente principal ──────────────────────── */

export default function DocumentacaoPage() {
  return (
    <div className="doc-root">

      {/* ── Hero ── */}
      <header className="doc-hero">
        <div className="doc-hero-circle1" />
        <div className="doc-hero-circle2" />
        <div className="doc-hero-inner">
          <div className="doc-hero-badge">AnalyticSEI · COPAG · PROGEP · UFC</div>
          <h1 className="doc-hero-title">
            Documentação Técnica<br /><span>AnalyticSEI</span>
          </h1>
          <div className="doc-hero-meta">
            <div className="doc-hero-meta-item"><strong>Versão</strong> {DOC_VERSION}</div>
            <div className="doc-hero-meta-item"><strong>Repositório</strong> <a href="https://github.com/copag-progep/bi-copag" target="_blank" rel="noreferrer">copag-progep/bi-copag</a></div>
            <div className="doc-hero-meta-item"><strong>Produção</strong> <a href="https://analyticsei.vercel.app" target="_blank" rel="noreferrer">analyticsei.vercel.app</a></div>
            <div className="doc-hero-meta-item"><strong>Atualizado</strong> {DOC_UPDATED}</div>
          </div>
          <div className="doc-hero-stats">
            <div className="doc-hero-stat"><strong>{CHAPTER_COUNT}</strong><span>Capítulos</span></div>
            <div className="doc-hero-stat"><strong>{DATABASE_TABLE_COUNT}</strong><span>Tabelas BD</span></div>
            <div className="doc-hero-stat"><strong>{WORKFLOWS.length}</strong><span>Workflows</span></div>
            <div className="doc-hero-stat"><strong>{FEATURES.length}</strong><span>Funcionalidades</span></div>
          </div>
        </div>
      </header>

      {/* ── Layout ── */}
      <div className="doc-layout">
        <TocSidebar />

        <div className="doc-content">

          {/* 01 */}
          <DocSection id="s01" num="01" eyebrow="Visão geral" title="O que é o AnalyticSEI">
            <p>
              O AnalyticSEI é uma plataforma web de Business Intelligence desenvolvida
              internamente para a COPAG da UFC. Transforma os relatórios CSV exportados
              do SEI em dashboards gerenciais, análises de produtividade, alertas automáticos
              e relatórios — sem nenhuma infraestrutura paga obrigatória.
            </p>
            <p>
              O SEI não possui visão gerencial nativa. Os relatórios exportados são tabelas brutas,
              sem análise de tempo de permanência, produtividade por servidor ou alertas de processos
              parados. O AnalyticSEI resolve isso.
            </p>
            <div className="doc-features-grid">
              {FEATURES.map((f, i) => <FeatureCard key={i} {...f} />)}
            </div>
          </DocSection>

          {/* 02 */}
          <DocSection id="s02" num="02" eyebrow="Infraestrutura" title="Arquitetura">
            <p>
              A plataforma usa quatro serviços conectados: código no GitHub, API no Render,
              frontend no Vercel e banco no Aiven for PostgreSQL. Todo push para <code>main</code> dispara
              deploy automático no Render e no Vercel simultaneamente.
            </p>
            <ArchDiagram />
            <Callout icon="💡">
              <strong>Rewrite do Vercel:</strong> toda chamada para <code>/api/*</code> em
              analyticsei.vercel.app é redirecionada transparentemente para o Render. O usuário
              nunca vê a URL do backend.
            </Callout>
          </DocSection>

          {/* 03 */}
          <DocSection id="s03" num="03" eyebrow="Tecnologia" title="Stack tecnológica">
            <h3>Backend</h3>
            <DocTable {...BACKEND_STACK} />
            <h3>Frontend</h3>
            <DocTable {...FRONTEND_STACK} />
            <h3>Scripts de automação</h3>
            <DocTable {...SCRIPTS_STACK} />
          </DocSection>

          {/* 04 */}
          <DocSection id="s04" num="04" eyebrow="Banco de dados" title="Modelo de dados">
            <p>12 tabelas principais gerenciadas pelo Alembic. Na inicialização, o backend executa <code>alembic upgrade head</code> automaticamente.</p>

            {[
              { name: "users", desc: "Usuários da aplicação AnalyticSEI", rows: [["id","Integer PK","Identificador único"],["name","String(120)","Nome completo"],["email","String(255) unique","E-mail de login"],["password_hash","String(255)","Hash bcrypt da senha"],["is_admin","Boolean","Privilégios administrativos"],["can_upload","Boolean","Permissão para upload manual de relatórios"],["created_at","DateTime","Data de criação"]] },
              { name: "uploads", desc: "Metadados de cada snapshot CSV importado. Unicidade: setor + data_relatorio + file_hash.", rows: [["id","Integer PK",""],["setor","String(80)","Sigla do setor (ex: DIAPE)"],["data_relatorio","Date","Data do relatório no SEI"],["data_upload","DateTime","Quando foi importado"],["original_filename","String(255)","Nome do arquivo CSV"],["file_hash","String(128)","SHA-256 (evita duplicatas)"],["total_records","Integer","Quantidade de processos"]] },
              { name: "processos", desc: "Linhas importadas dos CSVs. Unicidade: protocolo + setor + data_relatorio.", rows: [["id","Integer PK",""],["protocolo","String(120)","Número do processo SEI"],["atribuicao","String(255)","Nome original no CSV"],["atribuicao_normalizada","String(255)","Nome canônico após DE-PARA"],["tipo","String(255)","Tipo do processo"],["setor","String(80)","Setor"],["data_relatorio","Date","Data do snapshot"],["upload_id","FK → uploads",""]] },
              { name: "sei_users", desc: "DE-PARA entre variações de nome de um servidor e seu nome canônico.", rows: [["id","Integer PK",""],["nome","String(255)","Nome canônico"],["nome_sei","String(255)","Como aparece no CSV"],["usuario_sei","String(255)","Login no SEI"],["nome_key / nome_sei_key / usuario_sei_key","String(255)","Versões normalizadas (sem acentos, lowercase)"]] },
              { name: "sei_user_aliases", desc: "Aliases históricos ou alternativos vinculados a um usuário SEI canônico.", rows: [["id","Integer PK",""],["sei_user_id","FK → sei_users","Usuário principal"],["alias","String(255)","Nome antigo ou alternativo"],["alias_key","String(255) unique","Versão normalizada usada no lookup"],["created_at","DateTime","Data de criação"]] },
              { name: "sei_user_setor", desc: "Vínculo entre usuários SEI e setores onde atuam. Controla filtros de Atribuição e Servidor para usuários restritos.", rows: [["id","Integer PK",""],["sei_user_id","FK → sei_users","Usuário SEI vinculado"],["setor","String(80)","Setor permitido para aquela atribuição"]] },
              { name: "user_sector_access", desc: "Divisões que cada usuário comum da aplicação pode visualizar.", rows: [["id","Integer PK",""],["user_id","FK → users","Usuário que faz login"],["setor","String(80)","Setor liberado"],["created_at","DateTime","Data da liberação"]] },
              { name: "process_type_weights", desc: "Pesos por tipo de processo usados no Score de Risco.", rows: [["id","Integer PK",""],["tipo","String(255) unique","Tipo do processo como vem do SEI"],["peso","Numeric","Multiplicador entre 0.80 e 1.50"],["categoria","String(100)","Categoria gerencial opcional"],["justificativa","Text","Motivo do peso"],["ativo","Boolean","Indica se o peso está ativo"]] },
              { name: "pauta_sessoes", desc: "Sessões semanais de acompanhamento da Pauta Prioritária.", rows: [["id","Integer PK",""],["titulo","String(255)","Nome da pauta/reunião"],["data_inicio","Date","Início do acompanhamento"],["data_fim","Date","Prazo da pauta"],["data_reuniao","Date","Data prevista da reunião"],["observacoes","Text","Contexto geral da sessão"],["ativa","Boolean","Encerramento manual; a situação também é derivada das datas"],["criado_por","FK → users","Administrador que criou a sessão"]] },
              { name: "pauta_itens", desc: "Processos selecionados para acompanhamento em uma sessão de pauta.", rows: [["id","Integer PK",""],["sessao_id","FK → pauta_sessoes","Sessão da pauta"],["protocolo / setor / entrada_setor","—","Identifica o processo e a permanência acompanhada"],["dias_no_setor / score_risco / nivel_risco","—","Snapshot do risco no momento da inclusão"],["assigned_to / assigned_by","FK → users","Responsável e administrador que atribuiu"],["status","String(30)","pendente, em_acompanhamento, saiu_do_setor, resolvido_manual ou arquivado"],["nota_admin / nota_responsavel","Text","Orientação da gestão e atualização do responsável"],["data_status / resolucao_automatica","—","Data e origem da resolução"]] },
              { name: "monthly_stats", desc: "Indicadores mensais. Unicidade: setor + indicador + ano + num_mes.", rows: [["id","Integer PK",""],["setor","String(80)",""],["indicador","String(255)",""],["valor","Integer",""],["mes / num_mes / ano / periodo","—","Campos de período"]] },
              { name: "audit_logs", desc: "Registro de todas as ações críticas realizadas no sistema.", rows: [["id","Integer PK",""],["action","String(100)","Código da ação"],["entity_type / entity_id","String","Objeto afetado"],["details","Text","JSON com detalhes"],["user_email / user_name","String","Responsável pela ação"],["created_at","DateTime",""]] },
            ].map(({ name, desc, rows }) => (
              <div key={name}>
                <h3><code>{name}</code></h3>
                <p>{desc}</p>
                <DocTable headers={["Campo", "Tipo", "Descrição"]} rows={rows} />
              </div>
            ))}

            <div className="doc-pills-group">
              <strong style={{ fontSize: "0.82rem", color: "#5a6390", display: "block", marginBottom: 8 }}>Ações registradas no audit_logs:</strong>
              {["upload.imported","upload.replaced","upload.excluido","upload.data_alterada","usuario.criado","usuario.excluido","usuario.setores_atualizados","usuario.permissoes_atualizadas","sei_usuario.setores_atualizados","sei_usuario.setores_inferidos","process_type_weight.salvo","process_type_weight.removido","pauta.sessao_criada","pauta.sessao_editada","pauta.sessao_encerrada","pauta.pendencias_copiadas","senha.alterada"].map((a) => (
                <PillTag key={a} variant="default"><code>{a}</code></PillTag>
              ))}
            </div>
          </DocSection>

          {/* 05 */}
          <DocSection id="s05" num="05" eyebrow="API" title="Backend e endpoints">
            <p>O backend aceita <strong>JWT Bearer Token</strong> (usuários logados) ou <strong>X-Api-Key</strong> (scripts automáticos).</p>

            {[
              { group: "Saúde e Autenticação", endpoints: [
                ["GET", "/api/ping", "Keep-alive leve, sem consulta ao banco"],
                ["GET", "/api/health", "Verifica API e banco"],
                ["GET", "/api/health/data-freshness", "Frescor dos dados: data global, setores ausentes/defasados e alertas de qualidade"],
                ["POST", "/api/auth/login", "Retorna token JWT"],
                ["GET", "/api/auth/me", "Dados do usuário logado"],
                ["PATCH", "/api/auth/password", "Troca de senha (valida senha atual)"],
              ]},
              { group: "Usuários e Uploads", endpoints: [
                ["GET", "/api/admin/users", "Lista todos os usuários"],
                ["POST", "/api/admin/users", "Cria novo usuário"],
                ["DELETE", "/api/admin/users/{id}", "Remove usuário"],
                ["GET", "/api/admin/users/{id}/sectors", "Lista divisões liberadas para um usuário"],
                ["PUT", "/api/admin/users/{id}/sectors", "Redefine divisões visíveis para um usuário"],
                ["PATCH", "/api/admin/users/{id}/permissions", "Atualiza permissões adicionais, como envio de relatórios"],
                ["GET", "/api/uploads", "Lista uploads paginados"],
                ["POST", "/api/uploads", "Upload manual de CSV (JWT)"],
                ["POST", "/api/upload-with-key", "Upload automático (API key)"],
                ["PATCH", "/api/uploads/{id}", "Corrige data de snapshot"],
                ["DELETE", "/api/uploads/{id}", "Remove snapshot e processos"],
              ]},
              { group: "Usuários SEI", endpoints: [
                ["GET", "/api/admin/sei-users", "Lista usuários SEI, aliases e setores vinculados"],
                ["POST", "/api/admin/sei-users", "Cria vínculo DE-PARA de usuário SEI"],
                ["POST", "/api/admin/sei-users/import", "Importa planilha de usuários SEI"],
                ["POST", "/api/admin/sei-users/import-rows", "Importa linhas já processadas pelo frontend"],
                ["DELETE", "/api/admin/sei-users/{id}", "Remove usuário SEI"],
                ["GET", "/api/admin/sei-users/{id}/sectors", "Lista setores vinculados ao usuário SEI"],
                ["PUT", "/api/admin/sei-users/{id}/sectors", "Redefine setores vinculados ao usuário SEI"],
                ["POST", "/api/admin/sei-users/infer-sectors", "Infere vínculos de setor a partir dos processos históricos"],
              ]},
              { group: "Analytics", endpoints: [
                ["GET", "/api/meta/options", "Opções de filtro já filtradas pelo escopo do usuário logado"],
                ["GET", "/api/analytics/dashboard", "KPIs, distribuições, rankings"],
                ["GET", "/api/analytics/entries-exits", "Entradas e saídas por setor"],
                ["GET", "/api/analytics/productivity", "Produtividade por atribuição"],
                ["GET", "/api/analytics/stale", "Processos parados"],
                ["GET", "/api/analytics/multi-sector", "Processos em múltiplos setores"],
                ["GET", "/api/analytics/attributions", "Carteira com dias (paginado, filtros, ordenação)"],
                ["GET", "/api/analytics/workload-balance", "Balanceamento de carga"],
                ["GET", "/api/analytics/server-profile", "Perfil longitudinal de servidor"],
                ["GET", "/api/analytics/lead-time", "Lead time estimado: média, mediana, P90, faixas por duração e rankings por setor/tipo/atribuição"],
                ["GET", "/api/analytics/forecast", "Tendências estimadas: projeção de estoque ativo, saldo setorial e processos em envelhecimento"],
                ["GET", "/api/analytics/risk-score", "Score de Risco por processo: nível, fatores explicativos e ranking de prioridade"],
                ["GET", "/api/alerts/summary", "Resumo de processos críticos e itens pendentes da pauta (sino in-app)"],
              ]},
              { group: "Pauta Prioritária", endpoints: [
                ["GET", "/api/pauta/sessoes", "Lista sessões; admin vê todas e usuário comum vê apenas sessões com itens atribuídos e setores ainda permitidos"],
                ["POST", "/api/pauta/sessoes", "Cria sessão semanal de pauta (admin)"],
                ["GET", "/api/pauta/sessoes/{id}", "Detalha sessão, contagens e itens visíveis ao usuário; não-admin sem itens visíveis recebe 404"],
                ["PATCH", "/api/pauta/sessoes/{id}", "Atualiza título/datas/observações ou encerra sessão com auditoria"],
                ["POST", "/api/pauta/sessoes/{id}/itens", "Inclui processo individual na pauta (admin)"],
                ["POST", "/api/pauta/sessoes/{id}/itens/bulk", "Inclui processos em lote a partir do Score de Risco (admin)"],
                ["PATCH", "/api/pauta/itens/{id}", "Atualiza item; responsável só confirma ciência e edita sua nota"],
                ["DELETE", "/api/pauta/itens/{id}", "Remove item da pauta (admin)"],
                ["GET", "/api/pauta/minha", "Lista itens atribuídos ao usuário logado"],
                ["POST", "/api/pauta/sessoes/{id}/copy-pending", "Valida datas, copia pendências para nova sessão e encerra a origem quando ainda está operável"],
                ["GET", "/api/pauta/metricas", "Métricas administrativas de eficiência da pauta"],
              ]},
              { group: "Outros", endpoints: [
                ["GET", "/api/admin/audit-logs", "Log de auditoria paginado"],
                ["GET", "/api/processes/search", "Busca parcial por protocolo"],
                ["GET", "/api/monthly-stats", "Indicadores mensais"],
                ["POST", "/api/admin/monthly-stats/month-entry", "Lança mês manualmente"],
              ]},
            ].map(({ group, endpoints }) => (
              <div key={group}>
                <h3>{group}</h3>
                <div className="doc-table-wrapper">
                  <table className="doc-table">
                    <tbody>
                      {endpoints.map(([method, path, desc]) => (
                        <tr key={path} className="doc-endpoint-row">
                          <td style={{ width: 70 }}><MethodBadge method={method} /></td>
                          <td><code>{path}</code></td>
                          <td style={{ color: "#5a6390", fontSize: "0.82rem" }}>{desc}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}

            <Callout icon="⚡">
              <strong>Cache analítico:</strong> todos os endpoints analíticos usam cache em memória.
              No backend, a chave considera endpoint, assinatura dos uploads, filtros e escopo de setores.
              O cache é LRU com orçamento de memória. No frontend, usuários administradores podem reaproveitar
              cache persistente por usuário; usuários restritos aguardam a resposta atual do servidor para evitar
              exibição stale após mudança de permissão. Invalidado automaticamente após qualquer upload.
              O pré-aquecimento em background roda em modo leve por padrão:
              endpoints históricos pesados, como processos parados, atribuições, lead time, forecast e Score de Risco, só
              entram no precompute se <code>PRECOMPUTE_HEAVY_ANALYTICS=true</code>.
            </Callout>
          </DocSection>

          {/* 06 */}
          <DocSection id="s06" num="06" eyebrow="Interface" title="Frontend — páginas e funcionalidades">
            <p>SPA React com autenticação JWT no <code>localStorage</code>. Carregamento por rota com <code>React.lazy</code> (code splitting).</p>

            <h3>Elementos globais</h3>
            <p><strong>Topbar:</strong> título dinâmico por rota · badge de frescor dos dados · busca global de protocolo · sino de notificações com críticos e itens pendentes da pauta · chip do usuário.</p>
            <p><strong>Sidebar:</strong> colapsável (248px → 72px) com ícones SVG · itens admin ocultos para não-admins · Enviar Relatório oculto para usuários sem permissão de upload · chip do usuário e botão Sair no rodapé.</p>
            <p><strong>FilterBar:</strong> aparece nas páginas analíticas — Data de referência, setor, tipo, atribuição (inclui "Sem atribuição"). Para usuários restritos, mostra apenas setores permitidos e atribuições vinculadas aos seus setores.</p>

            <h3>Páginas</h3>
            <div className="doc-features-grid">
              {[
                { icon: "🎯", title: "/executivo", desc: "Central de decisão com prioridades do dia, saúde dos dados, cards com sparklines, lead time e listas executivas" },
                { icon: "📊", title: "/  Dashboard", desc: "KPIs, distribuição por setor/tipo, ranking, evolução diária, tabela de finalizações" },
                { icon: "📤", title: "/enviar-relatorio", desc: "Upload de CSV + histórico paginado; visível apenas para admins ou usuários com permissão de upload" },
                { icon: "↔️", title: "/entradas-saidas", desc: "Entradas, saídas, saldo e evolução do fluxo por setor" },
                { icon: "⚡", title: "/produtividade", desc: "Produção estimada, ranking acumulado e evolução histórica por servidor" },
                { icon: "🔀", title: "/multiplos-setores", desc: "Protocolos presentes em mais de um setor; detecção limitada ao escopo visível, busca local e exportação PDF/Excel" },
                { icon: "📋", title: "/atribuicoes", desc: "Carteira com 6 faixas de criticidade, busca, filtros server-side, exportação PDF e Excel" },
                { icon: "🛡️", title: "/risco", desc: "Ranking de Score de Risco por processo, filtros por nível e explicação dos fatores" },
                { icon: "✅", title: "/pauta", desc: "Pauta Prioritária: sessões semanais com cronograma, situação derivada por prazo, editor para admin, progresso, PDF, métricas e resolução automática quando o processo sai do setor" },
                { icon: "⚖️", title: "/servidores", desc: "Balanceamento de carga + perfil longitudinal individual; filtro de servidor respeita setores vinculados" },
                { icon: "📅", title: "/indicadores-mensais", desc: "Dashboard histórico + importação de CSV + lançamento manual mensal, filtrado pelos setores permitidos" },
                { icon: "🔍", title: "/busca", desc: "Histórico completo de movimentações de um protocolo específico" },
                { icon: "👤", title: "/minha-conta", desc: "Informações do usuário + formulário de troca de senha" },
                { icon: "⚙️", title: "/administracao", desc: "Gestão de usuários, divisões liberadas, permissão de upload, pesos do Score e log de auditoria (admin only)" },
                { icon: "🔗", title: "/usuarios-sei", desc: "DE-PARA de nomes, aliases históricos, setores por usuário SEI e inferência em lote (admin only)" },
              ].map((p, i) => <FeatureCard key={i} {...p} />)}
            </div>

            <h3>Faixas de criticidade — página /atribuicoes</h3>
            <div className="doc-pills-group">
              <PillTag variant="success">&lt;15d — Normal</PillTag>
              <PillTag variant="warning">15–29d — Atenção</PillTag>
              <PillTag variant="accent">30–44d — Alerta</PillTag>
              <PillTag variant="danger">45–59d — Grave</PillTag>
              <PillTag variant="danger">60–89d — Crítico</PillTag>
              <PillTag variant="purple">90d+ — Extremo</PillTag>
            </div>

            <Callout icon="⏱️">
              <strong>Central Executiva:</strong> a página carrega primeiro os indicadores leves
              (dashboard e fluxo), depois busca processos críticos, lead time e tendências estimadas separadamente. Assim,
              um endpoint pesado ou lento não derruba a tela inteira. O timeout padrão das chamadas
              analíticas é de 90 segundos, com 120 segundos nos blocos históricos mais pesados.
            </Callout>

            <Callout icon="🔐">
              <strong>Recorte por usuário:</strong> os filtros visuais não são apenas cosméticos.
              O backend aplica o escopo de setores em cada endpoint analítico, nas datas de referência,
              nas opções de filtro e nas pautas prioritárias. Para usuários comuns, a pauta exige atribuição
              ao usuário e acesso atual ao setor do processo.
            </Callout>
          </DocSection>

          {/* 07 */}
          <DocSection id="s07" num="07" eyebrow="GitHub Actions" title="Automação">
            <p>5 workflows em <code>.github/workflows/</code>. Todos podem ser disparados manualmente via <code>workflow_dispatch</code>.</p>
            <div className="doc-workflow-grid">
              {WORKFLOWS.map((w) => (
                <div key={w.name} className="doc-workflow-card">
                  <div className="doc-workflow-name">{w.name}</div>
                  <div className="doc-workflow-freq">⏰ {w.freq}</div>
                  <div className="doc-workflow-desc">{w.desc}</div>
                </div>
              ))}
            </div>
            <Callout icon="🔑">
              <strong>Troca de coordenador:</strong> basta atualizar <code>SEI_USER</code> e <code>SEI_PASSWORD</code> nos
              GitHub Secrets em <em>Settings → Secrets and variables → Actions</em>. Nenhum arquivo
              de código precisa ser alterado. A automação é 100% agnóstica ao usuário.
            </Callout>
          </DocSection>

          {/* 08 */}
          <DocSection id="s08" num="08" eyebrow="Proteção" title="Segurança e auditoria">
            <h3>Autenticação JWT</h3>
            <p>Algoritmo HS256, TTL de 720 minutos. Senhas com hash bcrypt (salt automático). Assinado com <code>JWT_SECRET_KEY</code>.</p>

            <h3>API Key para automação</h3>
            <p>Chave estática em <code>API_UPLOAD_KEY</code> (variável de ambiente). Passada no header <code>X-Api-Key</code>. Aceita nos endpoints de upload e nos analíticos para scripts. Nunca exposta no código.</p>

            <h3>Log de auditoria</h3>
            <p>Toda ação crítica é registrada com: código da ação, objeto afetado, detalhes em JSON, e-mail e nome do responsável, data/hora. Visível apenas para admins em <strong>Administração → Log de auditoria</strong>.</p>

            <h3>Controle de acesso por divisão</h3>
            <p>Administradores veem todos os dados. Usuários comuns veem apenas os setores liberados em <strong>Administração → Acessos</strong>. Esse recorte é aplicado no backend em dashboards, listas, datas de referência, indicadores mensais, histórico de uploads, badge de frescor e opções de filtro.</p>
            <p>Na Pauta Prioritária, o acesso é cumulativo: o item precisa estar atribuído ao usuário e o setor do processo ainda precisa estar liberado para ele. Se houver itens ativos, a remoção desse setor do usuário é bloqueada até a reatribuição.</p>

            <h3>Permissão de upload</h3>
            <p>A tela <strong>Enviar Relatório</strong> só fica disponível para administradores ou usuários marcados com permissão de upload. Mesmo com permissão, o usuário só consegue enviar CSV de setores aos quais tem acesso.</p>

            <h3>Usuários SEI por setor</h3>
            <p>A página <strong>Usuários SEI</strong> permite vincular servidores/atribuições a um ou mais setores. Usuários restritos passam a ver nos filtros de Atribuição e Servidor apenas os nomes vinculados aos seus setores permitidos.</p>

            <h3>Alembic — migrações versionadas</h3>
            <p>Novas colunas/tabelas criadas como arquivos em <code>alembic/versions/</code>. Na inicialização, o backend executa <code>alembic upgrade head</code>. Em bancos sem Alembic, sela automaticamente no baseline antes de aplicar migrações novas.</p>

            <h3>CORS</h3>
            <p>Aceita apenas <code>localhost:5173</code> (dev local) e qualquer subdomínio <code>*.vercel.app</code> (produção).</p>
          </DocSection>

          {/* 09 */}
          <DocSection id="s09" num="09" eyebrow="Deploy" title="Configuração de ambiente">
            <h3>Variáveis no Render (backend)</h3>
            <DocTable
              headers={["Variável", "Descrição"]}
              rows={[
                ["DATABASE_URL", "String de conexão PostgreSQL (Aiven)"],
                ["JWT_SECRET_KEY", "Chave para assinar tokens JWT"],
                ["API_UPLOAD_KEY", "Chave para uploads automáticos"],
                ["DEFAULT_ADMIN_EMAIL", "E-mail do admin padrão"],
                ["DEFAULT_ADMIN_PASSWORD", "Senha inicial do admin"],
                ["ACCESS_TOKEN_EXPIRE_MINUTES", "TTL do token (padrão: 720)"],
                ["AUTO_IMPORT_SAMPLE_DATA", "false em produção"],
                ["ANALYTICS_LOOKBACK_DAYS", "Janela máxima de histórico analítico (padrão: 120 dias). 0 = sem limite."],
                ["DISABLE_STARTUP_PRECOMPUTE", "false em produção. true desliga o aquecimento de cache na inicialização."],
                ["PRECOMPUTE_HEAVY_ANALYTICS", "false por padrão. true inclui endpoints pesados no precompute, como processos parados, atribuições, lead time, forecast e Score de Risco."],
                ["PRECOMPUTE_COOLDOWN_SECS", "Intervalo mínimo entre precomputes consecutivos (padrão: 120 s)."],
                ["DISABLE_POST_CHANGE_PRECOMPUTE", "true desliga o precompute automático após uploads/alterações; útil em instâncias com pouca RAM."],
                ["ANALYTICS_CACHE_MAX_ENTRIES", "Limite de entradas do cache LRU analítico."],
                ["ANALYTICS_CACHE_MAX_TOTAL_MB", "Orçamento total de memória do cache analítico em MB."],
                ["ANALYTICS_CACHE_MAX_ITEM_MB", "Tamanho máximo de payload individual que pode entrar no cache."],
                ["ANALYTICS_BUILD_CONCURRENCY", "Quantidade de builds analíticos simultâneos por processo. Recomendado: 1."],
                ["APP_TIMEZONE", "Fuso usado em checagens operacionais. Padrão: America/Fortaleza."],
                ["DATA_FRESHNESS_OK_MAX_DAYS", "Idade máxima para considerar o dado atualizado. Padrão: 3 dias."],
                ["DATA_FRESHNESS_CRITICAL_DAYS", "Idade a partir da qual o dado fica crítico. Padrão: 7 dias."],
                ["DATA_QUALITY_DROP_RATIO", "Queda mínima de volume para alerta simples de qualidade. Padrão: 0.6."],
                ["RISK_WEIGHT_*", "Pesos do Score de Risco: tempo absoluto, contexto histórico, sem atribuição e múltiplos setores."],
                ["RISK_TREND_*", "Multiplicadores do Score de Risco conforme tendência do setor."],
                ["RISK_*_THRESHOLD", "Limiares de classificação do Score de Risco: crítico, elevado e moderado."],
                ["RISK_MIN_LT_SAMPLE", "Amostra mínima para usar P90 de lead time no Score de Risco. Padrão: 5."],
                ["RISK_MIN_P90_DAYS", "Piso técnico do P90 usado no Score de Risco. Padrão: 7 dias."],
              ]}
            />
            <h3>GitHub Secrets</h3>
            <DocTable
              headers={["Secret", "Descrição"]}
              rows={[
                ["SEI_URL", "URL base do SEI (ex: https://sei.ufc.br/sei)"],
                ["SEI_USER", "Login SEI do coordenador — atualizar na troca"],
                ["SEI_PASSWORD", "Senha SEI — atualizar na troca"],
                ["BI_API_KEY", "Mesma chave que API_UPLOAD_KEY no Render"],
                ["GMAIL_USER", "copag@progep.ufc.br"],
                ["GMAIL_APP_PASSWORD", "Senha de app Google (myaccount.google.com)"],
              ]}
            />
            <h3>GitHub Variables</h3>
            <DocTable
              headers={["Variable", "Valor"]}
              rows={[
                ["BI_API_URL", "https://bi-copag-api.onrender.com"],
                ["REPORT_RECIPIENTS", "E-mails dos destinatários separados por vírgula"],
              ]}
            />
          </DocSection>

          {/* 10 */}
          <DocSection id="s10" num="10" eyebrow="Operação" title="Manutenção do dia a dia">
            <Callout icon="🤖">
              O upload diário é <strong>totalmente automático às 19:00 BRT</strong>. Se falhar,
              um e-mail de alerta é enviado automaticamente. Intervenção manual só é necessária
              em casos excepcionais. O relatório diário das 19:30 também verifica esse sucesso antes
              de enviar, evitando e-mail com dados desatualizados quando o upload do dia falha.
            </Callout>
            <div className="doc-grid-2">
              {MANUTENCAO.map(({ title, desc }) => (
                <div key={title} className="doc-procedure">
                  <h4>{title}</h4>
                  <p>{desc}</p>
                </div>
              ))}
            </div>
          </DocSection>

          {/* 11 */}
          <DocSection id="s11" num="11" eyebrow="Transferência" title="Transição para nova gestão">
            <h3>O que o novo coordenador precisa fazer (≈ 10 minutos)</h3>
            <ol>
              <li>Acessar GitHub → <code>copag-progep/bi-copag</code> → <strong>Settings → Secrets and variables → Actions</strong></li>
              <li>Atualizar <code>SEI_USER</code> com seu login no SEI</li>
              <li>Atualizar <code>SEI_PASSWORD</code> com sua senha no SEI</li>
              <li>Disparar <code>daily-upload</code> manualmente e confirmar sucesso nos logs</li>
              <li>Alterar a própria senha no AnalyticSEI em <strong>Minha Conta</strong></li>
            </ol>
            <p style={{ marginTop: 20 }}>
              <strong>Nenhum arquivo de código precisa ser alterado.</strong> A automação é
              agnóstica ao usuário — usa apenas as credenciais dos Secrets.
            </p>

            <h3>Checklist de transferência</h3>
            <Checklist items={CHECKLIST_TRANSICAO} />

            <h3>Informações críticas de produção</h3>
            <DocTable {...INFO_CRITICAS} />
          </DocSection>

          {/* 12 */}
          <DocSection id="s12" num="12" eyebrow="Evolução" title="Histórico de funcionalidades">
            {[
              { title: "Fundação do sistema", items: ["Autenticação JWT + bcrypt","Importação de CSVs (UTF-8, UTF-8-BOM, Latin-1)","Hash SHA-256 para evitar duplicatas","Substituição de snapshot por setor/data","Dashboard com KPIs, distribuição, evolução diária","Entradas e saídas, produtividade, múltiplos setores","Administração de usuários com proteção do último admin"] },
              { title: "Infraestrutura e qualidade", items: ["Alembic para migrações formais com auto-stamp","Log de auditoria em tabela dedicada","Lifespan context manager (substituiu @app.on_event)","datetime.now(timezone.utc) (substituiu utcnow)","sync_processo_atribuicoes com SQL UPDATE em lote","Cache analítico LRU com orçamento de memória, invalidação automática e chave por escopo de setores","Pré-aquecimento leve do cache em background, com endpoints históricos pesados controlados por PRECOMPUTE_HEAVY_ANALYTICS e precompute pós-alteração desligável","Healthcheck com verificação do banco","Endpoint /api/health/data-freshness + badge no topo para avisar dado velho, setor ausente/defasado e queda simples de volume"] },
              { title: "Identidade visual Progep/UFC", items: ["Paleta: navy #273168 · laranja #f39320 · amarelo #febb12 · azul #81c7ee","Fonte Plus Jakarta Sans","Sidebar redesenhada com ícones SVG e chip do usuário","Topbar com título dinâmico por rota","StatCards com hover e estrutura vertical","LoginPage com dois painéis e stats decorativos"] },
              { title: "Performance", items: ["React.lazy + Suspense para code splitting por rota","preconnect e dns-prefetch para o backend","LoadingBlock com spinner e mensagem de servidor iniciando","useAnalyticsData hook com cache stale-while-revalidate para admins e resposta atual obrigatória para usuários restritos","clearAnalyticsCache chamado após upload"] },
              { title: "Analíticas avançadas", items: ["Central Executiva com prioridades do dia, saúde dos dados, sparklines dos KPIs principais e carregamento escalonado","Lead time estimado dos processos que saíram da carteira, com média, mediana, P90, faixas por duração e ranking por setor/tipo/atribuição","Tendências estimadas com regressão linear simples, projeção de estoque ativo em 15/30 dias, tendência por setor e estimativa de críticos","Score de Risco por processo com pesos configuráveis, P90 com piso técnico e explicação por fator","Pauta Prioritária com sessões semanais, cronograma visível, situação derivada por prazo, edição de prazos pelo admin, responsáveis, resolução automática via snapshot, PDF de reunião, encerramento e métricas de eficiência","Página Atribuições com spans consecutivos por setor, 6 faixas de criticidade, filtros server-side, busca por protocolo e badge de risco por processo","Múltiplos setores com detecção e exibição limitadas ao escopo visível do usuário, busca local e exportação PDF/Excel","Exportação PDF com identidade visual (jsPDF + jspdf-autotable)","Exportação Excel (SheetJS)","Página Servidores: balanceamento por desvio-padrão + perfil longitudinal","Busca global de processo com histórico de movimentações","Filtro Sem atribuição no FilterBar global","Indicadores mensais com dashboard e lançamento manual"] },
              { title: "Automação (Bloco 4)", items: ["API key para uploads sem JWT","Script SEI Scraper (Playwright headless): login, troca de setor por JS, coleta todas as páginas","Workflow daily-upload (19:00 BRT) com notificação de falha","Workflow daily-report (19:30 BRT) bloqueado por check_daily_upload_success.py quando o upload do dia não concluiu com sucesso","Workflow weekly-report (sexta 20:00 BRT)","Script de alertas com anti-spam (não envia se sem críticos)","Workflow critical-alerts (sexta 21:00 BRT)"] },
              { title: "Alertas e notificações (Bloco 1)", items: ["Endpoint /api/alerts/summary (leve, usa cache)","Sino de notificações na topbar: badge somando críticos ≥45d e itens pendentes da Pauta Prioritária","Dropdown com link para /atribuicoes e /pauta","E-mail de alertas: cards por faixa, tabela dos críticos, destaque para >90d","Não envia e-mail se nenhum processo crítico"] },
              { title: "Segurança e acesso", items: ["Troca de senha pelo próprio usuário (valida senha atual)","Controle de acesso por divisão em todos os endpoints analíticos e operacionais sensíveis, incluindo datas de referência e opções de filtro","Permissão individual para upload manual de relatórios","Pauta Prioritária com acesso cumulativo por responsável e setor atual permitido","DE-PARA com normalização de identidade (sem acentos, lowercase, case-insensitive), aliases históricos e vínculos de usuários SEI por setor","Filtro de Atribuição e Servidor limitado aos setores do usuário logado","Cache analítico do frontend isolado por usuário e sem leitura persistente para usuários restritos antes da resposta atual","Autenticação dual (JWT ou API key) nos endpoints analíticos","Página Minha conta com informações e formulário de troca de senha"] },
            ].map(({ title, items }) => (
              <div key={title}>
                <h3>{title}</h3>
                <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
              </div>
            ))}
          </DocSection>

        </div>
      </div>

      {/* ── Footer ── */}
      <footer className="doc-footer">
        <div className="doc-footer-brand">AnalyticSEI · COPAG · PROGEP · UFC</div>
        <div className="doc-footer-text">
          Projeto de autoria de Anderson Santos, Administrador e Coordenador da COPAG.<br />
          Desenvolvido com o auxílio de IA: Claude Code (Anthropic) e Codex (OpenAI) — repositório copag-progep/bi-copag.
        </div>
      </footer>

      {/* ── Botão de impressão ── */}
      <button className="doc-print-btn" onClick={() => window.print()}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/>
          <rect x="6" y="14" width="12" height="8"/>
        </svg>
        Imprimir / PDF
      </button>

    </div>
  );
}
