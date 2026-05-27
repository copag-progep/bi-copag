import json
import os
from collections.abc import Callable
from statistics import median
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .analytics import (
    AnalyticsFilters,
    clear_analytics_cache,
    get_attributions_data,
    get_dashboard_data,
    get_entries_exits_data,
    get_filter_options,
    get_forecast_data,
    get_lead_time_data,
    get_multi_sector_data,
    get_productivity_data,
    get_risk_scores,
    get_server_profile,
    get_stale_processes_data,
    get_workload_balance,
)
from .auth import (
    authenticate_user,
    create_access_token,
    get_current_admin_user,
    get_current_user,
    get_current_user_or_api_key,
    get_password_hash,
    verify_password,
)
from .csv_importer import SETORES, bootstrap_workspace_csvs, import_csv_snapshot
from .database import SessionLocal, get_db, init_db
from .models import AuditLog, MonthlyStat, ProcessTypeWeight, Processo, SeiUser, Upload, User, UserSectorAccess
from .monthly_stats import MONTHLY_INDICATORS, import_monthly_stats_csv, update_monthly_stat_value, upsert_month_entry
from .schemas import (
    AuditLogRead,
    FilterOptions,
    MonthlyStatImportResult,
    PasswordChange,
    MonthlyStatMonthEntry,
    MonthlyStatRead,
    MonthlyStatUpdate,
    SeiUserAliasCreate,
    SeiUserAliasResult,
    SeiUserAttributionCandidate,
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
    add_sei_user_alias,
    delete_sei_user,
    delete_sei_user_alias,
    import_sei_users_file,
    import_sei_users_rows,
    list_attribution_candidates,
    needs_processo_atribuicoes_sync,
    sync_processo_atribuicoes,
    update_sei_user,
    upsert_sei_user,
)


DEFAULT_ADMIN_NAME = os.getenv("DEFAULT_ADMIN_NAME", "Anderson CFS")
API_UPLOAD_KEY = os.getenv("API_UPLOAD_KEY", "")
DEFAULT_ADMIN_EMAIL = os.getenv("DEFAULT_ADMIN_EMAIL", "andersoncfs@ufc.br")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")
DISABLE_STARTUP_PRECOMPUTE = os.getenv("DISABLE_STARTUP_PRECOMPUTE", "false").lower() == "true"
PRECOMPUTE_HEAVY_ANALYTICS = os.getenv("PRECOMPUTE_HEAVY_ANALYTICS", "false").lower() in {"1", "true", "yes", "on"}
LOCAL_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "America/Fortaleza"))
FRESHNESS_OK_MAX_DAYS = int(os.getenv("DATA_FRESHNESS_OK_MAX_DAYS", "3"))
FRESHNESS_CRITICAL_DAYS = int(os.getenv("DATA_FRESHNESS_CRITICAL_DAYS", "7"))
QUALITY_DROP_RATIO = float(os.getenv("DATA_QUALITY_DROP_RATIO", "0.6"))


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


_precompute_running = False
_last_precompute_started: float = 0.0

# Intervalo mínimo entre execuções consecutivas do precompute.
# Evita que lotes de uploads (6 setores) disparem 6 ciclos pesados em sequência.
_PRECOMPUTE_COOLDOWN = float(os.getenv("PRECOMPUTE_COOLDOWN_SECS", "120"))


def precompute_analytics() -> None:
    """Pré-computa endpoints analíticos leves com filtros padrão.

    Por padrão, evita endpoints de duração/carteira completa porque eles leem o
    histórico inteiro e podem disputar CPU/pool com requests reais no Render free.
    Se necessário, PRECOMPUTE_HEAVY_ANALYTICS=true inclui esses endpoints.
    """
    global _precompute_running, _last_precompute_started
    import time as _time
    if _precompute_running:
        return
    now = _time.monotonic()
    if now - _last_precompute_started < _PRECOMPUTE_COOLDOWN:
        return  # cooldown: outra execução recente já está em andamento ou terminou
    _precompute_running = True
    _last_precompute_started = now
    try:
        default_filters = AnalyticsFilters()
        steps: list[Callable] = [
            lambda db: get_filter_options(db),
            lambda db: get_dashboard_data(db, default_filters),
            lambda db: get_entries_exits_data(db, default_filters),
            lambda db: get_productivity_data(db, default_filters),
            lambda db: get_multi_sector_data(db, default_filters),
            lambda db: get_workload_balance(db, default_filters),
        ]
        if PRECOMPUTE_HEAVY_ANALYTICS:
            steps.extend(
                [
                    lambda db: get_stale_processes_data(db, default_filters),
                    lambda db: get_lead_time_data(db, default_filters),
                    lambda db: get_attributions_data(db, default_filters),
                    lambda db: get_forecast_data(db, default_filters),
                    lambda db: get_risk_scores(db, default_filters),
                ]
            )
        for step in steps:
            db = SessionLocal()
            try:
                step(db)
            except Exception:
                pass
            finally:
                db.close()
    finally:
        _precompute_running = False


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
    if not DISABLE_STARTUP_PRECOMPUTE:
        threading.Thread(target=precompute_analytics, daemon=True).start()
    yield


app = FastAPI(
    title="AnalyticSEI API",
    version="1.0.0",
    description="API para importacao de relatorios SEI e analise de processos administrativos.",
    lifespan=lifespan,
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
origins.extend([origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()])

app.add_middleware(GZipMiddleware, minimum_size=512)
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


def get_user_setores(user: User, db: Session) -> tuple[str, ...] | None:
    """Retorna os setores que o usuário pode acessar.

    None  → admin ou API key — sem restrição alguma.
    ()    → não-admin sem setores configurados — sem acesso a dado algum.
    (str,…) → não-admin com setores explícitos — só vê esses.
    """
    if user.is_admin:
        return None
    rows = (
        db.query(UserSectorAccess.setor)
        .filter(UserSectorAccess.user_id == user.id)
        .all()
    )
    return tuple(row[0].upper() for row in rows)


def build_filters_for_user(
    current_user: User,
    db: Session,
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
) -> AnalyticsFilters:
    """Constrói AnalyticsFilters com o controle de acesso por divisão do usuário.

    Se o usuário solicitou um setor específico que não está na sua lista, lança 403.
    """
    normalized_setor = setor.upper().strip() if setor else None
    setores_permitidos = get_user_setores(current_user, db)

    if setores_permitidos is not None and normalized_setor:
        if normalized_setor not in setores_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acesso não autorizado ao setor {normalized_setor}.",
            )

    return AnalyticsFilters(
        data_referencia=data_referencia,
        data_inicial=data_inicial,
        data_final=data_final,
        setor=normalized_setor,
        tipo=tipo,
        atribuicao=atribuicao,
        setores_permitidos=setores_permitidos,
    )


def _log_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
    user: User,
) -> None:
    """Registra uma entrada no log de auditoria sem fazer commit."""
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=json.dumps(details, ensure_ascii=False, default=str) if details else None,
        user_email=user.email,
        user_name=user.name,
    )
    db.add(entry)


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


@app.get("/api/ping")
def ping() -> dict:
    """Endpoint leve para keep-alive — não consulta o banco."""
    return {"status": "ok"}


@app.get("/api/health")
def healthcheck(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable.")


def _iso_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _freshness_status(age_days: int | None, lagging: list[str], missing: list[str], quality_alerts: list[dict]) -> str:
    if age_days is None:
        return "no_data"
    if age_days > FRESHNESS_CRITICAL_DAYS:
        return "critical"
    if missing or lagging or quality_alerts or age_days > FRESHNESS_OK_MAX_DAYS:
        return "attention"
    return "ok"


@app.get("/api/health/data-freshness")
def data_freshness(
    _: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Resumo de frescor e completude dos snapshots importados.

    A checagem usa somente a tabela de uploads para ser rápida e barata:
    identifica a data global mais recente, o último snapshot por setor e
    possíveis setores ausentes/defasados antes de o gestor interpretar os painéis.
    """
    reference_date = db.query(func.max(Upload.data_relatorio)).scalar()
    today = datetime.now(LOCAL_TIMEZONE).date()

    sectors: list[dict] = []
    missing_sectors: list[str] = []
    lagging_sectors: list[str] = []
    current_sectors: list[str] = []
    quality_alerts: list[dict] = []

    for setor in SETORES:
        latest = (
            db.query(Upload)
            .filter(Upload.setor == setor)
            .order_by(Upload.data_relatorio.desc(), Upload.data_upload.desc(), Upload.id.desc())
            .first()
        )

        if not latest:
            missing_sectors.append(setor)
            sectors.append(
                {
                    "setor": setor,
                    "status": "missing",
                    "data_relatorio": None,
                    "data_upload": None,
                    "total_records": 0,
                    "expected_reference_date": str(reference_date) if reference_date else None,
                    "quality_alert": None,
                }
            )
            continue

        setor_status = "current" if reference_date and latest.data_relatorio == reference_date else "lagging"
        if setor_status == "current":
            current_sectors.append(setor)
        else:
            lagging_sectors.append(setor)

        recent_counts = [
            row[0]
            for row in (
                db.query(Upload.total_records)
                .filter(Upload.setor == setor, Upload.data_relatorio < latest.data_relatorio)
                .order_by(Upload.data_relatorio.desc(), Upload.data_upload.desc())
                .limit(5)
                .all()
            )
            if row[0] is not None and row[0] > 0
        ]
        baseline = median(recent_counts) if recent_counts else None
        quality_alert = None
        if latest.total_records <= 0:
            quality_alert = {
                "type": "empty_snapshot",
                "message": "Snapshot sem registros importados.",
            }
        elif baseline and baseline >= 10 and latest.total_records < baseline * QUALITY_DROP_RATIO:
            quality_alert = {
                "type": "volume_drop",
                "message": "Volume muito abaixo do histórico recente.",
                "baseline_records": int(round(baseline)),
                "drop_ratio": round(latest.total_records / baseline, 2),
            }

        if quality_alert:
            quality_alerts.append({"setor": setor, **quality_alert})

        sectors.append(
            {
                "setor": setor,
                "status": setor_status,
                "data_relatorio": str(latest.data_relatorio),
                "data_upload": _iso_datetime(latest.data_upload),
                "total_records": latest.total_records,
                "expected_reference_date": str(reference_date) if reference_date else None,
                "quality_alert": quality_alert,
            }
        )

    age_days = (today - reference_date).days if reference_date else None
    status_label = _freshness_status(age_days, lagging_sectors, missing_sectors, quality_alerts)

    return JSONResponse(
        {
            "status": status_label,
            "data_referencia_global": str(reference_date) if reference_date else None,
            "hoje": str(today),
            "idade_dias": age_days,
            "setores_esperados": SETORES,
            "setores_em_dia": current_sectors,
            "setores_defasados": lagging_sectors,
            "setores_ausentes": missing_sectors,
            "total_setores_esperados": len(SETORES),
            "total_setores_em_dia": len(current_sectors),
            "alertas_qualidade": quality_alerts,
            "setores": sectors,
        }
    )


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


@app.patch("/api/auth/password")
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.senha_atual, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Senha atual incorreta.",
        )
    current_user.password_hash = get_password_hash(payload.nova_senha)
    _log_audit(db, action="senha.alterada", entity_type="usuario", user=current_user)
    db.commit()
    return {"message": "Senha alterada com sucesso."}


@app.get("/api/processes/search")
def process_search(
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q_clean = q.strip()
    setores_permitidos = get_user_setores(current_user, db)

    query = db.query(Processo).filter(Processo.protocolo.ilike(f"%{q_clean}%"))
    if setores_permitidos is not None:
        if len(setores_permitidos) == 0:
            return JSONResponse({"q": q_clean, "encontrado": False, "total": 0, "resultados": []})
        query = query.filter(Processo.setor.in_(setores_permitidos))

    rows = (
        query
        .order_by(Processo.protocolo.asc(), Processo.data_relatorio.asc())
        .limit(500)
        .all()
    )

    if not rows:
        return JSONResponse({"q": q_clean, "encontrado": False, "total": 0, "resultados": []})

    by_proto: dict[str, list] = {}
    for r in rows:
        by_proto.setdefault(r.protocolo, []).append(r)

    resultados = []
    for proto, proto_rows in sorted(by_proto.items()):
        last = proto_rows[-1]
        last_date = str(last.data_relatorio)

        spans: list[dict] = []
        current: dict | None = None
        for r in proto_rows:
            atrib = r.atribuicao_normalizada or r.atribuicao
            if current and r.setor == current["setor"] and atrib == current["atribuicao"]:
                current["data_saida"] = str(r.data_relatorio)
            else:
                if current:
                    spans.append(current)
                current = {
                    "setor": r.setor,
                    "atribuicao": atrib,
                    "tipo": r.tipo or "—",
                    "data_entrada": str(r.data_relatorio),
                    "data_saida": str(r.data_relatorio),
                    "ativa": False,
                }
        if current:
            current["ativa"] = current["data_saida"] == last_date
            spans.append(current)

        resultados.append({
            "protocolo": proto,
            "tipo": last.tipo or "—",
            "especificacao": last.especificacao or "",
            "setor_atual": last.setor,
            "atribuicao_atual": last.atribuicao_normalizada or last.atribuicao,
            "data_primeira": str(proto_rows[0].data_relatorio),
            "data_ultima": last_date,
            "historico": spans,
        })

    return JSONResponse({
        "q": q_clean,
        "encontrado": True,
        "total": len(resultados),
        "resultados": resultados[:20],
    })


@app.get("/api/admin/users", response_model=list[UserRead])
def list_users(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[User]:
    return db.query(User).order_by(User.name.asc()).all()


@app.post("/api/admin/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_admin: User = Depends(get_current_admin_user),
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
    db.flush()
    _log_audit(db, action="usuario.criado", entity_type="usuario",
               entity_id=str(user.id),
               details={"nome": user.name, "email": user.email, "is_admin": user.is_admin},
               user=current_admin)
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
    _log_audit(db, action="usuario.excluido", entity_type="usuario",
               entity_id=str(user.id),
               details={"nome": user.name, "email": user.email},
               user=current_admin)
    db.delete(user)
    db.commit()
    return {"message": f"Usuario {name} excluido com sucesso."}


@app.get("/api/admin/sei-users", response_model=list[SeiUserRead])
def list_sei_users(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[SeiUser]:
    return db.query(SeiUser).options(selectinload(SeiUser.aliases)).order_by(SeiUser.nome.asc()).all()


@app.get("/api/admin/sei-users/attribution-candidates", response_model=list[SeiUserAttributionCandidate])
def list_sei_user_attribution_candidates(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return list_attribution_candidates(db)


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


@app.put("/api/admin/sei-users/{sei_user_id}", response_model=SeiUserRead)
def edit_sei_user(
    sei_user_id: int,
    payload: SeiUserCreate,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> SeiUser:
    sei_user = update_sei_user(db, sei_user_id, payload.nome, payload.nome_sei, payload.usuario_sei)
    changed = sync_processo_atribuicoes(db)
    _log_audit(
        db,
        action="sei_usuario.editado",
        entity_type="sei_usuario",
        entity_id=str(sei_user_id),
        details={
            "nome": sei_user.nome,
            "nome_sei": sei_user.nome_sei,
            "usuario_sei": sei_user.usuario_sei,
            "processos_atualizados": changed,
        },
        user=current_admin,
    )
    db.commit()
    db.refresh(sei_user)
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return sei_user


@app.post("/api/admin/sei-users/{sei_user_id}/aliases", response_model=SeiUserAliasResult)
def create_sei_user_alias(
    sei_user_id: int,
    payload: SeiUserAliasCreate,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> SeiUserAliasResult:
    result = add_sei_user_alias(db, sei_user_id, payload.alias, merge_existing=payload.merge_existing)
    changed = sync_processo_atribuicoes(db)
    _log_audit(
        db,
        action="sei_usuario.unificado" if result.get("merged_user") else "sei_usuario.alias_adicionado",
        entity_type="sei_usuario",
        entity_id=str(sei_user_id),
        details={
            "usuario_principal": result.get("target_user"),
            "alias": result.get("alias"),
            "usuario_unificado": result.get("merged_user"),
            "processos_atualizados": changed,
        },
        user=current_admin,
    )
    db.commit()
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)

    if result.get("merged_user"):
        message = (
            f"Historico de {result['merged_user']} unido a {result['target_user']}. "
            f"{changed} processos foram ressincronizados."
        )
    else:
        message = f"Alias historico {result['alias']} vinculado com sucesso."

    return SeiUserAliasResult(
        message=message,
        alias=str(result["alias"]),
        merged_user=result.get("merged_user"),
        changed_processes=changed,
    )


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


@app.delete("/api/admin/sei-users/aliases/{alias_id}")
def remove_sei_user_alias(
    alias_id: int,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    alias = delete_sei_user_alias(db, alias_id)
    changed = sync_processo_atribuicoes(db)
    _log_audit(
        db,
        action="sei_usuario.alias_removido",
        entity_type="sei_usuario_alias",
        entity_id=str(alias_id),
        details={"alias": alias, "processos_atualizados": changed},
        user=current_admin,
    )
    db.commit()
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return {"message": f"Alias historico {alias} removido com sucesso."}


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
    current_user: User = Depends(get_current_user),
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
        _log_audit(db, action=f"upload.{result['status']}", entity_type="upload",
                   entity_id=result["setor"],
                   details={"arquivo": result["original_filename"], "setor": result["setor"],
                            "data_relatorio": str(result["data_relatorio"]),
                            "registros": result["total_registros"]},
                   user=current_user)
        db.commit()

    return UploadResult(**result)


@app.post("/api/upload-with-key", response_model=UploadResult)
async def upload_snapshot_api_key(
    background_tasks: BackgroundTasks,
    setor: str = Form(...),
    data_relatorio: date = Form(...),
    file: UploadFile = File(...),
    x_api_key: str = Header(..., alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> UploadResult:
    """Endpoint para upload automático via API key (sem JWT). Usado pelo script SEI → AnalyticSEI."""
    if not API_UPLOAD_KEY or x_api_key != API_UPLOAD_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key inválida.")
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Falha ao importar CSV.") from exc

    if result["status"] in {"imported", "replaced"}:
        bot = User(name="Automação SEI", email="automacao@sistema", password_hash="", is_admin=True)
        _log_audit(
            db,
            action=f"upload.{result['status']}",
            entity_type="upload",
            entity_id=result["setor"],
            details={
                "arquivo": result["original_filename"],
                "setor": result["setor"],
                "data_relatorio": str(result["data_relatorio"]),
                "registros": result["total_registros"],
                "origem": "automacao",
            },
            user=bot,
        )
        db.commit()
        clear_analytics_cache()
        background_tasks.add_task(precompute_analytics)

    return UploadResult(**result)


@app.patch("/api/uploads/{upload_id}", response_model=UploadRead)
def update_upload(
    upload_id: int,
    payload: UploadUpdate,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin_user),
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
    _log_audit(db, action="upload.data_alterada", entity_type="upload",
               entity_id=str(upload.id),
               details={"arquivo": upload.original_filename, "setor": upload.setor,
                        "data_nova": str(payload.data_relatorio)},
               user=current_admin)
    db.commit()
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)
    return upload


@app.delete("/api/uploads/{upload_id}")
def delete_upload(
    upload_id: int,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    upload = get_upload_or_404(db, upload_id)
    filename = upload.original_filename

    db.query(Processo).filter(Processo.upload_id == upload.id).delete(synchronize_session=False)
    db.delete(upload)
    _log_audit(db, action="upload.excluido", entity_type="upload",
               entity_id=str(upload_id),
               details={"arquivo": filename, "setor": upload.setor,
                        "data_relatorio": str(upload.data_relatorio)},
               user=current_admin)
    db.commit()
    clear_analytics_cache()
    background_tasks.add_task(precompute_analytics)

    return {"message": f"Relatorio {filename} excluido com sucesso."}


@app.get("/api/admin/audit-logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> dict:
    total = db.query(AuditLog).count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    items = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [AuditLogRead.model_validate(item).model_dump(mode="json") for item in items],
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size,
    }


# ── Pesos por tipo de processo (Score de Risco) ───────────────────────────

class TypeWeightUpsert(BaseModel):
    tipo: str
    peso: float = Field(default=1.00, ge=0.80, le=1.50)
    categoria: str | None = None
    justificativa: str | None = None
    ativo: bool = True


@app.get("/api/admin/type-weights")
def list_type_weights(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Lista todos os tipos conhecidos com seus pesos configurados.

    Retorna a união de:
    - Tipos com peso explícito na tabela process_type_weights
    - Tipos distintos existentes nos processos mas sem peso configurado (peso implícito 1.00)

    Assim o admin sempre vê todos os tipos, incluindo novos que entraram via upload.
    """
    configured: dict[str, ProcessTypeWeight] = {
        w.tipo: w
        for w in db.query(ProcessTypeWeight).order_by(ProcessTypeWeight.tipo).all()
    }
    # Contagem de registros por tipo — ajuda o admin a calibrar pesos com contexto
    type_counts: dict[str, int] = {
        row[0]: int(row[1])
        for row in db.query(Processo.tipo, func.count(Processo.id))
        .filter(Processo.tipo.is_not(None), Processo.tipo != "")
        .group_by(Processo.tipo)
        .all()
        if row[0]
    }
    known_types: list[str] = sorted(type_counts.keys())

    def _row(tipo: str, w: ProcessTypeWeight | None) -> dict:
        base = {
            "tipo": tipo,
            "total_processos": type_counts.get(tipo, 0),
        }
        if w:
            base.update({
                "id": w.id,
                "peso": float(w.peso),
                "categoria": w.categoria,
                "justificativa": w.justificativa,
                "ativo": w.ativo,
                "configurado": True,
                "updated_at": w.updated_at.isoformat() if w.updated_at else None,
            })
        else:
            base.update({
                "id": None,
                "peso": 1.00,
                "categoria": None,
                "justificativa": None,
                "ativo": True,
                "configurado": False,
                "updated_at": None,
            })
        return base

    result = [_row(tipo, configured.get(tipo)) for tipo in known_types]

    # Pesos configurados para tipos que já não existem nos processos (históricos)
    for tipo, w in configured.items():
        if tipo not in type_counts:
            result.append(_row(tipo, w))

    result.sort(key=lambda x: x["tipo"].lower())
    return result


@app.put("/api/admin/type-weights")
def upsert_type_weight(
    payload: TypeWeightUpsert,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Cria ou atualiza o peso de um tipo de processo.

    Idempotente: se o tipo já existe, atualiza; senão, insere.
    Invalida o cache do Score de Risco automaticamente.
    """
    existing = db.query(ProcessTypeWeight).filter(ProcessTypeWeight.tipo == payload.tipo).first()
    old_peso = float(existing.peso) if existing else None
    if existing:
        existing.peso = payload.peso
        existing.categoria = payload.categoria
        existing.justificativa = payload.justificativa
        existing.ativo = payload.ativo
        existing.updated_at = datetime.now(timezone.utc)
    else:
        db.add(ProcessTypeWeight(
            tipo=payload.tipo,
            peso=payload.peso,
            categoria=payload.categoria,
            justificativa=payload.justificativa,
            ativo=payload.ativo,
        ))
    _log_audit(
        db,
        action="process_type_weight.salvo",
        entity_type="process_type_weight",
        entity_id=payload.tipo,
        details={
            "peso_anterior": old_peso,
            "peso_novo": payload.peso,
            "categoria": payload.categoria,
            "ativo": payload.ativo,
        },
        user=current_admin,
    )
    db.commit()
    clear_analytics_cache()
    return {"ok": True, "tipo": payload.tipo, "peso": payload.peso}


@app.delete("/api/admin/type-weights/{weight_id}")
def delete_type_weight(
    weight_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Remove o peso configurado de um tipo (volta ao padrão 1.00 implícito)."""
    w = db.query(ProcessTypeWeight).filter(ProcessTypeWeight.id == weight_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="Peso não encontrado.")
    tipo_removido = w.tipo
    peso_removido = float(w.peso)
    db.delete(w)
    _log_audit(
        db,
        action="process_type_weight.removido",
        entity_type="process_type_weight",
        entity_id=tipo_removido,
        details={"peso_removido": peso_removido},
        user=current_admin,
    )
    db.commit()
    clear_analytics_cache()
    return {"ok": True, "message": f"Peso de '{tipo_removido}' removido. Voltará ao padrão 1.00."}


# ── Controle de acesso por divisão (setores por usuário) ─────────────────

class UserSectorsUpdate(BaseModel):
    setores: list[str]


@app.get("/api/admin/users/{user_id}/sectors")
def get_user_sectors(
    user_id: int,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Lista os setores liberados para um usuário (vazio = sem acesso)."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    rows = db.query(UserSectorAccess.setor).filter(UserSectorAccess.user_id == user_id).all()
    return {
        "user_id": user_id,
        "email": target.email,
        "is_admin": target.is_admin,
        "setores": sorted(row[0] for row in rows),
    }


@app.put("/api/admin/users/{user_id}/sectors")
def update_user_sectors(
    user_id: int,
    payload: UserSectorsUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Redefine a lista completa de setores de um usuário.

    Substituição total: enviar [] remove todas as restrições (sem acesso).
    Administradores não podem ter setores restritos.
    """
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if target.is_admin:
        raise HTTPException(
            status_code=400,
            detail="Administradores têm acesso total — setores não se aplicam.",
        )

    old_rows = db.query(UserSectorAccess.setor).filter(UserSectorAccess.user_id == user_id).all()
    old_setores = sorted(row[0] for row in old_rows)

    # Substituição completa
    db.query(UserSectorAccess).filter(UserSectorAccess.user_id == user_id).delete()
    new_setores = sorted({s.upper().strip() for s in payload.setores if s.strip()})
    for setor in new_setores:
        db.add(UserSectorAccess(user_id=user_id, setor=setor))

    _log_audit(
        db,
        action="usuario.setores_atualizados",
        entity_type="usuario",
        entity_id=str(user_id),
        details={
            "email": target.email,
            "setores_anteriores": old_setores,
            "setores_novos": new_setores,
        },
        user=current_admin,
    )
    db.commit()
    # Invalida cache analítico para que as novas restrições entrem em vigor imediatamente
    clear_analytics_cache()
    return {"ok": True, "user_id": user_id, "setores": new_setores}


@app.get("/api/alerts/summary")
def alerts_summary(
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Resumo rápido de processos críticos para o sino de notificações.
    Usa o cache do stale-processes — resposta muito rápida."""
    stale = get_stale_processes_data(db, AnalyticsFilters(setores_permitidos=get_user_setores(current_user, db)))
    processos = stale.get("processos", [])

    def conta(min_dias: int) -> int:
        return sum(1 for p in processos if p.get("dias_sem_movimentacao", 0) >= min_dias)

    criticos = sorted(
        [p for p in processos if p.get("dias_sem_movimentacao", 0) >= 45],
        key=lambda p: -p.get("dias_sem_movimentacao", 0),
    )[:8]

    return JSONResponse({
        "mais_de_30":    conta(30),
        "mais_de_45":    conta(45),
        "mais_de_90":    conta(90),
        "total_badge":   conta(45),
        "criticos":      criticos,
        "data_referencia": stale.get("data_referencia"),
    })


@app.get("/api/meta/options", response_model=FilterOptions)
def filter_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FilterOptions:
    opts = get_filter_options(db)
    opts["setores_validos"] = SETORES
    setores_permitidos = get_user_setores(current_user, db)
    if setores_permitidos is not None:
        # Restringe a lista de setores no dropdown ao que o usuário pode ver
        opts["setores"] = [s for s in opts["setores"] if s in setores_permitidos]
        opts["setor_restrito"] = True
        opts["setores_do_usuario"] = list(setores_permitidos)
    else:
        opts["setor_restrito"] = False
        opts["setores_do_usuario"] = []
    return FilterOptions(**opts)


@app.get("/api/analytics/dashboard")
def dashboard(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_dashboard_data(db, filters))


@app.get("/api/analytics/entries-exits")
def entries_exits(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_entries_exits_data(db, filters))


@app.get("/api/analytics/productivity")
def productivity(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_productivity_data(db, filters))


@app.get("/api/analytics/stale")
def stale_processes(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_stale_processes_data(db, filters))


@app.get("/api/analytics/lead-time")
def lead_time(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_lead_time_data(db, filters))


@app.get("/api/analytics/forecast")
def forecast(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Tendências estimadas de volume, saldo setorial e processos em envelhecimento.
    Carregado sob demanda pela Central Executiva — não incluído no precompute."""
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_forecast_data(db, filters))


@app.get("/api/analytics/risk-score")
def risk_score(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Score de risco composto por processo ativo.

    Carregado sob demanda — incluído no precompute apenas se
    PRECOMPUTE_HEAVY_ANALYTICS=true. Score é sobre o processo,
    não sobre o servidor atribuído.
    """
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_risk_scores(db, filters))


@app.get("/api/analytics/attributions")
def attributions_list(
    data_referencia: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    min_dias: int | None = Query(None, ge=0),
    max_dias: int | None = Query(None, ge=0),
    sem_atribuicao: bool = Query(False),
    sort_by: str = Query("dias"),
    sort_dir: str = Query("desc"),
    protocolo_busca: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=5000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, None, None, setor, tipo, atribuicao)
    result = get_attributions_data(db, filters)

    all_items = result["items"]

    if sem_atribuicao:
        all_items = [item for item in all_items if item["atribuicao"] is None]

    if min_dias is not None:
        all_items = [item for item in all_items if item["dias_com_atribuicao"] >= min_dias]
    if max_dias is not None:
        all_items = [item for item in all_items if item["dias_com_atribuicao"] <= max_dias]

    if protocolo_busca:
        busca = protocolo_busca.strip().lower()
        all_items = [item for item in all_items if busca in item["protocolo"].lower()]

    reverse = sort_dir == "desc"
    if sort_by == "atribuicao":
        all_items = sorted(all_items, key=lambda x: (x["atribuicao"] or "").lower(), reverse=reverse)
    elif sort_by == "tipo":
        all_items = sorted(all_items, key=lambda x: (x["tipo"] or "").lower(), reverse=reverse)
    elif sort_by == "dias" and sort_dir == "asc":
        all_items = list(reversed(all_items))

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


@app.get("/api/analytics/workload-balance")
def workload_balance_endpoint(
    data_referencia: date | None = None,
    setor: str | None = None,
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, None, None, setor, None, None)
    return JSONResponse(get_workload_balance(db, filters))


@app.get("/api/analytics/server-profile")
def server_profile_endpoint(
    atribuicao: str = Query(..., min_length=1),
    data_referencia: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, None, None, None, None, atribuicao)
    return JSONResponse(get_server_profile(db, filters))


@app.get("/api/analytics/multi-sector")
def multi_sector(
    data_referencia: date | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    setor: str | None = None,
    tipo: str | None = None,
    atribuicao: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = build_filters_for_user(current_user, db, data_referencia, data_inicial, data_final, setor, tipo, atribuicao)
    return JSONResponse(get_multi_sector_data(db, filters))


@app.get("/api/reports/daily-summary")
def daily_summary(
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Resumo diário compacto — usado pelo relatório WhatsApp e scripts externos.

    Agrega dashboard, fluxo do dia e críticos em uma única chamada leve,
    evitando que scripts externos façam múltiplas requisições analíticas pesadas.
    """
    filters = AnalyticsFilters(setores_permitidos=get_user_setores(current_user, db))
    dashboard_data = get_dashboard_data(db, filters)
    flow_data      = get_entries_exits_data(db, filters)
    stale_data     = get_stale_processes_data(db, filters)

    resumo  = flow_data.get("resumo_setorial", [])
    total_e = sum(s["entradas"] for s in resumo)
    total_s = sum(s["saidas"]   for s in resumo)

    processos_parados = stale_data.get("processos", [])

    return JSONResponse({
        "data_referencia": dashboard_data.get("data_referencia"),
        "total_ativos":    dashboard_data.get("kpis", {}).get("total_processos_ativos", 0),
        "delta_dia":       total_e - total_s,
        "entradas_dia":    total_e,
        "saidas_dia":      total_s,
        "setores": [
            {
                "setor":    s["setor"],
                "ativos":   s["carga_atual"],
                "entradas": s["entradas"],
                "saidas":   s["saidas"],
            }
            for s in sorted(resumo, key=lambda x: -x["carga_atual"])
        ],
        "criticos_30d": stale_data.get("contagens", {}).get("mais_de_30", 0),
        "criticos_90d": sum(
            1 for p in processos_parados
            if p.get("dias_sem_movimentacao", 0) >= 90  # >= para alinhar com faixa "extreme" do sistema
        ),
    })
