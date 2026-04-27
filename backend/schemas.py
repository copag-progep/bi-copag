from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    is_admin: bool = False


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    is_admin: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class UploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    setor: str
    data_relatorio: date
    data_upload: datetime
    original_filename: str
    total_records: int


class UploadListResponse(BaseModel):
    items: list[UploadRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class UploadUpdate(BaseModel):
    data_relatorio: date


class UploadResult(BaseModel):
    status: str
    message: str
    setor: str
    data_relatorio: date
    original_filename: str
    total_registros: int
    substituiu_snapshot_anterior: bool = False


class FilterOptions(BaseModel):
    datas: list[date]
    setores: list[str]
    tipos: list[str]
    atribuicoes: list[str]
    setores_validos: list[str] = []


class SeiUserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=255)
    nome_sei: str | None = Field(default=None, max_length=255)
    usuario_sei: str | None = Field(default=None, max_length=255)


class SeiUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    nome_sei: str | None
    usuario_sei: str | None
    created_at: datetime


class SeiUserImportResult(BaseModel):
    imported: int
    updated: int
    total: int


class SeiUserBulkImport(BaseModel):
    rows: list[SeiUserCreate]


class MonthlyStatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    setor: str
    indicador: str
    valor: int
    mes_ano: str
    mes: str
    num_mes: int
    ano: int
    periodo: date
    updated_at: datetime


class MonthlyStatImportResult(BaseModel):
    imported: int
    updated: int
    total: int


class MonthlyStatUpdate(BaseModel):
    valor: int = Field(ge=0)


class MonthlyStatMonthEntry(BaseModel):
    setor: str
    ano: int = Field(ge=2023, le=2100)
    num_mes: int = Field(ge=1, le=12)
    processos_gerados: int = Field(ge=0)
    processos_tramitacao: int = Field(ge=0)
    processos_fechados: int = Field(ge=0)
    processos_abertos: int = Field(ge=0)
    documentos_gerados: int = Field(ge=0)
    documentos_externos: int = Field(ge=0)
