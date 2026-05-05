from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Upload(Base):
    __tablename__ = "uploads"
    __table_args__ = (
        UniqueConstraint("setor", "data_relatorio", "file_hash", name="uq_upload_hash_snapshot"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    setor: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    data_relatorio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_upload: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
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
    source_row_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    protocolo: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    atribuicao: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    atribuicao_normalizada: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tipo: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    especificacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ponto_controle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    data_autuacao: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_recebimento: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_envio: Mapped[date | None] = mapped_column(Date, nullable=True)
    unidade_envio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    setor: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    data_relatorio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    upload_id: Mapped[int] = mapped_column(ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)

    upload: Mapped["Upload"] = relationship("Upload", back_populates="processos")


class SeiUser(Base):
    __tablename__ = "sei_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_sei: Mapped[str | None] = mapped_column(String(255), nullable=True)
    usuario_sei: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nome_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    nome_sei_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    usuario_sei_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


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
    indicador: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    valor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mes_ano: Mapped[str] = mapped_column(String(20), nullable=False)
    mes: Mapped[str] = mapped_column(String(40), nullable=False)
    num_mes: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    periodo: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
