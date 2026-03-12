export type HealthResponse = {
  status: string;
  service: string;
  environment: string;
  mail_ingestion_enabled: boolean;
  masked_imap_user: string;
  db_available?: boolean;
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
};

export type StatementListResponse = {
  items: StatementItem[];
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

function withRequestHeaders(headers: HeadersInit = {}, options?: RequestOptions): HeadersInit {
  if (!options?.requestId) {
    return headers;
  }
  return {
    ...headers,
    "X-Request-ID": options.requestId,
  };
}

async function readErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { error?: { code?: string; message?: string } };
    const code = payload.error?.code;
    const message = payload.error?.message;
    if (code && message) {
      return `${code}: ${message}`;
    }
    if (message) {
      return message;
    }
  } catch {
    // keep fallback when non-json error body
  }
  return fallback;
}

export async function getHealth(options?: RequestOptions): Promise<HealthResponse> {
  const response = await fetch("/api/health", {
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
  const response = await fetch(`/api/mail-ingestion/runs?${query.toString()}`, {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Ingestion runs request failed with status ${response.status}`));
  }
  return (await response.json()) as IngestionRunListResponse;
}

export async function getMailAccounts(options?: RequestOptions): Promise<MailAccountListResponse> {
  const response = await fetch("/api/mail-accounts", {
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
  const response = await fetch("/api/mail-accounts", {
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
  const response = await fetch(`/api/mail-accounts/${accountId}`, {
    method: "PATCH",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify(patch),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Patch mail account failed with status ${response.status}`));
  }
  return (await response.json()) as MailAccount;
}

export async function triggerMailSync(
  mailAccountId: number,
  options?: RequestOptions
): Promise<IngestionSyncResponse> {
  const response = await fetch(
    `/api/mail-ingestion/sync?mail_account_id=${encodeURIComponent(String(mailAccountId))}`,
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

export async function getStatements(options?: RequestOptions): Promise<StatementListResponse> {
  const response = await fetch("/api/statements", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Statements request failed with status ${response.status}`));
  }
  return (await response.json()) as StatementListResponse;
}

export async function getParserChanges(
  status: "pending" | "approved" | "rejected" = "pending",
  options?: RequestOptions
): Promise<ParserChangeListResponse> {
  const query = new URLSearchParams({ status });
  const response = await fetch(`/api/parser/changes?${query.toString()}`, {
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
  const response = await fetch(`/api/parser/changes/${changeId}/approve`, {
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
  const response = await fetch("/api/settings/auto-sync", {
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
  const response = await fetch("/api/settings/auto-sync", {
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
  const response = await fetch("/api/settings/llm", {
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) throw new Error(`LLM settings fetch failed: ${response.status}`);
  return (await response.json()) as LlmSettings;
}

export async function patchLlmSettings(
  patch: Partial<{ llm_provider: string; llm_api_url: string; llm_api_key: string; llm_model: string; llm_enabled: boolean; llm_timeout_seconds: number }>,
  options?: RequestOptions
): Promise<LlmSettings> {
  const response = await fetch("/api/settings/llm", {
    method: "PATCH",
    headers: withRequestHeaders({ "Content-Type": "application/json", Accept: "application/json" }, options),
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(await readErrorMessage(response, `LLM settings update failed: ${response.status}`));
  return (await response.json()) as LlmSettings;
}

export async function testLlmConnection(options?: RequestOptions): Promise<{ ok: boolean; model?: string; reply?: string; detail?: string }> {
  const response = await fetch("/api/settings/llm/test", {
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

export type ActivityMailSync = {
  type: "mail_sync";
  id: string;
  run_id: number;
  timestamp: string | null;
  status: "running" | "completed" | "completed_with_errors" | "failed";
  mail_account_id: number | null;
  scanned: number;
  processed: number;
  saved: number;
  failed: number;
  duplicates: number;
  duration_seconds: number | null;
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

export async function getActivityLog(options?: RequestOptions): Promise<ActivityLogResponse> {
  const response = await fetch("/api/activity-log", {
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
  const response = await fetch(`/api/parser/changes/${changeId}/reject`, {
    method: "POST",
    headers: withRequestHeaders({ Accept: "application/json" }, options),
  });
  if (!response.ok) {
    throw new Error(await readErrorMessage(response, `Reject parser change failed with status ${response.status}`));
  }
  return (await response.json()) as { status: string; change_id: number };
}
