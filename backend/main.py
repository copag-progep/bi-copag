import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .analytics import (
    AnalyticsFilters,
    clear_analytics_cache,
    get_attributions_data,
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
from .models import MonthlyStat, Processo, SeiUser, Upload, User
from .monthly_stats import MONTHLY_INDICATORS, import_monthly_stats_csv, update_monthly_stat_value, upsert_month_entry
from .schemas import (
    FilterOptions,
    MonthlyStatImportResult,
    MonthlyStatMonthEntry,
    MonthlyStatRead,
    MonthlyStatUpdate,
    SeiUserBulkImport,
    SeiUserCreate,
    SeiUserImportResult,
    SeiUserRead,
    Token,
    UploadListResponse,
    UploadRead,
    UploadResult,
    UploadUpdate,
    UserCreate,
    UserLogin,
    UserRead,
)
from .sei_users import (
    delete_sei_user,
    import_sei_users_file,
    import_sei_users_rows,
    needs_processo_atribuicoes_sync,
    sync_processo_atribuicoes,
    upsert_sei_user,
)


DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "Anderson CFS")
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "andersoncfs@ufc.br")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")


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


def precompute_analytics() -> None:
    db = SessionLocal()
    try:
        default_filters = AnalyticsFilters()
        get_filter_options(db)
        get_dashboard_data(db, default_filters)
        get_entries_exits_data(db, default_filters)
        get_productivity_data(db, default_filters)
        get_stale_processes_data(db, default_filters)
        get_multi_sector_data(db, default_filters)
        get_attributions_data(db, default_filters)
    except Exception:
        pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_default_user()
    auto_import_workspace_data()
    db = SessionLocal()
    try:
        if needs_processo_atribuicoes_sync(db):
            sync_processo_atribuicoes(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="SEI BI API",
    version="1.0.0",
    description="API para importacao de relatorios SEI e analise de processos administrativos.",
    lifespan=lifespan,
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


def get_upload_or_404(db: Session, upload_id: int) -> Upload:
    upload = db.query(Upload).filter(Upload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relatorio nao encontrado.")
    return upload


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado.")
    return user


@app.get("/api/health")
def healthcheck(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable.")


@app.post("/api/auth/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha invalidos.")
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ja existe um usuario com este email.")

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


@app.delete("/api/admin/users/{user_id}")
def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    user = get_user_or_404(db, user_id)
    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voce nao pode excluir a propria conta.",
        )

    if user.is_admin:
        admin_count = db.query(User).filter(User.is_admin.is_(True)).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nao e possivel excluir o ultimo administrador do sistema.",
            )

    name = user.name
    db.delete(user)
    db.commit()
    return {"message": f"Usuario {name} excluido com sucesso."}


@app.get("/api/admin/sei-users", response_model=list[SeiUserRead])
def list_sei_users(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[SeiUser]:
    return db.query(SeiUser).order_by(SeiUser.nome.asc()).all()


@app.post("/api/admin/sei-users", response_model=SeiUserRead, status_code=status.HTTP_201_CREATED)
def create_sei_user(
    payload: SeiUserCreate,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> SeiUser:
    _, sei_user = upsert_sei_user(db, payload.nome, payload.nome_sei, payload.usuario_sei)
    db.commit()
    db.refresh(sei_user)
    sync_processo_atribuicoes(db)
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return sei_user


@app.post("/api/admin/sei-users/import", response_model=SeiUserImportResult, status_code=status.HTTP_201_CREATED)
async def import_sei_users(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> SeiUserImportResult:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")

    result = import_sei_users_file(db, file.filename or "usuarios_sei.xls", file_bytes)
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return SeiUserImportResult(**result)


@app.post("/api/admin/sei-users/import-rows", response_model=SeiUserImportResult, status_code=status.HTTP_201_CREATED)
def import_sei_users_rows_endpoint(
    payload: SeiUserBulkImport,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> SeiUserImportResult:
    result = import_sei_users_rows(db, [row.model_dump() for row in payload.rows])
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return SeiUserImportResult(**result)


@app.delete("/api/admin/sei-users/{sei_user_id}")
def remove_sei_user(
    sei_user_id: int,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    name = delete_sei_user(db, sei_user_id)
    sync_processo_atribuicoes(db)
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return {"message": f"Usuario SEI {name} excluido com sucesso."}


@app.get("/api/monthly-stats")
def list_monthly_stats(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.query(MonthlyStat).order_by(MonthlyStat.periodo.asc(), MonthlyStat.setor.asc(), MonthlyStat.indicador.asc()).all()
    return {
        "rows": [MonthlyStatRead.model_validate(row).model_dump(mode="json") for row in rows],
        "setores": sorted({row.setor for row in rows}),
        "indicadores": list(MONTHLY_INDICATORS),
        "anos": sorted({row.ano for row in rows}),
    }


@app.post("/api/admin/monthly-stats/import", response_model=MonthlyStatImportResult, status_code=status.HTTP_201_CREATED)
async def import_monthly_stats(
    file: UploadFile = File(...),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> MonthlyStatImportResult:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Envie um arquivo CSV mensal.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Arquivo vazio.")

    result = import_monthly_stats_csv(db, file_bytes)
    return MonthlyStatImportResult(**result)


@app.post("/api/admin/monthly-stats/month-entry", response_model=MonthlyStatImportResult, status_code=status.HTTP_201_CREATED)
def save_monthly_stats_entry(
    payload: MonthlyStatMonthEntry,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> MonthlyStatImportResult:
    result = upsert_month_entry(db, payload.model_dump())
    return MonthlyStatImportResult(**result)


@app.patch("/api/admin/monthly-stats/{stat_id}", response_model=MonthlyStatRead)
def update_monthly_stat(
    stat_id: int,
    payload: MonthlyStatUpdate,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> MonthlyStat:
    return update_monthly_stat_value(db, stat_id, payload.valor)


@app.get("/api/uploads", response_model=UploadListResponse)
def list_uploads(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadListResponse:
    total = db.query(Upload).count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    items = (
        db.query(Upload)
        .order_by(Upload.data_relatorio.desc(), Upload.data_upload.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UploadListResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )


@app.post("/api/uploads", response_model=UploadResult)
async def upload_snapshot(
    background_tasks: BackgroundTasks,
    setor: str = Form(...),
    data_relatorio: date = Form(...),
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadResult:
    if setor.upper() not in SETORES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setor invalido.")
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
        background_tasks.add_task(precompute_analytics)

    return UploadResult(**result)


@app.patch("/api/uploads/{upload_id}", response_model=UploadRead)
def update_upload(
    upload_id: int,
    payload: UploadUpdate,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_admin_user),
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
            detail="Ja existe um relatorio deste setor com a data informada.",
        )

    processo_conflict = (
        db.query(Processo.id)
        .filter(
            Processo.upload_id != upload.id,
            Processo.setor == upload.setor,
            Processo.data_relatorio == payload.data_relatorio,
        )
        .first()
    )
    if processo_conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ja existem processos deste setor com a data informada. Exclua o snapshot conflitante antes de alterar a data.",
        )

    try:
        db.query(Processo).filter(Processo.upload_id == upload.id).update(
            {Processo.data_relatorio: payload.data_relatorio},
            synchronize_session=False,
        )
        upload.data_relatorio = payload.data_relatorio
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data informada gera conflito com processos ja existentes para este setor.",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao atualizar a data do relatorio.",
        ) from exc

    db.refresh(upload)
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return upload


@app.delete("/api/uploads/{upload_id}")
def delete_upload(
    upload_id: int,
    background_tasks: BackgroundTasks,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    upload = get_upload_or_404(db, upload_id)
    filename = upload.original_filename

    db.query(Processo).filter(Processo.upload_id == upload.id).delete(synchronize_session=False)
    db.delete(upload)
    db.commit()
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)

    return {"message": f"Relatorio {filename} excluido com sucesso."}


@app.get("/api/meta/options", response_model=FilterOptions)
def filter_options(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FilterOptions:
    opts = get_filter_options(db)
    opts["setores_validos"] = SETORES
    return FilterOptions(**opts)


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


@app.get("/api/analytics/attributions")
def attributions_list(
    data_referencia: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    min_dias: int | None = Query(None, ge=0),
    max_dias: int | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters(data_referencia, None, None, setor, tipo, atribuicao)
    result = get_attributions_data(db, filters)

    all_items = result["items"]
    if min_dias is not None:
        all_items = [item for item in all_items if item["dias_com_atribuicao"] >= min_dias]
    if max_dias is not None:
        all_items = [item for item in all_items if item["dias_com_atribuicao"] <= max_dias]

    total = len(all_items)
    total_pages = max((total + page_size - 1) // page_size, 1)
    start = (page - 1) * page_size

    return JSONResponse({
        "data_referencia": result["data_referencia"],
        "items": all_items[start: start + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "total_com_atribuicao": result["total_com_atribuicao"],
        "total_sem_atribuicao": result["total_sem_atribuicao"],
        "max_dias": result["max_dias"],
    })


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
