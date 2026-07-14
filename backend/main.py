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
from sqlalchemy import func, or_, text
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
from .models import AuditLog, MonthlyStat, PautaItem, PautaSessao, ProcessTypeWeight, Processo, SeiUser, SeiUserSetor, Upload, User, UserSectorAccess
from .monthly_stats import MONTHLY_INDICATORS, import_monthly_stats_csv, update_monthly_stat_value, upsert_month_entry
from .schemas import (
    AdminUserRead,
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


# Desativa os pré-cálculos automáticos disparados após uploads e alterações
# administrativas. Em instâncias com pouca RAM (Render Free), cada precompute
# reconstrói vários DataFrames em sequência — DISABLE_POST_CHANGE_PRECOMPUTE=true
# deixa o cache ser populado sob demanda pelo primeiro acesso de cada página.
DISABLE_POST_CHANGE_PRECOMPUTE = os.getenv("DISABLE_POST_CHANGE_PRECOMPUTE", "false").lower() in {"1", "true", "yes", "on"}


def precompute_analytics() -> None:
    """Pré-computa endpoints analíticos leves com filtros padrão.

    Por padrão, evita endpoints de duração/carteira completa porque eles leem o
    histórico inteiro e podem disputar CPU/pool com requests reais no Render free.
    Se necessário, PRECOMPUTE_HEAVY_ANALYTICS=true inclui esses endpoints.
    """
    global _precompute_running, _last_precompute_started
    import time as _time
    if DISABLE_POST_CHANGE_PRECOMPUTE:
        return
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


def run_noncritical_startup_tasks() -> None:
    """Executa rotinas úteis, mas não essenciais para a API aceitar tráfego.

    No Render Free, qualquer bloqueio no lifespan atrasa a abertura da porta e
    pode fazer o healthcheck falhar com connection refused. Por isso deixamos
    apenas migrações e criação do admin no caminho crítico de startup.
    """
    try:
        auto_import_workspace_data()
    except Exception:
        pass

    db = SessionLocal()
    try:
        if needs_processo_atribuicoes_sync(db):
            sync_processo_atribuicoes(db)
    except Exception:
        pass
    finally:
        db.close()

    if not DISABLE_STARTUP_PRECOMPUTE:
        precompute_analytics()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_default_user()
    threading.Thread(target=run_noncritical_startup_tasks, daemon=True).start()
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
    # sorted: chave de cache estável independente da ordem de inserção no banco
    return tuple(sorted(row[0].upper() for row in rows))


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
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Resumo de frescor e completude dos snapshots importados.

    A checagem usa somente a tabela de uploads para ser rápida e barata:
    identifica a data global mais recente, o último snapshot por setor e
    possíveis setores ausentes/defasados antes de o gestor interpretar os painéis.

    Para usuários com restrição de setor, exibe apenas os setores permitidos.
    """
    # Filtra os setores a checar conforme a permissão do usuário
    setores_permitidos = get_user_setores(current_user, db)
    setores_a_checar = (
        [s for s in SETORES if s in setores_permitidos]
        if setores_permitidos is not None
        else SETORES
    )
    reference_date = (
        db.query(func.max(Upload.data_relatorio))
        .filter(Upload.setor.in_(setores_a_checar))
        .scalar()
        if setores_a_checar
        else None
    )
    today = datetime.now(LOCAL_TIMEZONE).date()

    sectors: list[dict] = []
    missing_sectors: list[str] = []
    lagging_sectors: list[str] = []
    current_sectors: list[str] = []
    quality_alerts: list[dict] = []

    for setor in setores_a_checar:
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
            "setores_esperados": setores_a_checar,
            "setores_em_dia": current_sectors,
            "setores_defasados": lagging_sectors,
            "setores_ausentes": missing_sectors,
            "total_setores_esperados": len(setores_a_checar),
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


@app.get("/api/admin/users", response_model=list[AdminUserRead])
def list_users(
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    users = db.query(User).order_by(User.name.asc()).all()
    sector_rows = db.query(UserSectorAccess.user_id, UserSectorAccess.setor).all()
    sectors_by_user: dict[int, list[str]] = {}
    for user_id, setor in sector_rows:
        sectors_by_user.setdefault(user_id, []).append(setor)

    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "is_admin": user.is_admin,
            "can_upload": user.can_upload,
            "created_at": user.created_at,
            "setores": sorted(sectors_by_user.get(user.id, [])),
        }
        for user in users
    ]


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
    return (
        db.query(SeiUser)
        .options(selectinload(SeiUser.aliases), selectinload(SeiUser.setor_links))
        .order_by(SeiUser.nome.asc())
        .all()
    )


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


# ── Setores por usuário SEI ───────────────────────────────────────────────

class SeiUserSetoresUpdate(BaseModel):
    setores: list[str]


@app.get("/api/admin/sei-users/{sei_user_id}/sectors")
def get_sei_user_sectors(
    sei_user_id: int,
    _: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Lista os setores onde um usuário SEI atua (vínculos explícitos)."""
    sei_user = db.query(SeiUser).filter(SeiUser.id == sei_user_id).first()
    if not sei_user:
        raise HTTPException(status_code=404, detail="Usuário SEI não encontrado.")
    rows = db.query(SeiUserSetor.setor).filter(SeiUserSetor.sei_user_id == sei_user_id).all()
    return {"sei_user_id": sei_user_id, "nome": sei_user.nome, "setores": sorted(r[0] for r in rows)}


@app.put("/api/admin/sei-users/{sei_user_id}/sectors")
def update_sei_user_sectors(
    sei_user_id: int,
    payload: SeiUserSetoresUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Redefine os setores de um usuário SEI (substituição completa)."""
    sei_user = db.query(SeiUser).filter(SeiUser.id == sei_user_id).first()
    if not sei_user:
        raise HTTPException(status_code=404, detail="Usuário SEI não encontrado.")

    old_rows = db.query(SeiUserSetor.setor).filter(SeiUserSetor.sei_user_id == sei_user_id).all()
    old_setores = sorted(r[0] for r in old_rows)
    new_setores = sorted({s.upper().strip() for s in payload.setores if s.strip()})
    invalid_setores = [setor for setor in new_setores if setor not in SETORES]
    if invalid_setores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Setor(es) inválido(s): {', '.join(invalid_setores)}.",
        )

    db.query(SeiUserSetor).filter(SeiUserSetor.sei_user_id == sei_user_id).delete()
    for setor in new_setores:
        db.add(SeiUserSetor(sei_user_id=sei_user_id, setor=setor))

    _log_audit(
        db,
        action="sei_usuario.setores_atualizados",
        entity_type="sei_usuario",
        entity_id=str(sei_user_id),
        details={"nome": sei_user.nome, "setores_anteriores": old_setores, "setores_novos": new_setores},
        user=current_admin,
    )
    db.commit()
    clear_analytics_cache()
    return {"ok": True, "sei_user_id": sei_user_id, "setores": new_setores}


@app.post("/api/admin/sei-users/infer-sectors")
def infer_sei_user_sectors(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Infere e cadastra setores para usuários SEI a partir dos processos históricos.

    Para cada SEI user, vincula TODOS os setores onde aparece como
    atribuicao_normalizada nos processos. Nunca remove vínculos explícitos
    existentes — apenas adiciona os faltantes.
    """
    sei_users = db.query(SeiUser).all()
    updated = 0
    total_links_added = 0

    for sei_user in sei_users:
        # Setores onde este SEI user aparece nos processos
        found_setores: set[str] = {
            row[0]
            for row in db.query(Processo.setor)
            .filter(Processo.atribuicao_normalizada == sei_user.nome)
            .distinct()
            .all()
            if row[0]
        }
        if not found_setores:
            continue

        existing: set[str] = {
            row[0]
            for row in db.query(SeiUserSetor.setor)
            .filter(SeiUserSetor.sei_user_id == sei_user.id)
            .all()
        }
        new_links = found_setores - existing
        for setor in new_links:
            db.add(SeiUserSetor(sei_user_id=sei_user.id, setor=setor))
        if new_links:
            updated += 1
            total_links_added += len(new_links)

    _log_audit(
        db,
        action="sei_usuario.setores_inferidos",
        entity_type="sei_usuario",
        details={"sei_users_atualizados": updated, "vinculos_adicionados": total_links_added},
        user=current_admin,
    )
    db.commit()
    clear_analytics_cache()
    return {"ok": True, "sei_users_atualizados": updated, "vinculos_adicionados": total_links_added}


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




# ─────────────────────────────────────────────────────────────────────────────
# PAUTA PRIORITÁRIA — detecção automática pós-upload e endpoints
# ─────────────────────────────────────────────────────────────────────────────

def _check_pauta_resolution(db: Session, setor: str, data_relatorio: "date", total_records: int) -> None:
    """Após um upload válido, verifica se itens de pauta ativos saíram do setor.

    Regras conservadoras (não resolve com snapshot ruim):
      - total_records > 0 (snapshot não está vazio)
      - data_relatorio é a referência mais recente com registros válidos para o setor
      - item estava pendente ou em_acompanhamento
      - protocolo não aparece mais no snapshot atual do setor
    """
    if total_records <= 0:
        return

    # Confirma que este é o snapshot mais recente válido do setor
    latest_valid = (
        db.query(func.max(Upload.data_relatorio))
        .filter(Upload.setor == setor, Upload.total_records > 0)
        .scalar()
    )
    if latest_valid != data_relatorio:
        return

    current_protos: set[str] = {
        row[0]
        for row in db.query(Processo.protocolo)
        .filter(Processo.setor == setor, Processo.data_relatorio == data_relatorio)
        .all()
        if row[0]
    }

    items = (
        db.query(PautaItem)
        .filter(PautaItem.setor == setor, PautaItem.status.in_(["pendente", "em_acompanhamento"]))
        .all()
    )

    for item in items:
        if item.protocolo not in current_protos:
            item.status = "saiu_do_setor"
            item.data_status = data_relatorio
            item.resolucao_automatica = True
            item.updated_at = datetime.now(timezone.utc)
    # commit é feito pelo chamador (após o upload)


# ── Schemas Pydantic para Pauta ───────────────────────────────────────────

class PautaSessaoCreate(BaseModel):
    titulo: str = Field(min_length=3, max_length=255)
    data_inicio: date
    data_fim: date | None = None
    data_reuniao: date | None = None
    observacoes: str | None = None


class PautaSessaoUpdate(BaseModel):
    titulo: str | None = Field(default=None, min_length=3, max_length=255)
    data_inicio: date | None = None
    data_fim: date | None = None
    data_reuniao: date | None = None
    observacoes: str | None = None
    ativa: bool | None = None


class PautaItemCreate(BaseModel):
    protocolo: str
    setor: str
    entrada_setor: date | None = None
    data_referencia: date | None = None
    ultima_presenca: date | None = None
    atribuicao: str | None = None
    tipo: str | None = None
    dias_no_setor: int | None = None
    score_risco: float | None = None
    nivel_risco: str | None = None
    assigned_to: int | None = None
    nota_admin: str | None = None


class PautaItemBulkCreate(BaseModel):
    sessao_id: int
    assigned_to: int | None = None
    nota_admin: str | None = None
    itens: list[PautaItemCreate]


class PautaItemUpdate(BaseModel):
    status: str | None = None  # em_acompanhamento | resolvido_manual | arquivado
    nota_admin: str | None = None
    nota_responsavel: str | None = None
    assigned_to: int | None = None


# ── Helpers ───────────────────────────────────────────────────────────────

def _pauta_item_to_dict(item: PautaItem, users_map: dict) -> dict:
    return {
        "id": item.id,
        "sessao_id": item.sessao_id,
        "protocolo": item.protocolo,
        "setor": item.setor,
        "entrada_setor": str(item.entrada_setor) if item.entrada_setor else None,
        "data_referencia": str(item.data_referencia) if item.data_referencia else None,
        "ultima_presenca": str(item.ultima_presenca) if item.ultima_presenca else None,
        "atribuicao": item.atribuicao,
        "tipo": item.tipo,
        "dias_no_setor": item.dias_no_setor,
        "score_risco": float(item.score_risco) if item.score_risco is not None else None,
        "nivel_risco": item.nivel_risco,
        "assigned_to": item.assigned_to,
        "assigned_to_nome": users_map.get(item.assigned_to, {}).get("name") if item.assigned_to else None,
        "assigned_by": item.assigned_by,
        "status": item.status,
        "nota_admin": item.nota_admin,
        "nota_responsavel": item.nota_responsavel,
        "data_status": str(item.data_status) if item.data_status else None,
        "resolucao_automatica": item.resolucao_automatica,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _pauta_item_exists(
    db: Session,
    sessao_id: int,
    protocolo: str,
    setor: str,
    entrada_setor: date | None,
) -> bool:
    query = db.query(PautaItem.id).filter(
        PautaItem.sessao_id == sessao_id,
        PautaItem.protocolo == protocolo,
        PautaItem.setor == setor,
    )
    if entrada_setor is None:
        query = query.filter(PautaItem.entrada_setor.is_(None))
    else:
        query = query.filter(PautaItem.entrada_setor == entrada_setor)
    return query.first() is not None


_SITUACAO_LABELS = {
    "a_iniciar":    "A iniciar",
    "em_andamento": "Em andamento",
    "encerrada":    "Encerrada",
}


def _atribuicao_atual_por_processo(db: Session, itens: list[PautaItem]) -> dict[tuple[str, str], str | None]:
    """Atribuição atual no SEI (último snapshot) para cada (protocolo, setor) da pauta.

    Retorna {(protocolo, setor): atribuicao} para processos que AINDA constam no
    último snapshot daquele setor — a chave existir no dict significa "processo
    presente no setor" (mesmo que o valor seja None por não ter normalização).
    Processos ausentes do snapshot não entram no dict; o chamador usa
    item.atribuicao (valor da inclusão) como fallback histórico.

    Prefere atribuicao_normalizada; se nula, usa o texto bruto atribuicao.
    Consulta única em lote (sem N+1).
    """
    if not itens:
        return {}

    pares = {(i.protocolo, i.setor) for i in itens}
    protocolos = {p for p, _ in pares}
    setores = {s for _, s in pares}

    # Data de referência (último snapshot) por setor envolvido
    ref_por_setor = dict(
        db.query(Processo.setor, func.max(Processo.data_relatorio))
        .filter(Processo.setor.in_(setores))
        .group_by(Processo.setor)
        .all()
    )
    if not ref_por_setor:
        return {}

    rows = (
        db.query(
            Processo.protocolo, Processo.setor,
            Processo.atribuicao_normalizada, Processo.atribuicao, Processo.data_relatorio,
        )
        .filter(Processo.protocolo.in_(protocolos), Processo.setor.in_(setores))
        .all()
    )
    resultado: dict[tuple[str, str], str | None] = {}
    for protocolo, setor, atrib_norm, atrib_raw, data_rel in rows:
        if (protocolo, setor) in pares and data_rel == ref_por_setor.get(setor):
            # Chave presente = processo ainda no setor; valor pode ser None
            resultado[(protocolo, setor)] = atrib_norm or atrib_raw
    return resultado


def _situacao_pauta_sessao(s: PautaSessao) -> str:
    """Situação DERIVADA da sessão (nunca gravada no banco).

    a_iniciar    → ativa=True e data_inicio > hoje
    em_andamento → ativa=True e data_inicio <= hoje e (sem prazo OU data_fim >= hoje)
    encerrada    → ativa=False OU data_fim < hoje

    Regra de borda: data_fim == hoje ainda é EM ANDAMENTO (encerra só no dia seguinte).
    Cálculo em America/Fortaleza para não virar o dia por UTC.
    """
    hoje = datetime.now(LOCAL_TIMEZONE).date()
    if not s.ativa:
        return "encerrada"
    if s.data_fim is not None and s.data_fim < hoje:
        return "encerrada"
    if s.data_inicio is not None and s.data_inicio > hoje:
        return "a_iniciar"
    return "em_andamento"


def _pauta_item_em_sessao_ativa(
    db: Session,
    protocolo: str,
    setor: str,
    entrada_setor: date | None,
) -> PautaItem | None:
    """Retorna o item existente (se houver) do mesmo processo em QUALQUER sessão
    a_iniciar ou em_andamento — usado para impedir duplicidade global.

    Ignora itens arquivados e sessões encerradas. A situação é derivada em Python
    (depende de datas + ativa), então filtramos ativa=True no SQL e reavaliamos
    a situação de cada candidato.
    """
    query = (
        db.query(PautaItem)
        .join(PautaSessao, PautaItem.sessao_id == PautaSessao.id)
        .filter(
            PautaItem.protocolo == protocolo,
            PautaItem.setor == setor,
            PautaItem.status != "arquivado",
            PautaSessao.ativa == True,
        )
    )
    if entrada_setor is None:
        query = query.filter(PautaItem.entrada_setor.is_(None))
    else:
        query = query.filter(PautaItem.entrada_setor == entrada_setor)

    for item in query.all():
        if _situacao_pauta_sessao(item.sessao) in ("a_iniciar", "em_andamento"):
            return item
    return None


def _ensure_assignee_can_access_setor(db: Session, assigned_to: int | None, setor: str) -> None:
    if assigned_to is None:
        return
    target = db.query(User).filter(User.id == assigned_to).first()
    if not target:
        raise HTTPException(status_code=400, detail="Responsável informado não encontrado.")
    if target.is_admin:
        return
    has_access = (
        db.query(UserSectorAccess.id)
        .filter(UserSectorAccess.user_id == assigned_to, UserSectorAccess.setor == setor)
        .first()
    )
    if not has_access:
        raise HTTPException(
            status_code=400,
            detail=f"Responsável não tem acesso ao setor {setor}.",
        )


def _pauta_item_visible_to(item: PautaItem, user: User, setores: tuple[str, ...] | None) -> bool:
    """Escopo cumulativo da pauta para não-admin:
    o item deve estar atribuído ao usuário E o setor do item deve pertencer
    ao escopo setorial ATUAL do usuário. Se o admin removeu o acesso a um
    setor depois da atribuição, os itens daquele setor deixam de ser visíveis.
    """
    if user.is_admin:
        return True
    if item.assigned_to != user.id:
        return False
    if setores is None:
        return True
    return item.setor in setores


# ── Endpoints de Sessões ──────────────────────────────────────────────────

@app.get("/api/pauta/sessoes")
def list_pauta_sessoes(
    ativa: bool | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista sessões de pauta. Admin vê todas; usuário comum vê apenas as que
    têm itens atribuídos a ele em setores do seu escopo atual."""
    query = db.query(PautaSessao).order_by(PautaSessao.data_inicio.desc())
    if ativa is not None:
        query = query.filter(PautaSessao.ativa == ativa)
    sessoes = query.all()

    setores_atuais = get_user_setores(current_user, db)

    users_map = {
        u.id: {"name": u.name, "email": u.email}
        for u in db.query(User).all()
    }

    result = []
    for s in sessoes:
        contagens = {st: 0 for st in ["pendente", "em_acompanhamento", "saiu_do_setor", "resolvido_manual", "arquivado"]}
        for item in s.itens:
            if not _pauta_item_visible_to(item, current_user, setores_atuais):
                continue
            contagens[item.status] = contagens.get(item.status, 0) + 1

        # Não admin: sessão só aparece se tiver ao menos um item visível
        if not current_user.is_admin and sum(contagens.values()) == 0:
            continue

        situacao = _situacao_pauta_sessao(s)
        result.append({
            "id": s.id,
            "titulo": s.titulo,
            "data_inicio": str(s.data_inicio),
            "data_fim": str(s.data_fim) if s.data_fim else None,
            "data_reuniao": str(s.data_reuniao) if s.data_reuniao else None,
            "observacoes": s.observacoes,
            "ativa": s.ativa,
            "situacao": situacao,
            "situacao_label": _SITUACAO_LABELS[situacao],
            "criado_por": s.criado_por,
            "criado_por_nome": users_map.get(s.criado_por, {}).get("name") if s.criado_por else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "contagens": contagens,
            "total": sum(contagens.values()),
        })
    return result


@app.post("/api/pauta/sessoes", status_code=201)
def create_pauta_sessao(
    payload: PautaSessaoCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    s = PautaSessao(
        titulo=payload.titulo,
        data_inicio=payload.data_inicio,
        data_fim=payload.data_fim,
        data_reuniao=payload.data_reuniao,
        observacoes=payload.observacoes,
        criado_por=current_admin.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    _log_audit(db, action="pauta.sessao_criada", entity_type="pauta_sessao",
               entity_id=str(s.id), details={"titulo": s.titulo}, user=current_admin)
    db.commit()
    return {"id": s.id, "titulo": s.titulo, "data_inicio": str(s.data_inicio)}


@app.get("/api/pauta/sessoes/{sessao_id}")
def get_pauta_sessao(
    sessao_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = db.query(PautaSessao).filter(PautaSessao.id == sessao_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    setores_atuais = get_user_setores(current_user, db)
    users_map = {u.id: {"name": u.name, "email": u.email} for u in db.query(User).all()}

    # Atribuição ATUAL no SEI (último snapshot de cada protocolo+setor da sessão).
    # Consulta em lote para evitar N+1; fallback para item.atribuicao (snapshot da
    # inclusão) quando o processo já não consta mais no setor.
    atribuicao_atual = _atribuicao_atual_por_processo(db, s.itens)

    itens = []
    for item in sorted(s.itens, key=lambda x: (-(x.score_risco or 0), -(x.dias_no_setor or 0))):
        if not _pauta_item_visible_to(item, current_user, setores_atuais):
            continue
        d = _pauta_item_to_dict(item, users_map)
        # Presença no dict = processo ainda no setor (valor pode ser None sem normalização)
        presente = (item.protocolo, item.setor) in atribuicao_atual
        atual = atribuicao_atual.get((item.protocolo, item.setor)) if presente else None
        d["atribuicao_atual"] = atual
        d["atribuicao_display"] = atual if presente else item.atribuicao
        d["atribuicao_historica"] = not presente  # True → tooltip de valor histórico
        itens.append(d)

    # Não-admin sem itens visíveis: 404 — não confirma sequer que a sessão
    # existe, e não vaza título/observações de pautas alheias
    if not current_user.is_admin and not itens:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    contagens = {st: 0 for st in ["pendente", "em_acompanhamento", "saiu_do_setor", "resolvido_manual", "arquivado"]}
    for item in itens:
        contagens[item["status"]] = contagens.get(item["status"], 0) + 1

    situacao = _situacao_pauta_sessao(s)
    return {
        "id": s.id, "titulo": s.titulo, "data_inicio": str(s.data_inicio),
        "data_fim": str(s.data_fim) if s.data_fim else None,
        "data_reuniao": str(s.data_reuniao) if s.data_reuniao else None,
        "observacoes": s.observacoes, "ativa": s.ativa,
        "situacao": situacao, "situacao_label": _SITUACAO_LABELS[situacao],
        "criado_por_nome": users_map.get(s.criado_por, {}).get("name") if s.criado_por else None,
        "contagens": contagens, "itens": itens,
    }


@app.patch("/api/pauta/sessoes/{sessao_id}")
def update_pauta_sessao(
    sessao_id: int,
    payload: PautaSessaoUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    s = db.query(PautaSessao).filter(PautaSessao.id == sessao_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    was_active = s.ativa
    # exclude_unset (não exclude_none): permite ao admin LIMPAR uma data
    # opcional enviando null explicitamente; campos não enviados ficam intactos
    data = payload.model_dump(exclude_unset=True)

    if "titulo" in data and data["titulo"] is None:
        raise HTTPException(status_code=400, detail="Título é obrigatório.")
    if "data_inicio" in data and data["data_inicio"] is None:
        raise HTTPException(status_code=400, detail="Data de início é obrigatória.")

    # Valida coerência com os valores FINAIS (mesclando atuais + enviados)
    final_inicio = data.get("data_inicio", s.data_inicio)
    final_fim = data.get("data_fim", s.data_fim)
    if final_inicio and final_fim and final_inicio > final_fim:
        raise HTTPException(
            status_code=400,
            detail="O prazo da pauta não pode ser anterior à data de início.",
        )

    # Auditoria de edição: registra apenas os campos que mudaram, com antes/depois
    tracked = ("titulo", "data_inicio", "data_fim", "data_reuniao", "observacoes")
    changes = {
        field: {"de": str(getattr(s, field)) if getattr(s, field) is not None else None,
                "para": str(data[field]) if data[field] is not None else None}
        for field in tracked
        if field in data and data[field] != getattr(s, field)
    }

    for field, value in data.items():
        setattr(s, field, value)
    s.updated_at = datetime.now(timezone.utc)

    if changes:
        _log_audit(
            db,
            action="pauta.sessao_editada",
            entity_type="pauta_sessao",
            entity_id=str(sessao_id),
            details={"titulo": s.titulo, "alteracoes": changes},
            user=current_admin,
        )

    # Auditoria de encerramento — registra contagens finais da sessão
    if was_active and s.ativa is False:
        contagens: dict[str, int] = {}
        for item in s.itens:
            contagens[item.status] = contagens.get(item.status, 0) + 1
        _log_audit(
            db,
            action="pauta.sessao_encerrada",
            entity_type="pauta_sessao",
            entity_id=str(sessao_id),
            details={
                "titulo": s.titulo,
                "data_inicio": str(s.data_inicio),
                "contagens": contagens,
                "total": sum(contagens.values()),
            },
            user=current_admin,
        )

    db.commit()
    return {"ok": True}


# ── Endpoints de Itens ────────────────────────────────────────────────────

@app.get("/api/pauta/itens-ativos")
def list_pauta_itens_ativos(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Processos que já estão em alguma pauta a_iniciar ou em_andamento.

    Alimenta o botão verde "Na pauta" nas páginas Atribuições e Risco,
    persistindo o estado através de reload. Retorna dados estruturados
    para permitir tooltip com o nome da sessão.
    """
    rows = (
        db.query(PautaItem, PautaSessao)
        .join(PautaSessao, PautaItem.sessao_id == PautaSessao.id)
        .filter(PautaItem.status != "arquivado", PautaSessao.ativa == True)
        .all()
    )
    items = []
    for item, sessao in rows:
        if _situacao_pauta_sessao(sessao) in ("a_iniciar", "em_andamento"):
            ent = str(item.entrada_setor) if item.entrada_setor else ""
            items.append({
                "key": f"{item.protocolo}|{item.setor}|{ent}",
                "protocolo": item.protocolo,
                "setor": item.setor,
                "entrada_setor": str(item.entrada_setor) if item.entrada_setor else None,
                "sessao_id": sessao.id,
                "sessao_titulo": sessao.titulo,
            })
    return {"items": items}


@app.post("/api/pauta/sessoes/{sessao_id}/itens", status_code=201)
def add_pauta_item(
    sessao_id: int,
    payload: PautaItemCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    s = db.query(PautaSessao).filter(PautaSessao.id == sessao_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    if _situacao_pauta_sessao(s) == "encerrada":
        raise HTTPException(status_code=409, detail="Não é possível adicionar processos a uma pauta encerrada.")

    _ensure_assignee_can_access_setor(db, payload.assigned_to, payload.setor)

    # Duplicidade global: o mesmo processo não pode estar em duas pautas ativas
    existente = _pauta_item_em_sessao_ativa(db, payload.protocolo, payload.setor, payload.entrada_setor)
    if existente is not None:
        raise HTTPException(
            status_code=409,
            detail=f'Processo já está na pauta "{existente.sessao.titulo}".',
        )

    item = PautaItem(
        sessao_id=sessao_id,
        assigned_by=current_admin.id,
        **payload.model_dump(exclude_none=True),
    )
    db.add(item)
    db.commit()
    return {"id": item.id}


@app.post("/api/pauta/sessoes/{sessao_id}/itens/bulk", status_code=201)
def add_pauta_items_bulk(
    sessao_id: int,
    payload: PautaItemBulkCreate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Adiciona múltiplos processos de uma vez.

    Bloqueia sessão encerrada (409). Valida acesso do responsável a TODOS os
    setores selecionados. Ignora silenciosamente processos que já estejam em
    qualquer pauta ativa (duplicidade global), reportando quantos foram pulados.
    """
    s = db.query(PautaSessao).filter(PautaSessao.id == sessao_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    if _situacao_pauta_sessao(s) == "encerrada":
        raise HTTPException(status_code=409, detail="Não é possível adicionar processos a uma pauta encerrada.")

    # Valida acesso do responsável a todos os setores distintos do lote de uma vez
    if payload.assigned_to is not None:
        for setor in {i.setor for i in payload.itens}:
            _ensure_assignee_can_access_setor(db, payload.assigned_to, setor)

    added = 0
    skipped = 0
    for item_data in payload.itens:
        if _pauta_item_em_sessao_ativa(db, item_data.protocolo, item_data.setor, item_data.entrada_setor):
            skipped += 1
            continue
        data = item_data.model_dump(exclude_none=True, exclude={"assigned_to", "nota_admin"})
        item = PautaItem(
            sessao_id=sessao_id,
            assigned_to=payload.assigned_to,
            assigned_by=current_admin.id,
            nota_admin=payload.nota_admin,
            **data,
        )
        db.add(item)
        added += 1
    db.commit()
    return {"added": added, "skipped": skipped, "total_requested": len(payload.itens)}


@app.patch("/api/pauta/itens/{item_id}")
def update_pauta_item(
    item_id: int,
    payload: PautaItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza um item de pauta.

    Regras de permissão:
      Admin:
        - Pode alterar qualquer campo, incluindo nota_admin, assigned_to e resolvido_manual.
      Responsável (não-admin):
        - Só pode alterar nota_responsavel.
        - Só pode mudar status para em_acompanhamento, e apenas se o status atual for pendente.
        - Não pode alterar nota_admin, assigned_to, nem declarar resolução.
        - A resolução é exclusivamente automática (detectada via snapshot).
    """
    item = db.query(PautaItem).filter(PautaItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")

    if not current_user.is_admin:
        if item.assigned_to != current_user.id:
            raise HTTPException(status_code=403, detail="Sem permissão para editar este item.")

        # Campos restritos para o responsável
        if payload.assigned_to is not None:
            raise HTTPException(status_code=403, detail="Apenas admins podem reatribuir itens.")
        if payload.nota_admin is not None:
            raise HTTPException(status_code=403, detail="Apenas admins podem editar a nota da gestão.")

        # Status: responsável só pode confirmar ciência (pendente → em_acompanhamento)
        if payload.status is not None:
            if payload.status != "em_acompanhamento":
                raise HTTPException(
                    status_code=403,
                    detail="Responsável não pode declarar resolução. A resolução é automática via snapshot.",
                )
            if item.status != "pendente":
                raise HTTPException(
                    status_code=409,
                    detail=f"Não é possível confirmar ciência: status atual é '{item.status}'.",
                )

    data = payload.model_dump(exclude_none=True)
    if "assigned_to" in data:
        _ensure_assignee_can_access_setor(db, data["assigned_to"], item.setor)

    # Auditoria da nota da gestão (orientação formal): registra antes/depois
    if "nota_admin" in data and data["nota_admin"] != item.nota_admin:
        _log_audit(
            db,
            action="pauta.item_nota_gestao_editada",
            entity_type="pauta_item",
            entity_id=str(item.id),
            details={
                "protocolo": item.protocolo,
                "sessao_id": item.sessao_id,
                "de": item.nota_admin,
                "para": data["nota_admin"],
            },
            user=current_user,
        )

    if "status" in data:
        item.data_status = datetime.now(LOCAL_TIMEZONE).date()
        item.resolucao_automatica = False
    for field, value in data.items():
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@app.delete("/api/pauta/itens/{item_id}")
def delete_pauta_item(
    item_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    item = db.query(PautaItem).filter(PautaItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    db.delete(item)
    db.commit()
    return {"ok": True}


@app.get("/api/pauta/minha")
def get_minha_pauta(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna todos os itens atribuídos ao usuário atual, de sessões ativas, ordenados por risco."""
    users_map = {u.id: {"name": u.name, "email": u.email} for u in db.query(User).all()}
    items = (
        db.query(PautaItem)
        .join(PautaSessao, PautaItem.sessao_id == PautaSessao.id)
        .filter(
            PautaItem.assigned_to == current_user.id,
            PautaSessao.ativa == True,
            PautaItem.status.notin_(["arquivado"]),
        )
        .all()
    )

    # Escopo cumulativo: além de atribuído, o setor precisa estar no escopo atual.
    # Ignora sessões encerradas por prazo (ativa=True mas data_fim vencida).
    setores_atuais = get_user_setores(current_user, db)
    items = [
        i for i in items
        if _pauta_item_visible_to(i, current_user, setores_atuais)
        and _situacao_pauta_sessao(i.sessao) != "encerrada"
    ]

    return {
        "user": {"id": current_user.id, "name": current_user.name},
        "itens": sorted(
            [_pauta_item_to_dict(i, users_map) for i in items],
            key=lambda x: (-(x["score_risco"] or 0), -(x["dias_no_setor"] or 0)),
        ),
    }


class CopyPendingPayload(BaseModel):
    titulo: str = Field(min_length=3, max_length=255)
    data_inicio: date
    data_fim: date | None = None
    data_reuniao: date | None = None


@app.post("/api/pauta/sessoes/{sessao_id}/copy-pending", status_code=201)
def copy_pending_to_new_session(
    sessao_id: int,
    payload: CopyPendingPayload,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Encerra a sessão de origem E copia seus itens pendentes para uma nova sessão,
    tudo na mesma transação (atômico).

    A regra de não-duplicidade impede o mesmo processo em duas pautas ativas — por
    isso a origem é obrigatoriamente encerrada aqui. Encerrar a origem ANTES de
    copiar faz seus itens deixarem de contar como "pauta ativa", permitindo a cópia.
    """
    source = db.query(PautaSessao).filter(PautaSessao.id == sessao_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Sessão de origem não encontrada.")

    pending = [i for i in source.itens if i.status in ("pendente", "em_acompanhamento")]
    if not pending:
        raise HTTPException(status_code=400, detail="Nenhum item pendente nesta sessão.")

    # 1) Encerra a origem primeiro (na mesma transação) — seus itens deixam de
    #    contar como ativos, liberando a duplicidade global para a cópia
    source.ativa = False
    source.updated_at = datetime.now(timezone.utc)
    db.flush()

    new_session = PautaSessao(
        titulo=payload.titulo,
        data_inicio=payload.data_inicio,
        data_fim=payload.data_fim,
        data_reuniao=payload.data_reuniao,
        criado_por=current_admin.id,
    )
    db.add(new_session)
    db.flush()

    copiados = 0
    ignorados = 0
    for item in pending:
        # Salvaguarda: pula se o processo já estiver em outra pauta ativa
        if _pauta_item_em_sessao_ativa(db, item.protocolo, item.setor, item.entrada_setor):
            ignorados += 1
            continue
        db.add(PautaItem(
            sessao_id=new_session.id,
            protocolo=item.protocolo,
            setor=item.setor,
            entrada_setor=item.entrada_setor,
            data_referencia=item.data_referencia,
            ultima_presenca=item.ultima_presenca,
            atribuicao=item.atribuicao,
            tipo=item.tipo,
            dias_no_setor=item.dias_no_setor,
            score_risco=item.score_risco,
            nivel_risco=item.nivel_risco,
            assigned_to=item.assigned_to,
            assigned_by=current_admin.id,
            nota_admin=item.nota_admin,
            status="pendente",
        ))
        copiados += 1

    _log_audit(
        db,
        action="pauta.pendencias_copiadas",
        entity_type="pauta_sessao",
        entity_id=str(sessao_id),
        details={
            "origem": source.titulo, "origem_encerrada": True,
            "nova_sessao": payload.titulo, "itens_copiados": copiados, "ignorados": ignorados,
        },
        user=current_admin,
    )
    db.commit()
    return {
        "nova_sessao_id": new_session.id, "titulo": payload.titulo,
        "itens_copiados": copiados, "ignorados": ignorados, "origem_encerrada": True,
    }


@app.get("/api/pauta/metricas")
def get_pauta_metricas(
    ultimas_n: int = Query(8, ge=1, le=52),
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Indicadores de eficiência da pauta — admin only.

    Métricas por sessão (sem mistura global ambígua):
      - Percentual de resolução automática por sessão
      - Overrides manuais separados
      - Tempo médio até saída do setor (somente saiu_do_setor)
      - Pendências arrastadas (itens ativos em sessões encerradas)
    """
    from datetime import timedelta

    sessoes = (
        db.query(PautaSessao)
        .order_by(PautaSessao.data_inicio.desc())
        .limit(ultimas_n)
        .all()
    )

    # Pendências arrastadas: itens ativos em sessões encerradas
    pendencias_arrastadas = (
        db.query(PautaItem)
        .join(PautaSessao, PautaItem.sessao_id == PautaSessao.id)
        .filter(PautaSessao.ativa == False, PautaItem.status.in_(["pendente", "em_acompanhamento"]))
        .count()
    )

    # Tempo médio até resolução automática (created_at → data_status)
    itens_auto = (
        db.query(PautaItem)
        .join(PautaSessao, PautaItem.sessao_id == PautaSessao.id)
        .filter(PautaItem.status == "saiu_do_setor", PautaItem.data_status.is_not(None))
        .all()
    )
    duracoes = []
    for i in itens_auto:
        if i.data_status and i.created_at:
            delta = i.data_status - i.created_at.date()
            if 0 <= delta.days <= 365:  # sanidade
                duracoes.append(delta.days)
    tempo_medio_dias = round(sum(duracoes) / len(duracoes), 1) if duracoes else None

    # Métricas por sessão
    sessoes_data = []
    for s in reversed(sessoes):  # cronológico
        ct: dict[str, int] = {}
        for item in s.itens:
            ct[item.status] = ct.get(item.status, 0) + 1

        total = sum(ct.values())
        resolvidos_auto   = ct.get("saiu_do_setor", 0)
        resolvidos_manual = ct.get("resolvido_manual", 0)
        ativos = ct.get("pendente", 0) + ct.get("em_acompanhamento", 0)

        sessoes_data.append({
            "id":              s.id,
            "titulo":          s.titulo,
            "data_inicio":     str(s.data_inicio),
            "data_fim":        str(s.data_fim) if s.data_fim else None,
            "ativa":           s.ativa,
            "total":           total,
            "ativos":          ativos,
            "resolvidos_auto": resolvidos_auto,
            "resolvidos_manual": resolvidos_manual,
            "arquivados":      ct.get("arquivado", 0),
            "taxa_auto_pct":   round(resolvidos_auto / total * 100) if total else 0,
            "taxa_total_pct":  round((resolvidos_auto + resolvidos_manual) / total * 100) if total else 0,
        })

    return JSONResponse({
        "sessoes":              sessoes_data,
        "tempo_medio_auto_dias": tempo_medio_dias,
        "overrides_manuais_total": sum(s["resolvidos_manual"] for s in sessoes_data),
        "pendencias_arrastadas": pendencias_arrastadas,
    })


@app.get("/api/monthly-stats")
def list_monthly_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    setores_permitidos = get_user_setores(current_user, db)
    query = db.query(MonthlyStat).order_by(
        MonthlyStat.periodo.asc(), MonthlyStat.setor.asc(), MonthlyStat.indicador.asc()
    )
    if setores_permitidos is not None:
        if len(setores_permitidos) == 0:
            return {"rows": [], "setores": [], "indicadores": list(MONTHLY_INDICATORS), "anos": []}
        query = query.filter(MonthlyStat.setor.in_(setores_permitidos))
    rows = query.all()
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UploadListResponse:
    query = db.query(Upload)
    setores_permitidos = get_user_setores(current_user, db)
    if setores_permitidos is not None:
        if len(setores_permitidos) == 0:
            return UploadListResponse(items=[], page=page, page_size=page_size, total=0, total_pages=1)
        query = query.filter(Upload.setor.in_(setores_permitidos))

    total = query.count()
    total_pages = max((total + page_size - 1) // page_size, 1)
    items = (
        query
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
    if not current_user.is_admin and not current_user.can_upload:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para enviar relatórios. Solicite ao administrador.",
        )
    normalized_setor = setor.upper()
    if normalized_setor not in SETORES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Setor invalido.")
    setores_permitidos = get_user_setores(current_user, db)
    if setores_permitidos is not None and normalized_setor not in setores_permitidos:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem permissão para enviar relatórios do setor {normalized_setor}.",
        )
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
            setor=normalized_setor,
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
        # Verifica se algum item de pauta saiu do setor neste snapshot
        _check_pauta_resolution(
            db,
            setor=normalized_setor,
            data_relatorio=data_relatorio,
            total_records=result.get("total_registros", 0),
        )
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
        _check_pauta_resolution(
            db,
            setor=result["setor"],
            data_relatorio=result["data_relatorio"],
            total_records=result.get("total_registros", 0),
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
    new_setores = sorted({s.upper().strip() for s in payload.setores if s.strip()})

    # Valida contra a lista oficial de setores do sistema
    invalidos = [s for s in new_setores if s not in SETORES]
    if invalidos:
        raise HTTPException(status_code=400, detail=f"Setor(es) inválido(s): {', '.join(invalidos)}.")

    # Remoção de setor com pauta ativa: bloqueia até o admin reatribuir os itens,
    # evitando itens atribuídos a um responsável que não pode mais vê-los
    removidos = set(old_setores) - set(new_setores)
    if removidos:
        conflitos = (
            db.query(PautaItem)
            .join(PautaSessao, PautaItem.sessao_id == PautaSessao.id)
            .filter(
                PautaItem.assigned_to == user_id,
                PautaItem.setor.in_(removidos),
                PautaItem.status.in_(["pendente", "em_acompanhamento"]),
                PautaSessao.ativa == True,
            )
            .count()
        )
        if conflitos:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"O usuário tem {conflitos} item(ns) ativo(s) na Pauta Prioritária "
                    f"nos setores removidos ({', '.join(sorted(removidos))}). "
                    "Reatribua ou resolva esses itens antes de remover o acesso."
                ),
            )

    # Substituição completa
    db.query(UserSectorAccess).filter(UserSectorAccess.user_id == user_id).delete()
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


# ── Permissões adicionais por usuário ─────────────────────────────────────

class UserPermissionsUpdate(BaseModel):
    can_upload: bool


@app.patch("/api/admin/users/{user_id}/permissions")
def update_user_permissions(
    user_id: int,
    payload: UserPermissionsUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db),
):
    """Atualiza permissões adicionais de um usuário não-admin (can_upload, etc.)."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    if target.is_admin:
        raise HTTPException(status_code=400, detail="Administradores têm acesso total — permissões não se aplicam.")

    old_can_upload = target.can_upload
    target.can_upload = payload.can_upload

    _log_audit(
        db,
        action="usuario.permissoes_atualizadas",
        entity_type="usuario",
        entity_id=str(user_id),
        details={"email": target.email, "can_upload_anterior": old_can_upload, "can_upload_novo": payload.can_upload},
        user=current_admin,
    )
    db.commit()
    return {"ok": True, "user_id": user_id, "can_upload": target.can_upload}


@app.get("/api/alerts/summary")
def alerts_summary(
    current_user: User = Depends(get_current_user_or_api_key),
    db: Session = Depends(get_db),
):
    """Resumo rápido de processos críticos para o sino de notificações.
    Usa o cache do stale-processes — resposta muito rápida."""
    setores_atuais = get_user_setores(current_user, db)
    stale = get_stale_processes_data(db, AnalyticsFilters(setores_permitidos=setores_atuais))
    processos = stale.get("processos", [])

    def conta(min_dias: int) -> int:
        return sum(1 for p in processos if p.get("dias_sem_movimentacao", 0) >= min_dias)

    criticos = sorted(
        [p for p in processos if p.get("dias_sem_movimentacao", 0) >= 45],
        key=lambda p: -p.get("dias_sem_movimentacao", 0),
    )[:8]

    # ── Pauta: itens pendentes do usuário (ou de todos para admin) ──────
    # Escopo cumulativo: atribuído ao usuário E setor no escopo atual.
    # "Não encerrada" é filtrável direto no SQL: ativa=True E (sem prazo OU
    # prazo >= hoje) — cobre encerramento manual e por prazo sem pós-filtro Python.
    hoje = datetime.now(LOCAL_TIMEZONE).date()
    pauta_query = (
        db.query(PautaItem)
        .join(PautaSessao, PautaItem.sessao_id == PautaSessao.id)
        .filter(
            PautaSessao.ativa == True,
            or_(PautaSessao.data_fim.is_(None), PautaSessao.data_fim >= hoje),
            PautaItem.status.in_(["pendente", "em_acompanhamento"]),
        )
    )
    if not current_user.is_admin:
        pauta_query = pauta_query.filter(PautaItem.assigned_to == current_user.id)
        if setores_atuais is not None:
            if len(setores_atuais) == 0:
                pauta_query = pauta_query.filter(text("1=0"))
            else:
                pauta_query = pauta_query.filter(PautaItem.setor.in_(setores_atuais))

    pauta_rows = pauta_query.order_by(PautaItem.score_risco.desc().nullslast()).limit(50).all()
    pauta_pendentes = len(pauta_rows)
    pauta_itens = [
        {
            "id": i.id, "protocolo": i.protocolo, "setor": i.setor,
            "nivel_risco": i.nivel_risco, "dias_no_setor": i.dias_no_setor,
            "status": i.status,
        }
        for i in pauta_rows[:5]
    ]

    return JSONResponse({
        "mais_de_30":    conta(30),
        "mais_de_45":    conta(45),
        "mais_de_90":    conta(90),
        "total_badge":   conta(45) + pauta_pendentes,
        "criticos":      criticos,
        "data_referencia": stale.get("data_referencia"),
        "pauta_pendentes": pauta_pendentes,
        "pauta_itens":     pauta_itens,
    })


@app.get("/api/meta/options", response_model=FilterOptions)
def filter_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FilterOptions:
    setores_permitidos = get_user_setores(current_user, db)
    # Opções já derivadas exclusivamente dos setores permitidos (datas, tipos,
    # setores e atribuições) — nenhum metadado de divisões não autorizadas
    opts = get_filter_options(db, setores_permitidos)
    opts["setores_validos"] = SETORES
    if setores_permitidos is not None:
        opts["setor_restrito"] = True
        opts["setores_do_usuario"] = list(setores_permitidos)

        # ── Filtro de atribuições por setor ─────────────────────────────
        # Regra de fallback:
        #   Se existe ao menos 1 vínculo explícito (sei_user_setor) no sistema
        #   → usa apenas vínculos explícitos (comportamento definitivo).
        #   Se não existe nenhum vínculo ainda
        #   → infere pelo histórico de processos (fallback temporário, até o
        #     admin rodar "Inferir setores" em Usuários SEI).
        has_explicit_links = db.query(SeiUserSetor).limit(1).count() > 0

        if has_explicit_links:
            linked_nomes: set[str] = {
                row[0]
                for row in db.query(SeiUser.nome)
                .join(SeiUserSetor, SeiUser.id == SeiUserSetor.sei_user_id)
                .filter(SeiUserSetor.setor.in_(setores_permitidos))
                .all()
                if row[0]
            }
            opts["atribuicoes"] = [a for a in opts["atribuicoes"] if a in linked_nomes]
        else:
            # Fallback data-driven: atribuições que aparecem nos processos desses setores
            data_atribs: set[str] = {
                row[0]
                for row in db.query(Processo.atribuicao_normalizada)
                .filter(
                    Processo.atribuicao_normalizada.is_not(None),
                    Processo.setor.in_(setores_permitidos),
                )
                .distinct()
                .all()
                if row[0]
            }
            opts["atribuicoes"] = [a for a in opts["atribuicoes"] if a in data_atribs]
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
