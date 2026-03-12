from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


IngestionRunStatus = Literal["running", "completed", "completed_with_errors", "failed"]


class IngestionSummaryResponse(BaseModel):
    run_id: int
    scanned_messages: int
    processed_messages: int
    duplicate_messages: int
    saved_documents: int
    duplicate_documents: int
    skipped_attachments: int
    failed_messages: int
    csv_rows_parsed: int


class IngestionSyncResponse(BaseModel):
    status: Literal["ok"]
    idempotent: bool = False
    summary: IngestionSummaryResponse


class IngestionRunItemResponse(BaseModel):
    id: int
    mail_account_id: int | None = None
    status: IngestionRunStatus
    scanned_messages: int
    processed_messages: int
    duplicate_messages: int
    saved_documents: int
    duplicate_documents: int
    skipped_attachments: int
    failed_messages: int
    csv_rows_parsed: int
    started_at: datetime
    finished_at: datetime | None


class IngestionRunListResponse(BaseModel):
    items: list[IngestionRunItemResponse] = Field(default_factory=list)
    next_cursor: int | None = None
