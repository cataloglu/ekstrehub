import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
import html
import json
import logging
import pathlib
import re
from urllib.parse import quote, urlparse
from time import perf_counter
from typing import Any, Literal
import uvicorn
from uuid import uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.config import get_settings, mask_secret
from app.db.models import AuditLog, EmailIngested, MailAccount, MailIngestionRun, StatementDocument
from app.db.session import get_session_factory
from app.ingestion.gmail_oauth import GmailOAuthError
from app.ingestion.gmail_oauth_flow import build_auth_url, exchange_code_for_tokens
from app.ingestion.bank_identification import coalesce_bank_display, normalize_optional_llm_str
from app.ingestion.service import MailIngestionService
from app.auto_sync import get_auto_sync_status, update_settings as update_auto_sync_settings, run_scheduler
import app.app_settings as app_settings
from app.logging_utils import configure_logging, log_event
from app.system_reset import (
    CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE,
    CLEAR_LEARNED_RULES_CONFIRM_PHRASE,
    RESET_CONFIRM_PHRASE,
    clear_email_ingestion_cache,
    clear_learned_parser_rules,
    reset_ingestion_data,
)
from app.schemas.ingestion import (
    IngestionRunItemResponse,
    IngestionRunListResponse,
    IngestionSyncResponse,
)
from app.schemas.mail_accounts import (
    MailAccountCreateRequest,
    MailAccountListResponse,
    MailAccountResponse,
)

bootstrap_logger = logging.getLogger("ekstrehub.bootstrap")
request_logger = logging.getLogger("ekstrehub.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    log_event(
        bootstrap_logger,
        "startup_config_validated",
        category="system",
        app_env=settings.app_env,
        mail_ingestion_enabled=settings.mail_ingestion_enabled,
        masked_imap_user=mask_secret(settings.imap_user),
    )

    # Start background auto-sync scheduler
    def _svc_factory(account):
        return MailIngestionService(mail_account=account)

    scheduler_task = asyncio.create_task(
        run_scheduler(get_session_factory, _svc_factory)
    )

    yield

    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="EkstreHub API", version="1.0.0-alpha.1", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
    payload = {
        "error": {
            "code": detail.get("code", "HTTP_ERROR"),
            "message": detail.get("message", "Request failed."),
            "details": detail.get("details", {}),
        }
    }
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    started = perf_counter()

    log_event(
        request_logger,
        "http_request_started",
        category="system",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    response = await call_next(request)
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id

    log_event(
        request_logger,
        "http_request_completed",
        category="system",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=elapsed_ms,
    )
    return response


def _is_db_available() -> bool:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            session.execute(select(1))
        return True
    except (OperationalError, SQLAlchemyError):
        return False


@app.get("/api/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": "ekstrehub-api",
        "environment": settings.app_env,
        "mail_ingestion_enabled": settings.mail_ingestion_enabled,
        "masked_imap_user": mask_secret(settings.imap_user),
        "db_available": _is_db_available(),
        "gmail_oauth_configured": bool(
            settings.gmail_oauth_client_id and settings.gmail_oauth_client_secret
        ),
    }


@app.get("/api/cards")
async def list_cards():
    return {"items": []}


def _raise_db_unavailable(exc: Exception, request_id: str | None = None) -> None:
    log_event(
        request_logger,
        "db_unavailable",
        category="db",
        request_id=request_id,
        error_type=type(exc).__name__,
        message=str(exc),
    )
    raise HTTPException(
        status_code=503,
        detail={
            "code": "DB_UNAVAILABLE",
            "message": "Database is unavailable. Please check DB service and retry.",
            "details": {},
        },
    ) from exc


def _to_mail_account_response(account: MailAccount) -> MailAccountResponse:
    return MailAccountResponse(
        id=account.id,
        provider=account.provider,
        auth_mode=account.auth_mode,
        account_label=account.account_label,
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_user=mask_secret(account.imap_user),
        mailbox=account.mailbox,
        unseen_only=account.unseen_only,
        fetch_limit=account.fetch_limit,
        retry_count=account.retry_count,
        retry_backoff_seconds=float(account.retry_backoff_seconds),
        is_active=account.is_active,
        created_at=account.created_at,
    )


@app.get("/api/mail-accounts", response_model=MailAccountListResponse)
async def list_mail_accounts(request: Request) -> MailAccountListResponse:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            rows = session.scalars(select(MailAccount).order_by(desc(MailAccount.created_at))).all()
            return MailAccountListResponse(items=[_to_mail_account_response(row) for row in rows])
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.post("/api/mail-accounts", response_model=MailAccountResponse)
async def create_mail_account(
    payload: MailAccountCreateRequest, request: Request
) -> MailAccountResponse:
    imap_host = payload.imap_host
    imap_port = payload.imap_port
    if payload.provider == "gmail":
        imap_host = "imap.gmail.com"
        imap_port = 993
    elif payload.provider == "outlook":
        imap_host = "outlook.office365.com"
        imap_port = 993

    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            row = MailAccount(
                provider=payload.provider,
                auth_mode=payload.auth_mode,
                account_label=payload.account_label,
                imap_host=imap_host,
                imap_port=imap_port,
                imap_user=payload.imap_user,
                imap_password=payload.imap_password,
                oauth_refresh_token=payload.oauth_refresh_token,
                mailbox=payload.mailbox,
                unseen_only=payload.unseen_only,
                fetch_limit=payload.fetch_limit,
                retry_count=payload.retry_count,
                retry_backoff_seconds=payload.retry_backoff_seconds,
                is_active=payload.is_active,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_mail_account_response(row)
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.patch("/api/mail-accounts/{account_id}")
async def patch_mail_account(account_id: int, request: Request) -> dict:
    """Partial update of mail account settings (mailbox, fetch_limit, unseen_only)."""
    body = await request.json()
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            row = session.get(MailAccount, account_id)
            if not row:
                raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Mail account not found"})
            allowed = {"mailbox", "fetch_limit", "unseen_only", "is_active", "account_label"}
            for key, val in body.items():
                if key in allowed:
                    setattr(row, key, val)
            session.commit()
            session.refresh(row)
            return _to_mail_account_response(row).model_dump()
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.delete("/api/mail-accounts/{account_id}")
async def delete_mail_account(account_id: int, request: Request) -> dict:
    """Remove a mail account. Linked ingestion runs / emails keep history (FK set to NULL)."""
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            row = session.get(MailAccount, account_id)
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "not_found", "message": "Mail account not found"},
                )
            session.delete(row)
            session.commit()
            log_event(
                request_logger,
                "mail_account_deleted",
                category="mail",
                request_id=getattr(request.state, "request_id", None),
                account_id=account_id,
            )
            return {"deleted": True, "id": account_id}
    except HTTPException:
        raise
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


def _imap_error_is_invalid_credentials(reason: str) -> bool:
    r = reason.lower()
    return "authenticationfailed" in r or "invalid credentials" in r or "authentication failed" in r


def _imap_auth_failed_user_message() -> str:
    return (
        "E-posta girişi reddedildi (IMAP). Gmail’de normal hesap şifren çalışmaz — "
        "Google yalnızca «Uygulama şifresi» (16 karakter) kabul eder: "
        "Google Hesabı → Güvenlik → 2 Adımlı doğrulama açık olmalı → Uygulama şifreleri. "
        "EkstreHub’da Mail & Sync → «uygulama şifresi ile elle ekle» ile şifre alanını kullan. "
        "Alternatif: add-on’da Gmail OAuth (Client ID/Secret) tanımlayıp «Gmail’e bağlan»."
    )


@app.post("/api/mail-ingestion/sync")
async def run_mail_ingestion_sync(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    mail_account_id: int | None = None,
) -> IngestionSyncResponse:
    try:
        selected_account = None
        if mail_account_id is not None:
            session_factory = get_session_factory()
            with session_factory() as session:
                selected_account = session.get(MailAccount, mail_account_id)
            if not selected_account or not selected_account.is_active:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "MAIL_ACCOUNT_NOT_FOUND",
                        "message": "Mail account not found or inactive.",
                        "details": {"mail_account_id": mail_account_id},
                    },
                )
        summary, idempotent = MailIngestionService(mail_account=selected_account).run_sync(
            idempotency_key=idempotency_key
        )
    except GmailOAuthError as exc:
        log_event(
            request_logger,
            "gmail_oauth_refresh_failed",
            category="auth",
            request_id=getattr(request.state, "request_id", None),
            reason=str(exc),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "GMAIL_OAUTH_REFRESH_FAILED",
                "message": "Gmail OAuth yenilenemedi. Bu hesabı Mail & Sync’te silin, ardından yeniden ekleyin: ‘Google ile Bağlan’ veya ‘Şifre / Uygulama Şifresi’ ile.",
                "details": {"reason": str(exc)},
            },
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            request_logger,
            "mail_ingestion_sync_failed",
            category="mail",
            request_id=getattr(request.state, "request_id", None),
            reason=str(exc),
        )
        session_factory = get_session_factory()
        with session_factory() as session:
            session.add(
                AuditLog(
                    actor_type="system",
                    actor_id=None,
                    action="mail_ingestion_sync_failed",
                    entity_type="mail_ingestion_run",
                    entity_id="-1",
                    metadata_json=json.dumps({"reason": str(exc)}),
                )
            )
            session.commit()
        reason = str(exc)
        if _imap_error_is_invalid_credentials(reason):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "IMAP_AUTHENTICATION_FAILED",
                    "message": _imap_auth_failed_user_message(),
                    "details": {"reason": reason},
                },
            ) from exc
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INGESTION_SYNC_FAILED",
                "message": "Mail bağlantısı veya sync başarısız.",
                "details": {"reason": reason},
            },
        ) from exc
    session_factory = get_session_factory()
    with session_factory() as session:
        session.add(
            AuditLog(
                actor_type="system",
                actor_id=None,
                action="mail_ingestion_sync_completed",
                entity_type="mail_ingestion_run",
                entity_id=str(summary["run_id"]),
                metadata_json=json.dumps(summary),
            )
        )
        session.commit()
    log_event(
        request_logger,
        "mail_ingestion_sync_completed",
        category="mail",
        request_id=getattr(request.state, "request_id", None),
        run_id=summary["run_id"],
        idempotent=idempotent,
    )
    return IngestionSyncResponse(status="ok", idempotent=idempotent, summary=summary)


def _to_run_item(row: MailIngestionRun) -> IngestionRunItemResponse:
    return IngestionRunItemResponse(
        id=row.id,
        mail_account_id=row.mail_account_id,
        status=row.status,
        scanned_messages=row.scanned_messages,
        processed_messages=row.processed_messages,
        duplicate_messages=row.duplicate_messages,
        saved_documents=row.saved_documents,
        duplicate_documents=row.duplicate_documents,
        skipped_attachments=row.skipped_attachments,
        failed_messages=row.failed_messages,
        csv_rows_parsed=row.csv_rows_parsed,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


@app.get("/api/mail-ingestion/runs/{run_id}", response_model=IngestionRunItemResponse)
async def get_mail_ingestion_run(run_id: int, request: Request) -> IngestionRunItemResponse:
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            run = session.get(MailIngestionRun, run_id)
            if not run:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "code": "INGESTION_RUN_NOT_FOUND",
                        "message": "Ingestion run not found.",
                        "details": {"run_id": run_id},
                    },
                )
            return _to_run_item(run)
    except HTTPException:
        raise
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.get("/api/mail-ingestion/runs", response_model=IngestionRunListResponse)
async def list_mail_ingestion_runs(
    request: Request,
    limit: int = 20,
    cursor: int | None = None,
    status: Literal["running", "completed", "completed_with_errors", "failed"] | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
) -> IngestionRunListResponse:
    bounded_limit = min(max(limit, 1), 100)
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            stmt = select(MailIngestionRun)
            if cursor:
                stmt = stmt.where(MailIngestionRun.id < cursor)
            if status:
                stmt = stmt.where(MailIngestionRun.status == status)
            if started_from:
                stmt = stmt.where(MailIngestionRun.started_at >= started_from)
            if started_to:
                stmt = stmt.where(MailIngestionRun.started_at <= started_to)
            rows = session.scalars(stmt.order_by(desc(MailIngestionRun.id)).limit(bounded_limit + 1)).all()
            has_more = len(rows) > bounded_limit
            page_rows = rows[:bounded_limit]
            next_cursor = page_rows[-1].id if has_more and page_rows else None
            return IngestionRunListResponse(items=[_to_run_item(row) for row in page_rows], next_cursor=next_cursor)
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.get("/api/settings/auto-sync")
async def get_auto_sync(request: Request):
    """Return current auto-sync settings."""
    return get_auto_sync_status()


@app.post("/api/settings/auto-sync")
async def set_auto_sync(request: Request):
    """Update auto-sync settings. Body: {enabled?, interval_minutes?}"""
    body = await request.json()
    enabled = body.get("enabled")
    interval_minutes = body.get("interval_minutes")
    try:
        result = update_auto_sync_settings(
            enabled=bool(enabled) if enabled is not None else None,
            interval_minutes=int(interval_minutes) if interval_minutes is not None else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_settings", "message": str(exc)})
    log_event(
        request_logger,
        "auto_sync_settings_updated",
        category="system",
        enabled=result["enabled"],
        interval_minutes=result["interval_minutes"],
        request_id=getattr(request.state, "request_id", None),
    )
    return result


@app.get("/api/settings/llm")
async def get_llm_settings(request: Request):
    """Return current AI/LLM parser settings (API key is masked)."""
    return app_settings.get_api_response()


@app.patch("/api/settings/llm")
async def patch_llm_settings(request: Request):
    """Update AI/LLM parser settings. Body: {llm_provider?, llm_api_url?, llm_api_key?, llm_model?, llm_enabled?, llm_timeout_seconds?}"""
    body = await request.json()
    result = app_settings.update(body)
    log_event(
        request_logger,
        "llm_settings_updated",
        category="system",
        provider=result.get("llm_provider"),
        model=result.get("llm_model"),
        api_key_set=result.get("llm_api_key_set"),
        request_id=getattr(request.state, "request_id", None),
    )
    return result


@app.post("/api/settings/llm/test")
async def test_llm_connection(request: Request):
    """Send a minimal test prompt to verify LLM connectivity."""
    import httpx
    cfg = app_settings.get_llm_config()
    if not cfg["llm_api_url"]:
        raise HTTPException(status_code=400, detail={"code": "no_url", "message": "LLM API URL ayarlanmamış"})
    headers = {"Content-Type": "application/json"}
    if cfg["llm_api_key"]:
        headers["Authorization"] = f"Bearer {cfg['llm_api_key']}"
    payload = {
        "model": cfg["llm_model"],
        "messages": [{"role": "user", "content": "Say PONG"}],
        "max_tokens": 10,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{cfg['llm_api_url'].rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
        if resp.status_code == 200:
            data = resp.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"ok": True, "model": cfg["llm_model"], "reply": reply.strip()}
        else:
            return {"ok": False, "status": resp.status_code, "detail": resp.text[:300]}
    except Exception as exc:
        detail = str(exc) if str(exc) else type(exc).__name__
        return {"ok": False, "detail": detail}


@app.get("/api/statements")
async def list_statements(request: Request, limit: int = 50):
    """Return parsed statement documents with their transaction data."""
    bounded_limit = min(max(limit, 1), 200)
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            docs = session.scalars(
                select(StatementDocument)
                .where(StatementDocument.parse_status == "parsed")
                .order_by(desc(StatementDocument.id))
                .limit(bounded_limit)
            ).all()

            items = []
            for doc in docs:
                parsed = None
                if doc.parsed_json:
                    try:
                        parsed = json.loads(doc.parsed_json)
                    except Exception:
                        pass

                # Fetch email subject for context
                email_row = session.get(EmailIngested, doc.email_ingested_id)

                items.append({
                    "id": doc.id,
                    "file_name": doc.file_name,
                    "doc_type": doc.doc_type,
                    "parse_status": doc.parse_status,
                    "file_size_bytes": doc.file_size_bytes,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "email_subject": email_row.subject if email_row else None,
                    "bank_name": coalesce_bank_display(parsed.get("bank_name")) if parsed else None,
                    "card_number": normalize_optional_llm_str(parsed.get("card_number")) if parsed else None,
                    "period_start": parsed.get("period_start") if parsed else None,
                    "period_end": parsed.get("period_end") if parsed else None,
                    "due_date": parsed.get("due_date") if parsed else None,
                    "total_due_try": parsed.get("total_due_try") if parsed else None,
                    "minimum_due_try": parsed.get("minimum_due_try") if parsed else None,
                    "transaction_count": len(parsed.get("transactions", [])) if parsed else 0,
                    "transactions": parsed.get("transactions", []) if parsed else [],
                    "parse_notes": parsed.get("parse_notes", []) if parsed else [],
                })

            return {"items": items}
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


def _compute_ingestion_stats(session) -> dict[str, Any]:
    status_rows = session.execute(
        select(StatementDocument.parse_status, func.count())
        .select_from(StatementDocument)
        .group_by(StatementDocument.parse_status)
    ).all()
    by_status: dict[str, int] = {str(r[0]): int(r[1]) for r in status_rows}
    total = sum(by_status.values())
    parsed_n = by_status.get("parsed", 0)
    failed_n = by_status.get("parse_failed", 0)
    pending_n = by_status.get("pending", 0)
    unsupported_n = by_status.get("unsupported", 0)
    non_parsed = failed_n + pending_n + unsupported_n
    return {
        "total": total,
        "parsed": parsed_n,
        "parse_failed": failed_n,
        "pending": pending_n,
        "unsupported": unsupported_n,
        "non_parsed": non_parsed,
    }


def _ingestion_document_row(doc: StatementDocument, email_row: EmailIngested | None) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    if doc.parsed_json:
        try:
            parsed = json.loads(doc.parsed_json)
        except Exception:
            parsed = None
    tx_count = len(parsed.get("transactions", [])) if parsed else 0
    notes = list(parsed.get("parse_notes", [])) if parsed else []
    bank = coalesce_bank_display(parsed.get("bank_name")) if parsed else None
    return {
        "id": doc.id,
        "file_name": doc.file_name,
        "doc_type": doc.doc_type,
        "parse_status": doc.parse_status,
        "file_size_bytes": doc.file_size_bytes,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "email_subject": email_row.subject if email_row else None,
        "bank_name": bank,
        "transaction_count": tx_count,
        "parse_notes": notes,
    }


@app.get("/api/ingestion/documents")
async def list_ingestion_documents(
    request: Request,
    doc_filter: str = Query("all", alias="filter", description="all | non_parsed | parsed | parse_failed"),
    limit: int = Query(200, ge=1, le=500),
):
    """All statement files (PDF/CSV) with parse status — parsed, failed, pending.

    filter: all | non_parsed | parsed | parse_failed
    """
    bounded = min(max(limit, 1), 500)
    fl = (doc_filter or "all").strip().lower()
    if fl not in ("all", "non_parsed", "parsed", "parse_failed"):
        fl = "all"

    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            stats = _compute_ingestion_stats(session)

            q = select(StatementDocument).order_by(desc(StatementDocument.id)).limit(bounded)
            if fl == "non_parsed":
                q = select(StatementDocument).where(StatementDocument.parse_status != "parsed").order_by(
                    desc(StatementDocument.id)
                ).limit(bounded)
            elif fl == "parsed":
                q = select(StatementDocument).where(StatementDocument.parse_status == "parsed").order_by(
                    desc(StatementDocument.id)
                ).limit(bounded)
            elif fl == "parse_failed":
                q = select(StatementDocument).where(StatementDocument.parse_status == "parse_failed").order_by(
                    desc(StatementDocument.id)
                ).limit(bounded)

            docs = session.scalars(q).all()
            items: list[dict[str, Any]] = []
            for doc in docs:
                email_row = session.get(EmailIngested, doc.email_ingested_id)
                items.append(_ingestion_document_row(doc, email_row))

            return {"stats": stats, "items": items, "filter": fl}
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.get("/api/ingestion/documents/stats")
async def ingestion_documents_stats(request: Request):
    """Lightweight counts for nav badges (no document rows)."""
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            return {"stats": _compute_ingestion_stats(session)}
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.get("/api/statements/{doc_id}/pdf")
async def get_statement_original_pdf(doc_id: int, request: Request):
    """Return the original PDF from IMAP (not stored on disk). Inline display in browser."""
    from app.ingestion.reparse_from_imap import fetch_pdf_bytes_for_statement

    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            pdf, err, fname = fetch_pdf_bytes_for_statement(session, doc_id)
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))

    if err:
        err_map: dict[str, tuple[int, str]] = {
            "not_found_or_not_pdf": (404, "Ekstre PDF kaydı bulunamadı."),
            "email_or_account_missing": (502, "İlişkili mail kaydı veya hesap yok."),
            "mail_account_missing": (502, "Mail hesabı bulunamadı veya pasif."),
            "no_message_id": (502, "Message-ID eksik."),
            "pdf_not_found_in_imap": (
                404,
                "PDF posta kutusunda bulunamadı (silinmiş, taşınmış veya etiket dışı olabilir).",
            ),
        }
        status, msg = err_map.get(err, (502, err))
        raise HTTPException(status_code=status, detail={"code": err, "message": msg})

    safe_ascii = "".join(
        c if 32 <= ord(c) < 127 and c not in '\\"' else "_"
        for c in (fname or "ekstre.pdf")
    )
    disp = f'inline; filename="{safe_ascii}"; filename*=UTF-8\'\'{quote(fname or "ekstre.pdf")}'
    log_event(
        request_logger,
        "statement_pdf_served",
        category="parser",
        doc_id=doc_id,
        request_id=getattr(request.state, "request_id", None),
    )
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": disp})


@app.post("/api/statements/reparse")
async def reparse_statements(request: Request):
    """Re-fetch PDFs from IMAP and run the AI parser again (e.g. after enabling LLM).

    Body: { "scope": "empty" | "failed" | "all_pdf" | "selected", "doc_ids"?: number[] }
    """
    body = await request.json()
    scope = body.get("scope", "empty")
    raw_ids = body.get("doc_ids") or []
    if scope not in ("selected", "empty", "failed", "all_pdf"):
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_scope", "message": "scope: selected | empty | failed | all_pdf"},
        )
    if not isinstance(raw_ids, list):
        raw_ids = []
    doc_ids_int: list[int] = []
    for x in raw_ids:
        try:
            doc_ids_int.append(int(x))
        except (TypeError, ValueError):
            continue

    from app.ingestion.reparse_from_imap import run_batch_reparse

    result = await asyncio.to_thread(run_batch_reparse, scope, doc_ids_int, 50)
    if not result.get("ok") and result.get("error") == "llm_not_configured":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "llm_not_configured",
                "message": result.get("message", "LLM yapılandırılmamış."),
            },
        )
    log_event(
        request_logger,
        "statements_reparse_batch",
        category="parser",
        scope=scope,
        processed=result.get("processed"),
        succeeded=result.get("succeeded"),
        request_id=getattr(request.state, "request_id", None),
    )
    return result


@app.delete("/api/statements/{doc_id}")
async def delete_statement(doc_id: int, request: Request):
    """Delete a single parsed statement document and its email if no other docs reference it."""
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            doc = session.get(StatementDocument, doc_id)
            if not doc:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "not_found", "message": "Ekstre bulunamadı."},
                )
            email_id = doc.email_ingested_id
            session.delete(doc)
            session.flush()

            # If this was the only document for the email, delete the email too
            remaining = session.scalar(
                select(func.count(StatementDocument.id)).where(
                    StatementDocument.email_ingested_id == email_id
                )
            )
            if remaining == 0:
                email_row = session.get(EmailIngested, email_id)
                if email_row:
                    session.delete(email_row)

            session.commit()
            log_event(
                request_logger, "statement_deleted", category="parser",
                doc_id=doc_id, request_id=getattr(request.state, "request_id", None),
            )
            return {"deleted": True, "doc_id": doc_id}
    except HTTPException:
        raise
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.delete("/api/statements")
async def delete_statements_bulk(request: Request):
    """Delete multiple statement documents. Body: {ids: [1,2,3]}"""
    body = await request.json()
    ids: list[int] = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400, detail={"code": "no_ids", "message": "id listesi boş."})
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            deleted_count = 0
            email_ids: set[int] = set()
            for doc_id in ids:
                doc = session.get(StatementDocument, doc_id)
                if doc:
                    email_ids.add(doc.email_ingested_id)
                    session.delete(doc)
                    deleted_count += 1
            session.flush()

            # Clean up orphaned emails
            for email_id in email_ids:
                remaining = session.scalar(
                    select(func.count(StatementDocument.id)).where(
                        StatementDocument.email_ingested_id == email_id
                    )
                )
                if remaining == 0:
                    email_row = session.get(EmailIngested, email_id)
                    if email_row:
                        session.delete(email_row)

            session.commit()
            log_event(
                request_logger, "statements_bulk_deleted", category="parser",
                count=deleted_count, request_id=getattr(request.state, "request_id", None),
            )
            return {"deleted": True, "count": deleted_count}
    except HTTPException:
        raise
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.post("/api/system/reset-ingestion")
async def system_reset_ingestion(request: Request):
    """Delete all ekstre/mail ingestion data (not mail accounts, not LLM settings). Body: { \"confirm\": \"SIFIRLA\" }."""
    body = await request.json()
    confirm = (body.get("confirm") or "").strip()
    if confirm != RESET_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "confirm_required",
                "message": f'Onay için tam olarak "{RESET_CONFIRM_PHRASE}" yazın.',
            },
        )
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            result = reset_ingestion_data(session)
        log_event(
            request_logger,
            "system_reset_ingestion",
            category="system",
            request_id=getattr(request.state, "request_id", None),
            deleted=result.get("deleted"),
        )
        return result
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.post("/api/system/clear-learned-rules")
async def system_clear_learned_rules(request: Request):
    """Test: delete only learned_parser_rules. Body: { \"confirm\": \"KURALLAR\" }."""
    body = await request.json()
    confirm = (body.get("confirm") or "").strip()
    if confirm != CLEAR_LEARNED_RULES_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "confirm_required",
                "message": f'Onay için tam olarak "{CLEAR_LEARNED_RULES_CONFIRM_PHRASE}" yazın.',
            },
        )
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            result = clear_learned_parser_rules(session)
        log_event(
            request_logger,
            "learned_parser_rules_cleared",
            category="system",
            request_id=getattr(request.state, "request_id", None),
            deleted=result.get("deleted_learned_parser_rules"),
        )
        return result
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.post("/api/system/clear-email-ingestion-cache")
async def system_clear_email_ingestion_cache(request: Request):
    """Remove processed mail + ekstre rows so the next sync can re-import the same IMAP messages.

    Body: { \"confirm\": \"POSTA\" }. Does not delete learned rules or audit log (unlike SIFIRLA).
    """
    body = await request.json()
    confirm = (body.get("confirm") or "").strip()
    if confirm != CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "confirm_required",
                "message": f'Onay için tam olarak "{CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE}" yazın.',
            },
        )
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            result = clear_email_ingestion_cache(session)
        log_event(
            request_logger,
            "email_ingestion_cache_cleared",
            category="system",
            request_id=getattr(request.state, "request_id", None),
            deleted=result.get("deleted"),
        )
        return result
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


@app.get("/api/parser/changes")
async def list_parser_changes(
    request: Request,
    status: str = "pending",
):
    log_event(
        request_logger,
        "parser_changes_listed",
        category="parser",
        request_id=getattr(request.state, "request_id", None),
        status=status,
    )
    return {"items": [], "status": status}


@app.post("/api/parser/changes/{change_id}/approve")
async def approve_parser_change(change_id: int, request: Request):
    log_event(
        request_logger,
        "parser_change_approved",
        category="parser",
        request_id=getattr(request.state, "request_id", None),
        change_id=change_id,
    )
    return {"status": "approved", "change_id": change_id}


@app.post("/api/parser/changes/{change_id}/reject")
async def reject_parser_change(change_id: int, request: Request):
    log_event(
        request_logger,
        "parser_change_rejected",
        category="parser",
        request_id=getattr(request.state, "request_id", None),
        change_id=change_id,
    )
    return {"status": "rejected", "change_id": change_id}


def _oauth_base(request: Request) -> tuple[str, str]:
    """(redirect_uri, redirect_base_path) for OAuth. Uses X-Forwarded-*, X-Ingress-Path, or Referer when behind proxy."""
    forwarded_host = request.headers.get("x-forwarded-host", "").strip().split(",")[0].strip()
    forwarded_proto = request.headers.get("x-forwarded-proto", "").strip().split(",")[0].strip()
    ingress_path = request.headers.get("x-ingress-path", "").strip()
    if ingress_path and not ingress_path.endswith("/"):
        ingress_path += "/"
    if forwarded_host or ingress_path:
        host = forwarded_host or (request.headers.get("host") or "").split(":")[0].strip()
        scheme = forwarded_proto or "https"
        if host:
            base = f"{scheme}://{host}{ingress_path}".rstrip("/")
            return f"{base}/api/oauth/gmail/callback", ingress_path or "/"
    referer = request.headers.get("referer") or request.headers.get("referrer")
    if referer:
        from urllib.parse import urlparse
        try:
            p = urlparse(referer)
            if p.scheme and p.netloc and "accounts.google.com" not in p.netloc:
                path = p.path.rstrip("/") or "/"
                if "/api/" in path:
                    path = path.split("/api/")[0].rstrip("/") or "/"
                base = f"{p.scheme}://{p.netloc}{path}"
                return f"{base}/api/oauth/gmail/callback", path
        except Exception:
            pass
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/oauth/gmail/callback", "/"


def _oauth_redirect_uri(request: Request) -> str:
    uri, _ = _oauth_base(request)
    return uri


@app.get("/api/oauth/gmail/redirect-uri")
async def gmail_oauth_redirect_uri_info(request: Request):
    """Returns the redirect URI to add in Google Cloud Console. Helps with HA Ingress setup."""
    uri = _oauth_redirect_uri(request)
    return {"redirect_uri": uri}


@app.get("/api/oauth/gmail/start")
async def gmail_oauth_start(request: Request, label: str = "Gmail Hesabı"):
    import base64
    from urllib.parse import quote

    settings = get_settings()
    if not settings.gmail_oauth_client_id or not settings.gmail_oauth_client_secret:
        _, base_path = _oauth_base(request)
        # Must end with / before ?query or HA ingress route 404s on .../TOKEN?oauth=...
        root = base_path.rstrip("/") or "/"
        if not root.endswith("/"):
            root += "/"
        return RedirectResponse(f"{root}?oauth=not_configured")
    our_callback = _oauth_redirect_uri(request)
    if settings.gmail_oauth_redirect_proxy_url:
        redirect_uri = settings.gmail_oauth_redirect_proxy_url.rstrip("/")
        if "?" in redirect_uri:
            redirect_uri = redirect_uri.split("?")[0]
        callback_with_label = f"{our_callback}?label={quote(label)}"
        state = base64.urlsafe_b64encode(callback_with_label.encode("utf-8")).decode("ascii")
    else:
        redirect_uri = our_callback
        state = label
    url = build_auth_url(
        client_id=settings.gmail_oauth_client_id,
        redirect_uri=redirect_uri,
        state=state,
    )
    return RedirectResponse(url)


@app.get("/api/oauth/gmail/callback")
async def gmail_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    label: str | None = None,
):
    import base64
    from urllib.parse import quote

    _, base_path = _oauth_base(request)
    root = base_path.rstrip("/") or "/"
    if not root.endswith("/"):
        root += "/"

    if error:
        return RedirectResponse(f"{root}?oauth=error&reason={quote(error, safe='')}")

    if not code:
        raise HTTPException(status_code=400, detail={"code": "OAUTH_NO_CODE", "message": "Kod eksik."})

    settings = get_settings()
    if settings.gmail_oauth_redirect_proxy_url:
        redirect_uri = settings.gmail_oauth_redirect_proxy_url.rstrip("/").split("?")[0]
    else:
        redirect_uri = _oauth_redirect_uri(request)
    account_label = label or state or "Gmail Hesabı"
    if state and not label and settings.gmail_oauth_redirect_proxy_url:
        try:
            pad = 4 - len(state) % 4
            if pad != 4:
                state_padded = state + ("=" * pad)
            else:
                state_padded = state
            decoded = base64.urlsafe_b64decode(state_padded).decode("utf-8")
            if "?label=" in decoded:
                from urllib.parse import parse_qs
                parsed = parse_qs(decoded.split("?", 1)[1])
                if parsed.get("label"):
                    account_label = parsed["label"][0]
        except Exception:
            pass
    try:
        tokens = exchange_code_for_tokens(
            client_id=settings.gmail_oauth_client_id,
            client_secret=settings.gmail_oauth_client_secret,
            code=code,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:
        log_event(request_logger, "gmail_oauth_token_exchange_failed", category="auth", error=str(exc))
        return RedirectResponse(f"{root}?oauth=error&reason=token_exchange_failed")

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return RedirectResponse(f"{root}?oauth=error&reason=no_refresh_token")

    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            account = MailAccount(
                provider="gmail",
                auth_mode="oauth_gmail",
                account_label=account_label,
                imap_host="imap.gmail.com",
                imap_port=993,
                imap_user=label,
                imap_password="",
                oauth_refresh_token=refresh_token,
                mailbox="INBOX",
                unseen_only=True,
                fetch_limit=20,
                retry_count=3,
                retry_backoff_seconds=1.5,
                is_active=True,
            )
            session.add(account)
            session.commit()
            session.refresh(account)
            account_id = account.id
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))

    log_event(request_logger, "gmail_oauth_account_created", category="auth", account_id=account_id)
    return RedirectResponse(f"{root}?oauth=success&account_id={account_id}")


@app.get("/api/activity-log")
async def get_activity_log(request: Request, limit: int = 80):
    """Combined activity feed: mail sync runs + document parse events."""
    bounded_limit = min(max(limit, 1), 200)
    session_factory = get_session_factory()
    try:
        with session_factory() as session:
            runs = session.scalars(
                select(MailIngestionRun).order_by(desc(MailIngestionRun.id)).limit(30)
            ).all()
            docs = session.scalars(
                select(StatementDocument).order_by(desc(StatementDocument.id)).limit(60)
            ).all()

            account_ids = {r.mail_account_id for r in runs if r.mail_account_id}
            accounts_by_id: dict[int, MailAccount] = {}
            if account_ids:
                for acc in session.scalars(select(MailAccount).where(MailAccount.id.in_(account_ids))).all():
                    accounts_by_id[acc.id] = acc

            activities: list[dict] = []

            for run in runs:
                duration = None
                if run.started_at and run.finished_at:
                    duration = round((run.finished_at - run.started_at).total_seconds())
                ts = run.finished_at or run.started_at
                acc = accounts_by_id.get(run.mail_account_id) if run.mail_account_id else None
                activities.append({
                    "type": "mail_sync",
                    "id": f"run_{run.id}",
                    "run_id": run.id,
                    "timestamp": ts.isoformat() if ts else None,
                    "status": run.status,
                    "mail_account_id": run.mail_account_id,
                    "account_label": acc.account_label if acc else None,
                    "imap_user": acc.imap_user if acc else None,
                    "scanned": run.scanned_messages,
                    "processed": run.processed_messages,
                    "saved": run.saved_documents,
                    "failed": run.failed_messages,
                    "duplicates": run.duplicate_messages,
                    "duration_seconds": duration,
                    "notes": run.notes,
                })

            for doc in docs:
                email_row = session.get(EmailIngested, doc.email_ingested_id)
                bank_name = None
                tx_count = 0
                parse_notes: list[str] = []
                # parsed_json is stored for both parsed and parse_failed (timeout / LLM error notes)
                if doc.parsed_json:
                    try:
                        parsed = json.loads(doc.parsed_json)
                        bank_name = coalesce_bank_display(parsed.get("bank_name"))
                        tx_count = len(parsed.get("transactions", []))
                        parse_notes = parsed.get("parse_notes", [])
                    except Exception:
                        pass
                activities.append({
                    "type": "document_parse",
                    "id": f"doc_{doc.id}",
                    "doc_id": doc.id,
                    "timestamp": doc.created_at.isoformat() if doc.created_at else None,
                    "status": doc.parse_status,
                    "file_name": doc.file_name,
                    "doc_type": doc.doc_type,
                    "bank_name": bank_name or (email_row.bank_name if email_row else None),
                    "email_subject": email_row.subject if email_row else None,
                    "transaction_count": tx_count,
                    "file_size_bytes": doc.file_size_bytes,
                    "parse_notes": parse_notes,
                })

            activities.sort(key=lambda a: a.get("timestamp") or "", reverse=True)
            activities = activities[:bounded_limit]

            total_docs = session.scalar(select(func.count(StatementDocument.id))) or 0
            parsed_docs = session.scalar(
                select(func.count(StatementDocument.id)).where(StatementDocument.parse_status == "parsed")
            ) or 0
            failed_docs = session.scalar(
                select(func.count(StatementDocument.id)).where(StatementDocument.parse_status == "parse_failed")
            ) or 0

            return {
                "activities": activities,
                "auto_sync": get_auto_sync_status(),
                "stats": {
                    "total_docs": total_docs,
                    "parsed_docs": parsed_docs,
                    "failed_docs": failed_docs,
                },
            }
    except (OperationalError, SQLAlchemyError) as exc:
        _raise_db_unavailable(exc, getattr(request.state, "request_id", None))


# ── Serve built frontend (production) ──────────────────────────────────────
# The React app is built into ui/dist/ by `npm run build`.
# In development, Vite dev server is used instead.
_FRONTEND_DIR = pathlib.Path(__file__).parent.parent / "ui" / "dist"


def _ingress_base_href(request: Request) -> str:
    """Directory path for `<base href>` (trailing slash).

    Home Assistant Core sets **X-Ingress-Path** to `/api/hassio_ingress/{token}`
    (`homeassistant/components/hassio/ingress.py`). Some reverse proxies strip it;
    we also parse **Referer** when it contains `hassio_ingress` or `/app/<slug>`.
    """
    ingress_path = request.headers.get("x-ingress-path", "").strip()
    if ingress_path:
        return ingress_path if ingress_path.endswith("/") else ingress_path + "/"

    referer = (request.headers.get("referer") or request.headers.get("referrer") or "").strip()
    if referer:
        try:
            rpath = urlparse(referer).path or ""
            if "/api/hassio_ingress/" in rpath:
                m = re.search(r"(/api/hassio_ingress/[^/]+)", rpath)
                if m:
                    return m.group(1) + "/"
            rparts = [p for p in rpath.split("/") if p]
            if len(rparts) >= 2 and rparts[0] == "app":
                return "/" + "/".join(rparts[:2]) + "/"
        except Exception:
            pass

    raw_path = request.url.path.rstrip("/") or "/"
    parts = [p for p in raw_path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "app":
        return "/" + "/".join(parts[:2]) + "/"
    if len(parts) >= 3 and parts[0] == "hassio" and parts[1] == "ingress":
        return "/" + "/".join(parts[:3]) + "/"
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "hassio_ingress":
        return "/" + "/".join(parts[:3]) + "/"
    return "/"


def _rewrite_ingress_asset_urls(page_html: str, base_href: str) -> str:
    """Turn `./assets/...` into `{base}assets/...` so JS/CSS load without relying on <base>."""
    if base_href == "/":
        return page_html
    page_html = page_html.replace('src="./assets/', f'src="{base_href}assets/')
    page_html = page_html.replace("src='./assets/", f"src='{base_href}assets/")
    page_html = page_html.replace('href="./assets/', f'href="{base_href}assets/')
    page_html = page_html.replace("href='./assets/", f"href='{base_href}assets/")
    return page_html


if _FRONTEND_DIR.is_dir():
    # Serve /assets/* and other static files
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR / "assets")), name="assets")

    _INDEX_HTML_PATH = _FRONTEND_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _serve_spa(request: Request, full_path: str):
        """Catch-all: serve index.html for any non-API path (SPA routing)."""
        # Never intercept /api/* — those are handled by the routes above
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        file_path = _FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        page_html = _INDEX_HTML_PATH.read_text(encoding="utf-8")
        base_href = _ingress_base_href(request)
        base_tag = f'<base href="{html.escape(base_href, quote=True)}">'
        page_html = page_html.replace("<head>", f"<head>\n    {base_tag}", 1)
        page_html = _rewrite_ingress_asset_urls(page_html, base_href)
        return HTMLResponse(page_html)


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()

