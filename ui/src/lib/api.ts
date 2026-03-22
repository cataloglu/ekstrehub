export type HealthResponse = {
  status: string;
  service: string;
  /** Home Assistant add-on sürümü (`ekstrehub/config.yaml` → image ile aynı) */
  addon_version?: string | null;
  environment: string;
  mail_ingestion_enabled: boolean;
  masked_imap_user: string;
  db_available?: boolean;
  gmail_oauth_configured?: boolean;
};

export type IngestionRunItem = {
  id: number;
  mail_account_id?: number | null;
  status: "running" | "completed" | "completed_with_errors" | "failed";
  scanned_messages: number;
  processed_messages: number;
  duplicate_messages: number;
  saved_documents: number;
  duplicate_documents: number;
  skipped_attachments: number;
  failed_messages: number;
  csv_rows_parsed: number;
  started_at: string;
  finished_at: string | null;
};

export type IngestionRunListResponse = {
  items: IngestionRunItem[];
  next_cursor: number | null;
};

export type IngestionRunStatus = IngestionRunItem["status"];

export type MailAccount = {
  id: number;
  provider: "gmail" | "outlook" | "custom";
  auth_mode: "password" | "oauth_gmail";
  account_label: string;
  imap_host: string;
  imap_port: number;
  imap_user: string;
  mailbox: string;
  unseen_only: boolean;
  fetch_limit: number;
  retry_count: number;
  retry_backoff_seconds: number;
  is_active: boolean;
  created_at: string;
};

export type MailAccountListResponse = {
  items: MailAccount[];
};

export type MailAccountCreatePayload = {
  provider: "gmail" | "outlook" | "custom";
  auth_mode: "password" | "oauth_gmail";
  account_label: string;
  imap_host: string;
  imap_port: number;
  imap_user: string;
  imap_password: string;
  oauth_refresh_token?: string | null;
  mailbox: string;
  unseen_only: boolean;
  fetch_limit: number;
  retry_count: number;
  retry_backoff_seconds: number;
  is_active: boolean;
};

export type IngestionSyncResponse = {
  status: "ok";
  idempotent: boolean;
  summary: {
    run_id: number;
  };
};

export type StatementTransaction = {
  date: string | null;
  description: string;
  amount: number;
  currency: string;
};

/** PDF notices: Pazarama/MaxiMil expiry, legal warnings, contract updates (from parser heuristics). */
export type StatementReminder = {
  title: string;
  text: string;
  kind: string;
  expires_on: string | null;
};

export type StatementItem = {
  id: number;
  file_name: string;
  doc_type: string;
  parse_status: string;
  file_size_bytes: number;
  created_at: string | null;
  email_subject: string | null;
  bank_name: string | null;
  card_number: string | null;
  period_start: string | null;
  period_end: string | null;
  due_date: string | null;
  total_due_try: number | null;
  minimum_due_try: number | null;
  transaction_count: number;
  transactions: StatementTransaction[];
  parse_notes: string[];
  statement_reminders?: StatementReminder[];
};

export type StatementListResponse = {
  items: StatementItem[];
};

/** Tüm mail ekleri (PDF/CSV) — parse durumu dahil */
export type IngestionStats = {
  total: number;
  parsed: number;
  parse_failed: number;
  pending: number;
  unsupported: number;
  non_parsed: number;
};

export type IngestionDocumentItem = {
  id: number;
  file_name: string;
  doc_type: string;
  parse_status: string;
  file_size_bytes: number;
  created_at: string | null;
  email_subject: string | null;
  bank_name: string | null;
  transaction_count: number;
  parse_notes: string[];
};

export type IngestionDocumentsResponse = {
  stats: IngestionStats;
  items: IngestionDocumentItem[];
  filter: string;
};

export type ParserChangeItem = {
  id: number;
  status: "pending" | "approved" | "rejected";
  bank_name: string;
  reason: string;
  detected_at: string;
};

export type ParserChangeListResponse = {
  items: ParserChangeItem[];
  status: string;
};

export type RequestOptions = {
  requestId?: string;
};

/**
 * Home Assistant Ingress: `fetch("api/...")` çağrıları `<base href>` ile çözülür.
 * OAuth için tam URL üretirken de **aynı tabanı** kullanmalıyız; yalnızca `location.pathname`
 * kullanmak Ingress'te 404'e yol açabilir (panel/iframe veya path uyuşmazlığı).
 */
export function apiUrlPath(path: string): string {
  if (typeof window === "undefined") {
    return path.startsWith("/") ? path : `/${path}`;
  }
  const p = path.replace(/^\//, "");
  const baseEl = document.querySelector("base");
  let base: string;
  if (baseEl?.href) {
    base = baseEl.href;
  } else {
    let pathname = window.location.pathname;
    if (!pathname.endsWith("/")) {
      pathname = `${pathname}/`;
    }
    base = `${window.location.origin}${pathname}`;
  }
  if (!base.endsWith("/")) {
    base = `${base}/`;
  }
  return new URL(p, base).href;
}

/**
 * Gmail OAuth (Ingress iframe): yeni sekmede aç; popup engellenirse aynı pencerede git.
 *
 * ÖNEMLİ: `window.open(..., "noopener")` çoğu tarayıcıda **her zaman `null` döndürür**;
 * önceki kod bunu “engellendi” sanıp `location.assign` yapıyordu → Google OAuth hiç yeni sekmede
 * açılmıyordu. `noopener`’ı açılan pencerede `w.opener = null` ile sağlıyoruz.
 */
export function openOAuthInNewTabOrNavigate(url: string): void {
  try {
    let w: Window | null = window.open(url, "_blank");
    if (w) {
      w.opener = null;
      return;
    }
    const topWin = window.top;
    if (topWin && topWin !== window) {
      w = topWin.open(url, "_blank");
      if (w) {
        w.opener = null;
        return;
      }
    }
    window.location.assign(url);
  } catch {
    window.location.assign(url);
  }
}

function withRequestHeaders(headers: HeadersInit = {}, options?: RequestOptions): HeadersInit {
  if (!options?.requestId) {
    return headers;
  }
  return {
    ...headers,
    "X-Request-ID": options.requestId,
  };
}

const VALIDATION_FIELD_NAMES: Record<string, string> = {
  account_label: "Hesap adı",
  imap_user: "E-posta adresi",
  imap_password: "Şifre / Uygulama şifresi",
  imap_host: "IMAP sunucusu",
  mailbox: "Posta kutusu",
};

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as {
      error?: { code?: string; message?: string; details?: { reason?: string } };
      detail?:
        | { code?: string; message?: string; details?: { reason?: string } }
        | Array<{ loc?: (string | number)[]; msg?: string }>;
    };
    const rawDetail = payload.detail;
    if (Array.isArray(rawDetail) && rawDetail.length > 0) {
      const parts = rawDetail.slice(0, 3).map((e) => {
        const loc = e.loc;
        const field = Array.isArray(loc) && typeof loc[loc.length - 1] === "string"
          ? VALIDATION_FIELD_NAMES[loc[loc.length - 1] as string] ?? loc[loc.length - 1]
          : null;
        const msg = e.msg ?? "";
        return field ? `${field}: ${msg}` : msg;
      });
      return parts.join(". ") || fallback;
    }
    const err = payload.error ?? (typeof rawDetail === "object" && rawDetail !== null && !Array.isArray(rawDetail) ? rawDetail : null);
    const code = err?.code;
    const message = err?.message;
    const reason = err?.details?.reason;
    if (code === "IMAP_AUTHENTICATION_FAILED" && message) {
      return message;
    }
    if (reason && message) {
      return `${message} ${reason}`.trim();
    }
    if (code && message) {
      return `${code}: ${message}`;
    }
    if (message) {
      return message;
    }
    if (reason) {
      return reason;
    }
  } catch {
    // keep fallback when non-json error body
  }
  return fallback;
}

export async function getHealth(options?: RequestOptions): Promise<HealthResponse> {
  const response = await fetch("api/health", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Health request failed with status ${response.status}`));
  }
  return (await response.json()) as HealthResponse;
}

export async function getIngestionRuns(
  limit = 5,
  cursor?: number,
  status?: IngestionRunStatus | "all",
  options?: RequestOptions
): Promise<IngestionRunListResponse> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (typeof cursor === "number") {
    query.set("cursor", String(cursor));
  }
  if (status && status !== "all") {
    query.set("status", status);
  }
  const response = await fetch(`api/mail-ingestion/runs?${query.toString()}`, {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Ingestion runs request failed with status ${response.status}`));
  }
  return (await response.json()) as IngestionRunListResponse;
}

export async function getMailAccounts(options?: RequestOptions): Promise<MailAccountListResponse> {
  const response = await fetch("api/mail-accounts", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Mail accounts request failed with status ${response.status}`));
  }
  return (await response.json()) as MailAccountListResponse;
}

export async function createMailAccount(
  payload: MailAccountCreatePayload,
  options?: RequestOptions
): Promise<MailAccount> {
  const response = await fetch("api/mail-accounts", {
    method: "POST",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Create mail account failed with status ${response.status}`));
  }
  return (await response.json()) as MailAccount;
}

export async function patchMailAccount(
  accountId: number,
  patch: Partial<Pick<MailAccount, "mailbox" | "fetch_limit" | "unseen_only" | "is_active" | "account_label">>,
  options?: RequestOptions
): Promise<MailAccount> {
  const response = await fetch(`api/mail-accounts/${accountId}`, {
    method: "PATCH",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Patch mail account failed with status ${response.status}`));
  }
  return (await response.json()) as MailAccount;
}

export async function deleteMailAccount(accountId: number, options?: RequestOptions): Promise<void> {
  const response = await fetch(`api/mail-accounts/${accountId}`, {
    method: "DELETE",
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Mail hesabı silinemedi (${response.status})`));
  }
}

export async function triggerMailSync(
  mailAccountId: number,
  options?: RequestOptions
): Promise<IngestionSyncResponse> {
  const response = await fetch(
    `api/mail-ingestion/sync?mail_account_id=${encodeURIComponent(String(mailAccountId))}`,
    {
      method: "POST",
      headers: withRequestHeaders(
        { Accept: "application/json", "Idempotency-Key": `ui-${mailAccountId}-${crypto.randomUUID()}` },
        options
      ),
    }
  );
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Mail sync failed with status ${response.status}`));
  }
  return (await response.json()) as IngestionSyncResponse;
}

export async function getStatements(
  options?: RequestOptions & { limit?: number }
): Promise<StatementListResponse> {
  const limit = options?.limit;
  const rest: RequestOptions | undefined = options
    ? (() => {
        const o = { ...options } as RequestOptions & { limit?: number };
        delete o.limit;
        return o;
      })()
    : undefined;
  const url = typeof limit === "number" ? `api/statements?limit=${encodeURIComponent(String(limit))}` : "api/statements";
  const response = await fetch(url, {
    headers: withRequestHeaders({ Accept: "application/json" }, rest),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Statements request failed with status ${response.status}`));
  }
  return (await response.json()) as StatementListResponse;
}

export async function getIngestionDocumentsStats(
  options?: RequestOptions
): Promise<{ stats: IngestionStats }> {
  const response = await fetch("api/ingestion/documents/stats", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Dosya istatistikleri başarısız: ${response.status}`));
  }
  return (await response.json()) as { stats: IngestionStats };
}

export async function getIngestionDocuments(
  filter: string,
  limit: number,
  options?: RequestOptions
): Promise<IngestionDocumentsResponse> {
  const params = new URLSearchParams({
    filter: filter || "all",
    limit: String(limit),
  });
  const response = await fetch(`api/ingestion/documents?${params}`, {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Dosya listesi başarısız: ${response.status}`));
  }
  return (await response.json()) as IngestionDocumentsResponse;
}

export async function getParserChanges(
  status: "pending" | "approved" | "rejected" = "pending",
  options?: RequestOptions
): Promise<ParserChangeListResponse> {
  const query = new URLSearchParams({ status });
  const response = await fetch(`api/parser/changes?${query.toString()}`, {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Parser changes request failed with status ${response.status}`));
  }
  return (await response.json()) as ParserChangeListResponse;
}

export async function approveParserChange(
  changeId: number,
  options?: RequestOptions
): Promise<{ status: string; change_id: number }> {
  const response = await fetch(`api/parser/changes/${changeId}/approve`, {
    method: "POST",
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Approve parser change failed with status ${response.status}`));
  }
  return (await response.json()) as { status: string; change_id: number };
}

export type AutoSyncSettings = {
  enabled: boolean;
  interval_minutes: number;
  last_auto_sync_at: string | null;
  next_sync_at: string | null;
};

export async function getAutoSync(options?: RequestOptions): Promise<AutoSyncSettings> {
  const response = await fetch("api/settings/auto-sync", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Auto-sync get failed with status ${response.status}`));
  }
  return (await response.json()) as AutoSyncSettings;
}

export async function setAutoSync(
  payload: Partial<Pick<AutoSyncSettings, "enabled" | "interval_minutes">>,
  options?: RequestOptions
): Promise<AutoSyncSettings> {
  const response = await fetch("api/settings/auto-sync", {
    method: "POST",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Auto-sync update failed with status ${response.status}`));
  }
  return (await response.json()) as AutoSyncSettings;
}

export type LlmSettings = {
  llm_enabled: boolean;
  llm_provider: "ollama" | "openai" | "custom";
  llm_api_url: string;
  llm_api_key_set: boolean;
  llm_api_key_masked: string;
  llm_model: string;
  llm_timeout_seconds: number;
  llm_min_tx_threshold: number;
  provider_defaults: Record<string, { llm_api_url: string; llm_api_key: string; llm_model: string; llm_timeout_seconds: number }>;
};

export async function getLlmSettings(options?: RequestOptions): Promise<LlmSettings> {
  const response = await fetch("api/settings/llm", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) throw new Error(`LLM settings fetch failed: ${response.status}`);
  return (await response.json()) as LlmSettings;
}

export async function patchLlmSettings(
  patch: Partial<{ llm_provider: string; llm_api_url: string; llm_api_key: string; llm_model: string; llm_enabled: boolean; llm_timeout_seconds: number }>,
  options?: RequestOptions
): Promise<LlmSettings> {
  const response = await fetch("api/settings/llm", {
    method: "PATCH",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, `LLM settings update failed: ${response.status}`));
  return (await response.json()) as LlmSettings;
}

export async function testLlmConnection(options?: RequestOptions): Promise<{ ok: boolean; model?: string; reply?: string; detail?: string }> {
  const response = await fetch("api/settings/llm/test", {
    method: "POST",
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  let data: Record<string, unknown>;
  try {
    data = await response.json();
  } catch {
    return { ok: false, detail: `HTTP ${response.status} — geçersiz yanıt` };
  }
  if (!response.ok) {
    let msg: string;
    if (typeof data.detail === "string") {
      msg = data.detail;
    } else if (data.detail && typeof (data.detail as Record<string, unknown>).message === "string") {
      msg = (data.detail as Record<string, unknown>).message as string;
    } else if (typeof data.message === "string") {
      msg = data.message as string;
    } else {
      msg = `HTTP ${response.status}`;
    }
    return { ok: false, detail: msg };
  }
  return data as { ok: boolean; model?: string; reply?: string; detail?: string };
}

export type ReparseBatchResponse = {
  ok: boolean;
  error?: string;
  message?: string;
  processed?: number;
  succeeded?: number;
  failed?: number;
  results?: Array<{
    doc_id: number;
    ok: boolean;
    error?: string;
    bank_name?: string;
    transaction_count?: number;
    parse_notes?: string[];
  }>;
};

export async function reparseStatements(
  scope: "empty" | "failed" | "all_pdf" | "selected",
  doc_ids?: number[],
  options?: RequestOptions
): Promise<ReparseBatchResponse> {
  const response = await fetch("api/statements/reparse", {
    method: "POST",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify({ scope, doc_ids: doc_ids ?? [] }),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Yeniden parse başarısız: ${response.status}`));
  }
  return (await response.json()) as ReparseBatchResponse;
}

export type ActivityMailSync = {
  type: "mail_sync";
  id: string;
  run_id: number;
  timestamp: string | null;
  status: "running" | "completed" | "completed_with_errors" | "failed";
  mail_account_id: number | null;
  /** Hesap adı (sunucudan; yoksa null) */
  account_label?: string | null;
  /** IMAP kullanıcı / e-posta */
  imap_user?: string | null;
  scanned: number;
  processed: number;
  saved: number;
  failed: number;
  duplicates: number;
  duration_seconds: number | null;
  /** İşlem notu / kısa özet (varsa) */
  notes?: string | null;
};

export type ActivityDocParse = {
  type: "document_parse";
  id: string;
  doc_id: number;
  timestamp: string | null;
  status: "pending" | "parsed" | "parse_failed" | "unsupported";
  file_name: string;
  doc_type: string;
  bank_name: string | null;
  email_subject: string | null;
  transaction_count: number;
  file_size_bytes: number;
  parse_notes: string[];
};

export type ActivityEvent = ActivityMailSync | ActivityDocParse;

export type ActivityLogResponse = {
  activities: ActivityEvent[];
  auto_sync: {
    enabled: boolean;
    interval_minutes: number;
    last_auto_sync_at: string | null;
    next_sync_at: string | null;
  };
  stats: {
    total_docs: number;
    parsed_docs: number;
    failed_docs: number;
  };
};

export async function deleteStatement(
  docId: number,
  options?: RequestOptions
): Promise<{ deleted: boolean; doc_id: number }> {
  const response = await fetch(`api/statements/${docId}`, {
    method: "DELETE",
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Delete statement failed: ${response.status}`));
  }
  return (await response.json()) as { deleted: boolean; doc_id: number };
}

/** Must match server `app.system_reset.RESET_CONFIRM_PHRASE` */
export const RESET_INGESTION_CONFIRM_PHRASE = "SIFIRLA";

/** Must match server `app.system_reset.CLEAR_LEARNED_RULES_CONFIRM_PHRASE` */
export const CLEAR_LEARNED_RULES_CONFIRM_PHRASE = "KURALLAR";

/** Must match server `app.system_reset.CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE` */
export const CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE = "POSTA";

export async function resetIngestionData(
  confirm: string,
  options?: RequestOptions
): Promise<{ ok: boolean; deleted: Record<string, number> }> {
  const response = await fetch("api/system/reset-ingestion", {
    method: "POST",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify({ confirm }),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Sıfırlama başarısız: ${response.status}`));
  }
  return (await response.json()) as { ok: boolean; deleted: Record<string, number> };
}

export async function clearLearnedParserRules(
  confirm: string,
  options?: RequestOptions
): Promise<{ ok: boolean; deleted_learned_parser_rules: number }> {
  const response = await fetch("api/system/clear-learned-rules", {
    method: "POST",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify({ confirm }),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Kurallar silinemedi: ${response.status}`));
  }
  return (await response.json()) as { ok: boolean; deleted_learned_parser_rules: number };
}

export async function clearEmailIngestionCache(
  confirm: string,
  options?: RequestOptions
): Promise<{ ok: boolean; deleted: Record<string, number> }> {
  const response = await fetch("api/system/clear-email-ingestion-cache", {
    method: "POST",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify({ confirm }),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Posta önbelleği temizlenemedi: ${response.status}`));
  }
  return (await response.json()) as { ok: boolean; deleted: Record<string, number> };
}

export async function deleteStatementsBulk(
  ids: number[],
  options?: RequestOptions
): Promise<{ deleted: boolean; count: number }> {
  const response = await fetch("api/statements", {
    method: "DELETE",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify({ ids }),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Bulk delete failed: ${response.status}`));
  }
  return (await response.json()) as { deleted: boolean; count: number };
}

export async function getActivityLog(options?: RequestOptions): Promise<ActivityLogResponse> {
  const response = await fetch("api/activity-log", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Activity log request failed: ${response.status}`));
  }
  return (await response.json()) as ActivityLogResponse;
}

export async function rejectParserChange(
  changeId: number,
  options?: RequestOptions
): Promise<{ status: string; change_id: number }> {
  const response = await fetch(`api/parser/changes/${changeId}/reject`, {
    method: "POST",
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Reject parser change failed with status ${response.status}`));
  }
  return (await response.json()) as { status: string; change_id: number };
}
