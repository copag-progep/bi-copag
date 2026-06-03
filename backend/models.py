"""Modelos SQLAlchemy — espelham os dados exportados do SEI e entidades de suporte do AnalyticSEI."""
from datetime import date, datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_upload: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    sector_access: Mapped[list["UserSectorAccess"]] = relationship(
        "UserSectorAccess", back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        UniqueConstraint("setor", "data_relatorio", "file_hash", name="uq_upload_hash_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    setor: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    data_relatorio: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # data do CSV exportado do SEI
    data_upload: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)  # SHA-256, usado para dedup
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    processos: Mapped[list["Processo"]] = relationship(
        "Processo",
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Processo(Base):
    __tablename__ = "processos"
    __table_args__ = (
        UniqueConstraint("protocolo", "setor", "data_relatorio", name="uq_processo_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_row_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ID da linha no CSV original
    protocolo: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    atribuicao: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # texto bruto do SEI
    atribuicao_normalizada: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)  # nome canônico via DE-PARA (sei_users)
    tipo: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    especificacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ponto_controle: Mapped[str | None] = mapped_column(String(255), nullable=True)  # etapa do workflow no SEI
    data_autuacao: Mapped[date | None] = mapped_column(Date, nullable=True)  # data de abertura do processo
    data_recebimento: Mapped[date | None] = mapped_column(Date, nullable=True)  # chegada no setor atual
    data_envio: Mapped[date | None] = mapped_column(Date, nullable=True)  # envio para outro setor
    unidade_envio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    setor: Mapped[str] = mapped_column(String(80), nullable=False, index=True)  # divisão da COPAG (DIAPE, DICAT, etc.)
    data_relatorio: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # data do snapshot CSV
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)

    upload: Mapped["Upload"] = relationship("Upload", back_populates="processos")


class SeiUser(Base):
    __tablename__ = "sei_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)  # nome canônico (exibido nos relatórios)
    nome_sei: Mapped[str | None] = mapped_column(String(255), nullable=True)  # nome como aparece no SEI (pode diferir)
    usuario_sei: Mapped[str | None] = mapped_column(String(255), nullable=True)  # login do SEI
    nome_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # nome normalizado (casefold, sem acentos) para lookup
    nome_sei_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    usuario_sei_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    aliases: Mapped[list["SeiUserAlias"]] = relationship(
        "SeiUserAlias",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SeiUserAlias.alias",
    )
    setor_links: Mapped[list["SeiUserSetor"]] = relationship(
        "SeiUserSetor",
        back_populates="sei_user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def setores(self) -> list[str]:
        """Setores vinculados ao usuário SEI, prontos para serialização na API."""
        return sorted(link.setor for link in self.setor_links)


class SeiUserSetor(Base):
    """Vínculo entre um usuário SEI (servidor/atribuição) e os setores onde atua.

    Usado para filtrar o dropdown de Atribuição para usuários com acesso restrito
    por divisão. Admin vê todos; usuário restrito vê apenas atribuições dos SEI
    users vinculados aos seus setores permitidos.
    """
    __tablename__ = "sei_user_setor"
    __table_args__ = (
        sa.UniqueConstraint("sei_user_id", "setor", name="uq_sei_user_setor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sei_user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("sei_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    setor: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    sei_user: Mapped["SeiUser"] = relationship("SeiUser", back_populates="setor_links")


class SeiUserAlias(Base):
    __tablename__ = "sei_user_aliases"
    __table_args__ = (
        UniqueConstraint("alias_key", name="uq_sei_user_alias_key"),
        Index("ix_sei_user_aliases_user_id_alias_key", "sei_user_id", "alias_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sei_user_id: Mapped[int] = mapped_column(ForeignKey("sei_users.id", ondelete="CASCADE"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user: Mapped["SeiUser"] = relationship("SeiUser", back_populates="aliases")


class PautaSessao(Base):
    """Sessão semanal da pauta executiva de processos prioritários.

    Cada sessão agrupa os processos selecionados para uma semana de acompanhamento.
    """
    __tablename__ = "pauta_sessoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    data_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    data_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_reuniao: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_por: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    itens: Mapped[list["PautaItem"]] = relationship(
        "PautaItem", back_populates="sessao", cascade="all, delete-orphan", passive_deletes=True
    )


class PautaItem(Base):
    """Item de pauta — processo específico incluído em uma sessão de acompanhamento.

    Status:
      pendente        → incluído, aguardando ação
      em_acompanhamento → responsável confirmou ciência
      saiu_do_setor   → processo não aparece mais no snapshot do setor (automático)
      resolvido_manual → marcado manualmente como resolvido
      arquivado       → removido da vista ativa pelo admin
    """
    __tablename__ = "pauta_itens"
    __table_args__ = (
        UniqueConstraint("sessao_id", "protocolo", "setor", "entrada_setor", name="uq_pauta_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sessao_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pauta_sessoes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    protocolo: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    setor: Mapped[str] = mapped_column(String(80), nullable=False)
    entrada_setor: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_referencia: Mapped[date | None] = mapped_column(Date, nullable=True)
    ultima_presenca: Mapped[date | None] = mapped_column(Date, nullable=True)
    atribuicao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dias_no_setor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_risco: Mapped[float | None] = mapped_column(sa.Numeric(5, 3), nullable=True)
    nivel_risco: Mapped[str | None] = mapped_column(String(20), nullable=True)
    assigned_to: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_by: Mapped[int | None] = mapped_column(
        sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="pendente", nullable=False)
    nota_admin: Mapped[str | None] = mapped_column(Text, nullable=True)
    nota_responsavel: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_status: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolucao_automatica: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    sessao: Mapped["PautaSessao"] = relationship("PautaSessao", back_populates="itens")


class UserSectorAccess(Base):
    """Controle de acesso por divisão (setor) para usuários não-administradores.

    Regras:
      - Administradores não usam esta tabela — sempre têm acesso total.
      - Usuários sem nenhuma linha aqui não têm acesso a dado algum (padrão seguro).
      - Usuários com linhas aqui enxergam apenas os setores listados.
    """
    __tablename__ = "user_sector_access"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "setor", name="uq_user_sector_access"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    setor: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="sector_access")


class ProcessTypeWeight(Base):
    """Peso de prioridade por tipo de processo para o Score de Risco.

    Tipos sem registro nesta tabela recebem peso implícito 1.00 (neutro).
    O admin pode criar/editar pesos pela interface administrativa ou
    pela API /api/admin/type-weights.
    """
    __tablename__ = "process_type_weights"
    __table_args__ = (
        sa.CheckConstraint("peso >= 0.80 AND peso <= 1.50", name="ck_process_type_weights_peso"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tipo: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    peso: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False, default=1.00)
    categoria: Mapped[str | None] = mapped_column(String(100), nullable=True)   # ex: "Alta prioridade"
    justificativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )


class MonthlyStat(Base):
    __tablename__ = "monthly_stats"
    __table_args__ = (
        UniqueConstraint("setor", "indicador", "ano", "num_mes", name="uq_monthly_stat_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    setor: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    indicador: Mapped[str] = mapped_column(String(255), nullable=False, index=True)  # ex: "Processos gerados no período"
    valor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mes_ano: Mapped[str] = mapped_column(String(20), nullable=False)  # label curto: "mai/26"
    mes: Mapped[str] = mapped_column(String(40), nullable=False)  # label completo: "maio"
    num_mes: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    periodo: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # primeiro dia do mês (para ordenação)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
