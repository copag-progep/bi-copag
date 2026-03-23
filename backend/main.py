import os
from datetime import date

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from .analytics import (
    AnalyticsFilters,
    clear_analytics_cache,
    get_dashboard_data,
    get_entries_exits_data,
    get_filter_options,
    get_multi_sector_data,
    get_productivity_data,
    get_stale_processes_data,
)
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_admin_user,
    get_current_user,
    get_password_hash,
)
from .csv_importer import SETORES, bootstrap_workspace_csvs, import_csv_snapshot
from .database import SessionLocal, get_db, init_db
from .models import Processo, Upload, User
from .schemas import FilterOptions, Token, UploadRead, UploadResult, UploadUpdate, UserCreate, UserLogin, UserRead


DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "Anderson CFS")
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "andersoncfs@ufc.br")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")

app = FastAPI(
    title="SEI BI API",
    version="1.0.0",
    description="API para importação de relatórios SEI e análise de processos administrativos.",
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
origins.extend([origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_filters(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
) -> AnalyticsFilters:
    normalized_setor = setor.upper().strip() if setor else None
    return AnalyticsFilters(
        data_referencia=data_referencia,
        data_inicial=data_inicial,
        data_final=data_final,
        setor=normalized_setor,
        tipo=tipo,
        atribuicao=atribuicao,
    )


def ensure_default_user() -> None:
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == DEFAULT_ADMIN_EMAIL.lower()).first()
        if existing_user:
            return
        user = User(
            name=DEFAULT_ADMIN_NAME,
            email=DEFAULT_ADMIN_EMAIL.lower(),
            password_hash=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            is_admin=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()


def auto_import_workspace_data() -> None:
    db = SessionLocal()
    try:
        results = bootstrap_workspace_csvs(db)
        if any(result["status"] in {"imported", "replaced"} for result in results):
            clear_analytics_cache()
    finally:
        db.close()


def get_upload_or_404(db: Session, upload_id: int) -> Upload:
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relatório não encontrado.")
    return upload


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    ensure_default_user()
    auto_import_workspace_data()


@app.get("/api/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha inválidos.")
    token = create_access_token(user.email)
    return Token(access_token=token, user=user)


@app.post("/api/auth/logout")
def logout() -> dict:
    return {"message": "Logout realizado com sucesso."}


@app.get("/api/auth/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get("/api/admin/users", response_model=list[UserRead])
def list_users(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.name.asc()).all()


@app.post("/api/admin/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> User:
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um usuário com este email.")

    user = User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=get_password_hash(payload.password),
        is_admin=payload.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/api/uploads", response_model=list[UploadRead])
def list_uploads(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Upload]:
    return db.query(Upload).order_by(Upload.data_relatorio.desc(), Upload.data_upload.desc()).limit(100).all()


@app.post("/api/uploads", response_model=UploadResult)
async def upload_snapshot(
    setor: str = Form(...),
    data_relatorio: date = Form(...),
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResult:
    if setor.upper() not in SETORES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setor inválido.")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie um arquivo CSV.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")

    try:
        result = import_csv_snapshot(
            db=db,
            file_bytes=file_bytes,
            filename=file.filename,
            setor=setor,
            data_relatorio=data_relatorio,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha ao importar CSV.") from exc

    if result["status"] in {"imported", "replaced"}:
        clear_analytics_cache()

    return UploadResult(**result)


@app.patch("/api/uploads/{upload_id}", response_model=UploadRead)
def update_upload(
    upload_id: int,
    payload: UploadUpdate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Upload:
    upload = get_upload_or_404(db, upload_id)
    if payload.data_relatorio == upload.data_relatorio:
        return upload

    conflict = (
        db.query(Upload)
        .filter(
            Upload.id != upload.id,
            Upload.setor == upload.setor,
            Upload.data_relatorio == payload.data_relatorio,
        )
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um relatório deste setor com a data informada.",
        )

    db.query(Processo).filter(Processo.upload_id == upload.id).update(
        {Processo.data_relatorio: payload.data_relatorio},
        synchronize_session=False,
    )
    upload.data_relatorio = payload.data_relatorio
    db.commit()
    db.refresh(upload)
    clear_analytics_cache()
    return upload


@app.delete("/api/uploads/{upload_id}")
def delete_upload(
    upload_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    upload = get_upload_or_404(db, upload_id)
    filename = upload.original_filename

    db.query(Processo).filter(Processo.upload_id == upload.id).delete(synchronize_session=False)
    db.delete(upload)
    db.commit()
    clear_analytics_cache()

    return {"message": f"Relatório {filename} excluído com sucesso."}


@app.get("/api/meta/options", response_model=FilterOptions)
def filter_options(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FilterOptions:
    return FilterOptions(**get_filter_options(db))


@app.get("/api/analytics/dashboard")
def dashboard(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters(data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_dashboard_data(db, filters))


@app.get("/api/analytics/entries-exits")
def entries_exits(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters(data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_entries_exits_data(db, filters))


@app.get("/api/analytics/productivity")
def productivity(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters(data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_productivity_data(db, filters))


@app.get("/api/analytics/stale")
def stale_processes(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters(data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_stale_processes_data(db, filters))


@app.get("/api/analytics/multi-sector")
def multi_sector(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters(data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_multi_sector_data(db, filters))
