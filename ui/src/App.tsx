import { useEffect, useMemo, useState } from "react";

import {
  approveParserChange,
  createMailAccount,
  deleteMailAccount,
  apiUrlPath,
  openOAuthInNewTabOrNavigate,
  getAutoSync,
  getParserChanges,
  getHealth,
  getIngestionRuns,
  getMailAccounts,
  getStatements,
  getIngestionDocuments,
  getIngestionDocumentsStats,
  getLlmSettings,
  patchLlmSettings,
  testLlmConnection,
  reparseStatements,
  KNOWN_BANK_OPTIONS,
  patchStatementBank,
  patchMailAccount,
  rejectParserChange,
  setAutoSync,
  triggerMailSync,
  getActivityLog,
  deleteStatement,
  deleteStatementsBulk,
  resetIngestionData,
  RESET_INGESTION_CONFIRM_PHRASE,
  clearEmailIngestionCache,
  CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE,
  clearLearnedParserRules,
  CLEAR_LEARNED_RULES_CONFIRM_PHRASE,
  type AutoSyncSettings,
  type LlmSettings,
  type HealthResponse,
  type IngestionRunItem,
  type IngestionRunStatus,
  type MailAccount,
  type ParserChangeItem,
  type StatementItem,
  type StatementReminder,
  type IngestionStats,
  type IngestionDocumentItem,
  type ActivityLogResponse,
  type ActivityEvent,
} from "./lib/api";
import {
  buildActivityLogPlainText,
  buildClientLogsPlainText,
  copyTextRobust,
  downloadTextFile,
  formatMailSyncSummaryLine,
} from "./lib/logExport";

type LoadState = "idle" | "loading" | "success" | "error";
type AppTab = "dashboard" | "statements" | "documents" | "search" | "mail" | "settings" | "logs";
type SettingsSubTab = "parser" | "logs" | "auto-sync" | "ai-parser" | "system";
type UiLogLevel = "info" | "error";
type UiLogCategory = "system" | "auth" | "mail" | "parser" | "db";
type UiLogEntry = {
  id: number;
  at: string;
  level: UiLogLevel;
  category: UiLogCategory;
  requestId?: string;
  message: string;
};

const NAV_ITEMS: { id: AppTab; icon: string; label: string }[] = [
  { id: "dashboard", icon: "⊞", label: "Özet" },
  { id: "statements", icon: "▦", label: "Ekstreler" },
  { id: "documents", icon: "📑", label: "Dosyalar" },
  { id: "search", icon: "⌕", label: "Ara" },
  { id: "logs", icon: "◎", label: "Loglar" },
  { id: "mail", icon: "✉", label: "Mail & Sync" },
  { id: "settings", icon: "◈", label: "Ayarlar" },
];

function formatReparseFetchError(e: unknown): string {
  const s = e instanceof Error ? e.message : String(e);
  if (/Load failed|Failed to fetch|NetworkError|aborted/i.test(s)) {
    return (
      "Bağlantı kesildi veya zaman aşımı. Home Assistant tek uzun isteği kesebilir; "
      + "ekstreler artık tek tek işlenir. AI Parser’da «Zaman aşımı (sn)» değerini 180–300 yapıp Kaydet."
    );
  }
  return s;
}

function fmtActivityDate(ts: string | null): string {
  if (!ts) return "";
  return new Date(ts).toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function relActivityAge(ts: string | null): string {
  if (!ts) return "";
  const diff = Math.round((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60) return "az önce";
  if (diff < 3600) return `${Math.floor(diff / 60)} dk önce`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} saat önce`;
  return `${Math.floor(diff / 86400)} gün önce`;
}

/** Statement PDF notice — expired if past end of expires_on (local date). */
function reminderDeadlinePassed(expiresOn: string | null | undefined): boolean {
  if (!expiresOn) return false;
  const end = new Date(`${expiresOn}T23:59:59`);
  return end < new Date();
}

const LOYALTY_REMINDER_RX =
  /(pazarama|maximil|maximiles|maxipuan|bonusflaş|bonus|world\s*puan|worldpuan|chip-?para|paraf\s*para|cardfinans|bankkart\s*lira|sadakat|\bpuan(?:lar)?\b|\bmil(?:ler)?\b)/i;
const LOYALTY_VALUE_CONTEXT_RX = /(kalan|kullan[ıi]labilir|toplam|mevcut|biriken|süresi|sona\s*erm|bakiy)/i;
const SPECIFIC_LOYALTY_PROGRAM_RX =
  /^(pazarama|maximil|maximiles|maxipuan|bonus|worldpuan|chip-para|parafpara|cardfinans|bankkart lira)$/i;

function loyaltyReminders(reminders: StatementReminder[] | undefined): StatementReminder[] {
  if (!reminders?.length) return [];
  return reminders.filter((r) => {
    const hay = `${r.title ?? ""} ${r.text ?? ""}`;
    const programRaw = (r.loyalty_program ?? "").trim();
    const hasSpecificProgram = SPECIFIC_LOYALTY_PROGRAM_RX.test(programRaw);
    const hasRemaining = typeof r.remaining_value_try === "number" && Number.isFinite(r.remaining_value_try) && r.remaining_value_try > 0;
    const hasLoyaltyKeyword = LOYALTY_REMINDER_RX.test(hay);
    const hasValueContext = LOYALTY_VALUE_CONTEXT_RX.test(hay);
    return hasSpecificProgram || hasRemaining || (hasLoyaltyKeyword && hasValueContext);
  });
}

function countActiveReminders(reminders: StatementReminder[] | undefined): number {
  return loyaltyReminders(reminders).filter((r) => !r.expires_on || !reminderDeadlinePassed(r.expires_on)).length;
}

function loyaltyProgramOf(r: StatementReminder): string {
  const fromPayload = (r.loyalty_program || "").trim();
  if (fromPayload) return fromPayload;
  const hay = `${r.title ?? ""} ${r.text ?? ""}`.toLowerCase();
  if (hay.includes("pazarama")) return "Pazarama";
  if (hay.includes("maximil") || hay.includes("maximiles")) return "MaxiMil";
  if (hay.includes("maxipuan")) return "MaxiPuan";
  if (hay.includes("mil")) return "Mil";
  return "Puan";
}

function maskedCardLabel(cardNumber: string | null | undefined): string {
  if (!cardNumber) return "Kart bilinmiyor";
  const digits = cardNumber.replace(/\D/g, "");
  if (digits.length >= 4) return `**** ${digits.slice(-4)}`;
  return cardNumber;
}

function parseTrAmountFromText(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const s = raw.trim().replace(/\s+/g, "");
  if (!s) return null;
  let normalized = s;
  if (normalized.includes(",") && normalized.includes(".")) {
    if (normalized.lastIndexOf(",") > normalized.lastIndexOf(".")) {
      normalized = normalized.replace(/\./g, "").replace(",", ".");
    } else {
      normalized = normalized.replace(/,/g, "");
    }
  } else if (normalized.includes(",")) {
    normalized = normalized.replace(/\./g, "").replace(",", ".");
  } else if (normalized.includes(".") && /^\d{1,3}(\.\d{3})+$/.test(normalized)) {
    normalized = normalized.replace(/\./g, "");
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function fallbackRemainingValueTry(reminder: StatementReminder): number | null {
  const hay = `${reminder.title ?? ""}\n${reminder.text ?? ""}`;
  const low = hay.toLowerCase();
  const headerCue = /(hesap\s+kesim|son\s+ödeme|son\s+odeme|dönem\s+borcu|donem\s+borcu|asgari|hesap\s+özet|hesap\s+ozet)/i;
  const balanceCue =
    /(kalan|kullanmad[ıiğg]?[ıi]n[ıi]z|kullan[ıi]labilir|harcan[ıi]labilir|bakiyeniz|bakiye|kullanım\s+süresi|kullanim\s+suresi|sona\s+erm)/i;
  if (headerCue.test(low) && !balanceCue.test(low)) return null;
  const m1 = hay.match(/(?:kalan|kullanmad[ıiğg]?[ıi]n[ıi]z)\s+([\d\.,]+)\s*TL/i);
  if (m1?.[1]) return parseTrAmountFromText(m1[1]);
  const m2 = hay.match(/([\d\.,]+)\s*TL[^\n]{0,70}(?:Pazarama|MaxiMil(?:es)?|MaxiPuan|puan|mil)/i);
  if (m2?.[1]) return parseTrAmountFromText(m2[1]);
  const m3 = hay.match(/(?:Pazarama|MaxiMil(?:es)?|MaxiPuan|puan|mil)[^\n]{0,70}([\d\.,]+)\s*TL/i);
  if (m3?.[1]) return parseTrAmountFromText(m3[1]);
  const m4 = hay.match(
    /(?:kalan|kullan[ıi]labilir|toplam|mevcut|biriken)[^\n]{0,50}?([\d\.,]+)\s*(?:adet\s*)?(?:Pazarama|MaxiMil(?:es)?|MaxiPuan|Bonus(?:Flaş)?|World\s*Puan|Chip-?Para|Paraf\s*Para|CardFinans|Bankkart\s*Lira|puan|mil)/i,
  );
  if (m4?.[1]) return parseTrAmountFromText(m4[1]);
  // More tolerant multiline matcher for old/mojibake statement rows.
  const m5 = hay.match(
    /([\d][\d\.,]{0,16})\s*(?:TL|TRY)\s*(?:Pazarama|MaxiMil(?:es)?|MaxiPuan|Bonus(?:Flaş)?|World\s*Puan|Chip-?Para|Paraf\s*Para|CardFinans|Bankkart\s*Lira|puan|mil)/i,
  );
  if (m5?.[1]) return parseTrAmountFromText(m5[1]);
  const m6 = hay.match(
    /(?:Pazarama|MaxiMil(?:es)?|MaxiPuan|Bonus(?:Flaş)?|World\s*Puan|Chip-?Para|Paraf\s*Para|CardFinans|Bankkart\s*Lira|puan|mil)[\s\S]{0,120}?([\d][\d\.,]{0,16})\s*(?:TL|TRY)\b/i,
  );
  if (m6?.[1]) return parseTrAmountFromText(m6[1]);
  return null;
}

const NON_CARD_DOC_RX = /(işlem sonuç formu|yatırım|fon alış|fon satış|portföyden|hisse senedi|virman|dekont)/i;

function isLikelyNonCardStatement(stmt: StatementItem): boolean {
  const txText = (stmt.transactions ?? [])
    .slice(0, 6)
    .map((t) => t.description || "")
    .join(" ");
  const hay = `${stmt.email_subject ?? ""} ${txText}`;
  const hasNonCardCue = NON_CARD_DOC_RX.test(hay);
  const weakCardMeta = !stmt.due_date || (stmt.minimum_due_try ?? 0) <= 0;
  return hasNonCardCue && weakCardMeta;
}

/** Ekstre satırı banka açılır listesi: bilinen bankalar + mevcut (ör. yanlış tespit Param) */
function statementBankSelectOptions(current: string | null | undefined): string[] {
  const names = new Set<string>(KNOWN_BANK_OPTIONS);
  if (current) names.add(current);
  return Array.from(names).sort((a, b) => a.localeCompare(b, "tr"));
}

const REMINDER_KIND_LABEL: Record<string, string> = {
  expiry: "Son kullanma",
  legal_warning: "Uyarı",
  contract: "Sözleşme",
  service_change: "Hizmet",
  info: "Bilgi",
};

export function App() {
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [activeTab, setActiveTab] = useState<AppTab>("dashboard");
  const [settingsSubTab, setSettingsSubTab] = useState<SettingsSubTab>("auto-sync");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [latestRuns, setLatestRuns] = useState<IngestionRunItem[]>([]);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [runStatusFilter, setRunStatusFilter] = useState<IngestionRunStatus | "all">("all");
  const [runSortDirection] = useState<"desc" | "asc">("desc");
  const [mailAccounts, setMailAccounts] = useState<MailAccount[]>([]);
  const [selectedMailAccountId, setSelectedMailAccountId] = useState<number | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isCreatingAccount, setIsCreatingAccount] = useState(false);
  const [isDeletingMailAccount, setIsDeletingMailAccount] = useState(false);
  const [syncInfo, setSyncInfo] = useState<string>("");
  const [editingMailboxId, setEditingMailboxId] = useState<number | null>(null);
  const [editMailboxValue, setEditMailboxValue] = useState("");
  const [parserStatusFilter, setParserStatusFilter] = useState<"pending" | "approved" | "rejected">("pending");
  const [parserChanges, setParserChanges] = useState<ParserChangeItem[]>([]);
  const [isLoadingParser, setIsLoadingParser] = useState(false);
  const [activeParserActionId, setActiveParserActionId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [uiLogs, setUiLogs] = useState<UiLogEntry[]>([]);
  const [logLevelFilter, setLogLevelFilter] = useState<"all" | UiLogLevel>("all");
  const [logCategoryFilter, setLogCategoryFilter] = useState<"all" | UiLogCategory>("all");
  const [logSearch, setLogSearch] = useState("");
  const [formProvider, setFormProvider] = useState<"gmail" | "outlook" | "custom">("gmail");
  const [formAuthMode, setFormAuthMode] = useState<"password" | "oauth_gmail">("password");
  const [formLabel, setFormLabel] = useState("Primary Gmail");

  const gmailOAuthUrl = useMemo(
    () =>
      `${apiUrlPath("api/oauth/gmail/start")}?label=${encodeURIComponent(formLabel || "Gmail Hesabı")}`,
    [formLabel]
  );
  const [formImapUser, setFormImapUser] = useState("");
  const [formImapPassword, setFormImapPassword] = useState("");
  const [formRefreshToken, setFormRefreshToken] = useState("");
  const [formMailbox, setFormMailbox] = useState("INBOX");
  const [formImapHost, setFormImapHost] = useState("");
  /** Gmail'de Mail.app gibi önce OAuth; bunu açınca IMAP + uygulama şifresi formu görünür. */
  const [gmailImapManual, setGmailImapManual] = useState(false);
  const [statements, setStatements] = useState<StatementItem[]>([]);
  const [ingestionStats, setIngestionStats] = useState<IngestionStats | null>(null);
  const [ingestionDocs, setIngestionDocs] = useState<IngestionDocumentItem[]>([]);
  const [ingestionDocFilter, setIngestionDocFilter] = useState<string>("all");
  const [ingestionRefreshTick, setIngestionRefreshTick] = useState(0);
  const [expandedStatementId, setExpandedStatementId] = useState<number | null>(null);
  const [stmtSearch, setStmtSearch] = useState("");
  const [stmtBankFilter, setStmtBankFilter] = useState("all");
  const [txSearch, setTxSearch] = useState<Record<number, string>>({});
  const [autoSync, setAutoSyncState] = useState<AutoSyncSettings | null>(null);
  const [isSavingAutoSync, setIsSavingAutoSync] = useState(false);
  const [llmSettings, setLlmSettings] = useState<LlmSettings | null>(null);
  const [llmForm, setLlmForm] = useState<{ provider: string; api_url: string; api_key: string; model: string; timeout: number; enabled: boolean; min_tx_threshold: number } | null>(null);
  const [llmTestResult, setLlmTestResult] = useState<{ ok: boolean; reply?: string; detail?: string } | null>(null);
  const [isSavingLlm, setIsSavingLlm] = useState(false);
  const [isTestingLlm, setIsTestingLlm] = useState(false);
  const [isReparsingStatements, setIsReparsingStatements] = useState(false);
  const [reparseStmtId, setReparseStmtId] = useState<number | null>(null);
  const [bankPatchingId, setBankPatchingId] = useState<number | null>(null);
  const [reparseSummary, setReparseSummary] = useState<string | null>(null);
  const [systemResetOpen, setSystemResetOpen] = useState(false);
  const [systemResetInput, setSystemResetInput] = useState("");
  const [isResettingSystem, setIsResettingSystem] = useState(false);
  const [clearLearnedOpen, setClearLearnedOpen] = useState(false);
  const [clearLearnedInput, setClearLearnedInput] = useState("");
  const [isClearingLearned, setIsClearingLearned] = useState(false);
  const [clearEmailOpen, setClearEmailOpen] = useState(false);
  const [clearEmailInput, setClearEmailInput] = useState("");
  const [isClearingEmail, setIsClearingEmail] = useState(false);
  const [globalSearch, setGlobalSearch] = useState("");
  const [feeMode, setFeeMode] = useState(false);
  const [activityLog, setActivityLog] = useState<ActivityLogResponse | null>(null);
  const [activityLogError, setActivityLogError] = useState<string | null>(null);
  const [activityFilter, setActivityFilter] = useState<"all" | "mail_sync" | "document_parse">("all");
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);
  const [activityRefreshTick, setActivityRefreshTick] = useState(0);
  /** Loglar sekmesi: kart / tablo / düz metin */
  const [activityViewMode, setActivityViewMode] = useState<"cards" | "table" | "text">("table");
  const [selectedStmtIds, setSelectedStmtIds] = useState<Set<number>>(new Set());
  const [isDeletingStmts, setIsDeletingStmts] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<{ ids: number[]; label: string } | null>(null);

  /** Gmail + manuel IMAP: OAuth yoksa şifre; Outlook/Özel: formAuthMode. */
  const resolvedMailAuthMode = useMemo<"password" | "oauth_gmail">(() => {
    if (formProvider !== "gmail") return formAuthMode;
    if (!gmailImapManual) return "password";
    return !health?.gmail_oauth_configured ? "password" : formAuthMode;
  }, [formProvider, gmailImapManual, health?.gmail_oauth_configured, formAuthMode]);

  function nextRequestId(prefix: string): string {
    return `${prefix}-${Date.now()}-${Math.floor(Math.random() * 10000)}`;
  }

  function pushLog(level: UiLogLevel, category: UiLogCategory, message: string, requestId?: string) {
    setUiLogs((prev) =>
      [
        { id: Date.now() + Math.floor(Math.random() * 1000), at: new Date().toISOString(), level, category, requestId, message },
        ...prev,
      ].slice(0, 200)
    );
  }

  async function reloadCoreData() {
    const requestId = nextRequestId("reload");
    setLoadState("loading");
    pushLog("info", "system", "Yenileniyor...", requestId);
    try {
      const [data, runs, accounts, stmts, ingSt] = await Promise.all([
        getHealth({ requestId }),
        getIngestionRuns(10, undefined, runStatusFilter, { requestId }),
        getMailAccounts({ requestId }),
        getStatements({ requestId }),
        getIngestionDocumentsStats({ requestId }),
      ]);
      setHealth(data);
      setLatestRuns(runs.items);
      setNextCursor(runs.next_cursor);
      setMailAccounts(accounts.items);
      setSelectedMailAccountId(accounts.items[0]?.id ?? null);
      setStatements(stmts.items);
      setIngestionStats(ingSt.stats);
      setIngestionRefreshTick((x) => x + 1);
      setLoadState("success");
      setErrorMessage("");
      pushLog("info", "system", "Veriler güncellendi", requestId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setErrorMessage(message);
      setLoadState("error");
      pushLog("error", "system", `Yenileme başarısız: ${message}`, requestId);
    }
  }

  useEffect(() => {
    if (activeTab !== "documents") return;
    let cancelled = false;
    (async () => {
      try {
        const r = await getIngestionDocuments(ingestionDocFilter, 200);
        if (!cancelled) {
          setIngestionDocs(r.items);
          setIngestionStats(r.stats);
        }
      } catch (e) {
        if (!cancelled) {
          pushLog("error", "system", e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeTab, ingestionDocFilter, ingestionRefreshTick]);

  async function confirmDeleteStatements(ids: number[], label: string) {
    setDeleteConfirm({ ids, label });
  }

  async function executeDeleteStatements() {
    if (!deleteConfirm) return;
    setIsDeletingStmts(true);
    const { ids } = deleteConfirm;
    setDeleteConfirm(null);
    try {
      if (ids.length === 1) {
        await deleteStatement(ids[0]);
      } else {
        await deleteStatementsBulk(ids);
      }
      setStatements((prev) => prev.filter((s) => !ids.includes(s.id)));
      setSelectedStmtIds(new Set());
      pushLog("info", "parser", `${ids.length} ekstre silindi.`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Silme başarısız";
      setErrorMessage(msg);
      pushLog("error", "parser", msg);
    } finally {
      setIsDeletingStmts(false);
    }
  }

  const llmReadyForReparse =
    !!llmSettings?.llm_enabled && (llmSettings.llm_api_url || "").trim().length > 0;

  async function handleReparseStatement(stmt: Pick<StatementItem, "id" | "doc_type">) {
    if (isReparsingStatements || reparseStmtId !== null) {
      setSyncInfo("Yeniden çözme zaten çalışıyor, lütfen bitmesini bekleyin.");
      return;
    }
    if (stmt.doc_type !== "pdf") {
      setSyncInfo("Yeniden çöz: sadece PDF ekstreler desteklenir.");
      pushLog("info", "parser", `doc #${stmt.id} CSV/görsel — atlandı`);
      return;
    }
    if (!llmReadyForReparse) {
      setErrorMessage("AI Parser kapalı veya API URL boş. Ayarlar → AI Parser.");
      setActiveTab("settings");
      setSettingsSubTab("ai-parser");
      return;
    }
    setIsReparsingStatements(true);
    setReparseStmtId(stmt.id);
    setErrorMessage("");
    try {
      const r = await reparseStatements("selected", [stmt.id]);
      const row = r.results?.find((x) => x.doc_id === stmt.id) ?? r.results?.[0];
      if (row?.ok) {
        const n = row.transaction_count ?? 0;
        setSyncInfo(`Ekstre yeniden parse edildi (${n} işlem).`);
        pushLog("info", "parser", `reparse ok doc #${stmt.id} tx=${n}`);
        await reloadCoreData();
      } else {
        const raw = row?.error ?? r.message ?? "Bilinmeyen hata";
        const err =
          raw === "pdf_not_found_in_imap"
            ? "PDF postada bulunamadı (mesaj silinmiş / yanlış klasör)."
            : raw === "email_or_account_missing"
              ? "Bu ekstre için mail hesabı veya mesaj bağlantısı yok."
              : raw === "non_credit_card_document"
                ? "Bu dosya kredi kartı ekstresi değil (ekstre listesine alınmadı)."
              : raw.startsWith("pdf_extract_failed:")
                ? "PDF okunamadı."
                : raw;
        pushLog("error", "parser", `reparse doc #${stmt.id}: ${raw}`);
        await reloadCoreData();
        setErrorMessage(`Yeniden çöz: ${err}`);
      }
    } catch (e) {
      setErrorMessage(formatReparseFetchError(e));
      pushLog("error", "parser", formatReparseFetchError(e));
    } finally {
      setReparseStmtId(null);
      setIsReparsingStatements(false);
    }
  }

  async function handleReparseSelectedStatements() {
    const pdfIds = Array.from(selectedStmtIds).filter((id) => {
      const s = statements.find((x) => x.id === id);
      return s?.doc_type === "pdf";
    });
    if (pdfIds.length === 0) {
      setSyncInfo("Seçilenlerde PDF ekstre yok.");
      return;
    }
    if (!llmReadyForReparse) {
      setErrorMessage("AI Parser kapalı veya API URL boş. Ayarlar → AI Parser.");
      setActiveTab("settings");
      setSettingsSubTab("ai-parser");
      return;
    }
    if (
      !window.confirm(
        `${pdfIds.length} PDF ekstre mailden tekrar alınıp yeniden çözülecek. Devam?`,
      )
    ) {
      return;
    }
    setIsReparsingStatements(true);
    setErrorMessage("");
    try {
      let ok = 0;
      let fail = 0;
      for (let i = 0; i < pdfIds.length; i++) {
        const id = pdfIds[i];
        setReparseStmtId(id);
        try {
          const r = await reparseStatements("selected", [id]);
          const row = r.results?.find((x) => x.doc_id === id) ?? r.results?.[0];
          if (row?.ok) ok += 1;
          else fail += 1;
        } catch {
          fail += 1;
        }
      }
      setSyncInfo(`Yeniden çöz bitti: ${ok} başarılı, ${fail} sorunlu / ${pdfIds.length} ekstre.`);
      pushLog("info", "parser", `bulk reparse ${ok}/${pdfIds.length}`);
      setSelectedStmtIds(new Set());
      await reloadCoreData();
    } catch (e) {
      setErrorMessage(formatReparseFetchError(e));
    } finally {
      setReparseStmtId(null);
      setIsReparsingStatements(false);
    }
  }

  async function executeSystemReset() {
    if (systemResetInput !== RESET_INGESTION_CONFIRM_PHRASE) return;
    setIsResettingSystem(true);
    setErrorMessage("");
    try {
      const r = await resetIngestionData(systemResetInput);
      const d = r.deleted;
      setSystemResetOpen(false);
      setSystemResetInput("");
      setSelectedStmtIds(new Set());
      setExpandedStatementId(null);
      setSyncInfo(
        `Sıfırlama tamam. Silinen: ekstre ${d.statement_documents ?? 0}, mail kaydı ${d.emails_ingested ?? 0}, sync çalışması ${d.mail_ingestion_runs ?? 0}. Mail & Sync ile yeniden indirebilirsin.`,
      );
      pushLog("info", "system", "Sistem verisi sıfırlandı (ingestion)");
      await reloadCoreData();
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : String(e));
      pushLog("error", "system", e instanceof Error ? e.message : String(e));
    } finally {
      setIsResettingSystem(false);
    }
  }

  async function executeClearLearnedRules() {
    if (clearLearnedInput !== CLEAR_LEARNED_RULES_CONFIRM_PHRASE) return;
    setIsClearingLearned(true);
    setErrorMessage("");
    try {
      const r = await clearLearnedParserRules(clearLearnedInput);
      setClearLearnedOpen(false);
      setClearLearnedInput("");
      setSyncInfo(
        `Öğrenilmiş parser kuralları silindi (${r.deleted_learned_parser_rules} satır). `
        + "Ekstreleri LLM ile yeniden denemek için AI Parser → «Boş/hatalı…» veya Ekstreler’de «Yeniden çöz».",
      );
      pushLog("info", "parser", `learned rules cleared n=${r.deleted_learned_parser_rules}`);
      await reloadCoreData();
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setIsClearingLearned(false);
    }
  }

  async function executeClearEmailIngestionCache() {
    if (clearEmailInput !== CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE) return;
    setIsClearingEmail(true);
    setErrorMessage("");
    try {
      const r = await clearEmailIngestionCache(clearEmailInput);
      const d = r.deleted;
      setClearEmailOpen(false);
      setClearEmailInput("");
      setSelectedStmtIds(new Set());
      setExpandedStatementId(null);
      setSyncInfo(
        `Posta işleme önbelleği temizlendi. Silinen: ekstre ${d.statement_documents ?? 0}, mail kaydı ${d.emails_ingested ?? 0}, sync çalışması ${d.mail_ingestion_runs ?? 0}. `
        + "Şimdi «Mail ile senkronize et» ile aynı kutudaki mailler yeniden indirilebilir. (Öğrenilmiş kurallar korunur.)",
      );
      pushLog("info", "mail", "email ingestion cache cleared");
      await reloadCoreData();
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setIsClearingEmail(false);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthResult = params.get("oauth");
    if (!oauthResult) return;
    if (oauthResult === "success") {
      const id = params.get("account_id");
      setSyncInfo(`Gmail hesabı eklendi! #${id}`);
      pushLog("info", "mail", `Gmail OAuth tamamlandı, hesap #${id} oluşturuldu`);
      setActiveTab("mail");
    } else if (oauthResult === "not_configured") {
      setErrorMessage(
        "Bu sunucuda Gmail tarayıcı girişi (OAuth) henüz ayarlanmamış. Aşağıda “uygulama şifresi ile elle ekle”yi açıp IMAP ile ekleyebilirsin; kalıcı çözüm için add-on’da OAuth + isteğe bağlı proxy tanımlanmalı."
      );
      setGmailImapManual(true);
      setActiveTab("mail");
      pushLog("info", "auth", "Gmail OAuth yapılandırılmamış; manuel IMAP açıldı.");
    } else {
      const reason = params.get("reason") ?? "bilinmeyen hata";
      setErrorMessage(`Gmail OAuth hatası: ${reason}`);
      pushLog("error", "auth", `Gmail OAuth başarısız: ${reason}`);
    }
    window.history.replaceState({}, "", window.location.pathname);
  }, []);

  useEffect(() => {
    let mounted = true;
    async function run() {
      const requestId = nextRequestId("init");
      setLoadState("loading");
      pushLog("info", "system", "Başlatılıyor...", requestId);
      try {
        const [data, runs, accounts, stmts, autoSyncData, llmData] = await Promise.all([
          getHealth({ requestId }),
          getIngestionRuns(10, undefined, "all", { requestId }),
          getMailAccounts({ requestId }),
          getStatements({ requestId }),
          getAutoSync({ requestId }),
          getLlmSettings({ requestId }),
        ]);
        if (!mounted) return;
        setHealth(data);
        setLatestRuns(runs.items);
        setNextCursor(runs.next_cursor);
        setMailAccounts(accounts.items);
        setSelectedMailAccountId(accounts.items[0]?.id ?? null);
        setStatements(stmts.items);
        setAutoSyncState(autoSyncData);
        setLlmSettings(llmData);
        setLlmForm({
          provider: llmData.llm_provider,
          api_url: llmData.llm_api_url,
          api_key: "",
          model: llmData.llm_model,
          timeout: llmData.llm_timeout_seconds,
          enabled: llmData.llm_enabled,
          min_tx_threshold: llmData.llm_min_tx_threshold ?? 0,
        });
        setLoadState("success");
        setErrorMessage("");
        pushLog("info", "system", "Hazır", requestId);
      } catch (error) {
        if (!mounted) return;
        const message = error instanceof Error ? error.message : "Unknown error";
        setErrorMessage(message);
        pushLog("error", "system", `Başlatma hatası: ${message}`, requestId);
        setLoadState("error");
      }
    }
    run();
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    let mounted = true;
    async function run() {
      const requestId = nextRequestId("runs-filter");
      try {
        const runs = await getIngestionRuns(10, undefined, runStatusFilter, { requestId });
        if (!mounted) return;
        setLatestRuns(runs.items);
        setNextCursor(runs.next_cursor);
      } catch {
        pushLog("error", "mail", "Run listesi güncellenemedi", requestId);
      }
    }
    run();
    return () => { mounted = false; };
  }, [runStatusFilter]);

  // Load activity log when logs tab is active, and auto-refresh every 30s
  useEffect(() => {
    if (activeTab !== "logs") return;
    let mounted = true;
    async function loadActivity() {
      setIsLoadingActivity(true);
      try {
        const data = await getActivityLog();
        if (!mounted) return;
        setActivityLog(data);
        setActivityLogError(null);
      } catch (e) {
        if (!mounted) return;
        setActivityLogError(e instanceof Error ? e.message : "Aktivite günlüğü alınamadı");
      } finally {
        if (mounted) setIsLoadingActivity(false);
      }
    }
    loadActivity();
    const timer = setInterval(loadActivity, 30_000);
    return () => { mounted = false; clearInterval(timer); };
  }, [activeTab, activityRefreshTick]);

  async function loadMoreRuns() {
    if (!nextCursor || isLoadingMore) return;
    setIsLoadingMore(true);
    const requestId = nextRequestId("runs-more");
    try {
      const nextPage = await getIngestionRuns(10, nextCursor, runStatusFilter, { requestId });
      setLatestRuns((prev) => [...prev, ...nextPage.items]);
      setNextCursor(nextPage.next_cursor);
    } catch {
      // keep existing
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function refreshRuns() {
    const [runs, stmts] = await Promise.all([
      getIngestionRuns(10, undefined, runStatusFilter, { requestId: nextRequestId("runs-refresh") }),
      getStatements({ requestId: nextRequestId("stmts-refresh") }),
    ]);
    setLatestRuns(runs.items);
    setNextCursor(runs.next_cursor);
    setStatements(stmts.items);
  }

  async function handleCreateMailAccount() {
    if (formProvider === "gmail" && !gmailImapManual) {
      setErrorMessage("Gmail için önce “Gmail’e bağlan (tarayıcıda aç)” kullan veya “uygulama şifresi ile elle ekle”yi aç.");
      return;
    }
    setIsCreatingAccount(true);
    const requestId = nextRequestId("mail-create");
    pushLog("info", "mail", "Mail hesabı oluşturuluyor...", requestId);
    try {
      const authMode = resolvedMailAuthMode;
      const created = await createMailAccount(
        {
          provider: formProvider,
          auth_mode: authMode,
          account_label: formLabel.trim() || formLabel,
          imap_host:
            formProvider === "gmail"
              ? "imap.gmail.com"
              : formProvider === "outlook"
              ? "outlook.office365.com"
              : formImapHost.trim(),
          imap_port: 993,
          imap_user: formImapUser.trim(),
          imap_password: authMode === "password" ? formImapPassword.trim().replace(/\s/g, "") : "",
          oauth_refresh_token: authMode === "oauth_gmail" ? formRefreshToken : null,
          mailbox: formMailbox,
          unseen_only: true,
          fetch_limit: 20,
          retry_count: 3,
          retry_backoff_seconds: 1.5,
          is_active: true,
        },
        { requestId }
      );
      setMailAccounts((prev) => [created, ...prev]);
      setSelectedMailAccountId(created.id);
      setSyncInfo(`Mail hesabı oluşturuldu: #${created.id}`);
      setErrorMessage("");
      pushLog("info", "mail", `Mail hesabı oluşturuldu: #${created.id}`, requestId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Oluşturma başarısız";
      setErrorMessage(message);
      pushLog("error", "mail", `Mail hesabı oluşturma başarısız: ${message}`, requestId);
    } finally {
      setIsCreatingAccount(false);
    }
  }

  async function handleDeleteMailAccount(accountId: number, label: string) {
    if (
      !window.confirm(
        `"${label}" (#${accountId}) hesabını silmek istediğinize emin misiniz? Bu işlem geri alınamaz.`
      )
    ) {
      return;
    }
    setIsDeletingMailAccount(true);
    const requestId = nextRequestId("mail-delete");
    try {
      await deleteMailAccount(accountId, { requestId });
      const remaining = mailAccounts.filter((a) => a.id !== accountId);
      setMailAccounts(remaining);
      if (selectedMailAccountId === accountId) {
        setSelectedMailAccountId(remaining[0]?.id ?? null);
      }
      setSyncInfo(`Mail hesabı silindi: #${accountId}`);
      setErrorMessage("");
      pushLog("info", "mail", `Mail hesabı silindi: #${accountId}`, requestId);
    } catch (e) {
      setErrorMessage(e instanceof Error ? e.message : "Silme başarısız");
    } finally {
      setIsDeletingMailAccount(false);
    }
  }

  async function handleSyncSelectedAccount() {
    if (!selectedMailAccountId || isSyncing) return;
    setIsSyncing(true);
    const requestId = nextRequestId("mail-sync");
    pushLog("info", "mail", `Sync başlatılıyor (hesap #${selectedMailAccountId})`, requestId);
    try {
      const result = await triggerMailSync(selectedMailAccountId, { requestId });
      await refreshRuns();
      setSyncInfo(`Sync tamamlandı — Run #${result.summary.run_id}`);
      setErrorMessage("");
      pushLog("info", "mail", `Sync tamamlandı. Run #${result.summary.run_id}`, requestId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Sync başarısız";
      setErrorMessage(message);
      pushLog("error", "mail", `Sync başarısız: ${message}`, requestId);
    } finally {
      setIsSyncing(false);
    }
  }

  async function loadParserChanges(status: "pending" | "approved" | "rejected") {
    setIsLoadingParser(true);
    const requestId = nextRequestId("parser-list");
    try {
      const response = await getParserChanges(status, { requestId });
      setParserChanges(response.items);
      setErrorMessage("");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Yükleme başarısız";
      setErrorMessage(message);
      pushLog("error", "parser", `Parser değişiklikleri yüklenemedi: ${message}`, requestId);
    } finally {
      setIsLoadingParser(false);
    }
  }

  useEffect(() => {
    if (activeTab !== "settings" || settingsSubTab !== "parser") return;
    loadParserChanges(parserStatusFilter);
  }, [parserStatusFilter, activeTab, settingsSubTab]);

  async function handleParserDecision(changeId: number, action: "approve" | "reject") {
    setActiveParserActionId(changeId);
    const requestId = nextRequestId("parser-action");
    try {
      if (action === "approve") {
        await approveParserChange(changeId, { requestId });
      } else {
        await rejectParserChange(changeId, { requestId });
      }
      await loadParserChanges(parserStatusFilter);
      setErrorMessage("");
      pushLog("info", "parser", `Parser değişikliği ${action === "approve" ? "onaylandı" : "reddedildi"}: #${changeId}`, requestId);
    } catch (error) {
      const message = error instanceof Error ? error.message : "İşlem başarısız";
      setErrorMessage(message);
      pushLog("error", "parser", `Parser işlemi başarısız (#${changeId}): ${message}`, requestId);
    } finally {
      setActiveParserActionId(null);
    }
  }

  function statusBadge(status: IngestionRunItem["status"]) {
    switch (status) {
      case "completed": return "badge badgeOk";
      case "completed_with_errors": return "badge badgeWarn";
      case "failed": return "badge badgeErr";
      default: return "badge badgeMuted";
    }
  }

  const statusLabel = useMemo(() => {
    if (loadState === "loading") return "Yükleniyor";
    if (loadState === "error") return "Bağlantı sorunu";
    if (loadState === "success") return "Sistem hazır";
    return "Bekleniyor";
  }, [loadState]);

  const visibleRuns = useMemo(() => {
    const copied = [...latestRuns];
    copied.sort((a, b) => (runSortDirection === "desc" ? b.id - a.id : a.id - b.id));
    return copied;
  }, [latestRuns, runSortDirection]);

  const visibleLogs = useMemo(() => {
    const term = logSearch.trim().toLowerCase();
    return uiLogs.filter((entry) => {
      if (logLevelFilter !== "all" && entry.level !== logLevelFilter) return false;
      if (logCategoryFilter !== "all" && entry.category !== logCategoryFilter) return false;
      if (!term) return true;
      return (
        entry.message.toLowerCase().includes(term) ||
        entry.at.toLowerCase().includes(term) ||
        entry.category.toLowerCase().includes(term)
      );
    });
  }, [uiLogs, logLevelFilter, logCategoryFilter, logSearch]);

  const filteredActivityEvents = useMemo(() => {
    if (!activityLog) return [];
    return activityLog.activities.filter(
      (a) => activityFilter === "all" || a.type === activityFilter,
    );
  }, [activityLog, activityFilter]);

  const bankNames = useMemo(() => {
    return Array.from(new Set(statements.map((s) => s.bank_name).filter(Boolean) as string[])).sort();
  }, [statements]);

  const visibleStatements = useMemo(() => {
    return statements.filter((s) => {
      if (stmtBankFilter !== "all" && s.bank_name !== stmtBankFilter) return false;
      if (stmtSearch) {
        const q = trLower(stmtSearch);
        return (
          trLower(s.bank_name ?? "").includes(q) ||
          trLower(s.file_name ?? "").includes(q) ||
          s.period_start?.includes(q) ||
          s.period_end?.includes(q) ||
          s.due_date?.includes(q) ||
          s.transactions.some((tx) => trLower(tx.description ?? "").includes(q))
        );
      }
      return true;
    });
  }, [statements, stmtSearch, stmtBankFilter]);

  // When stmtSearch matches transactions, count matching tx per statement
  const stmtMatchingTxCount = useMemo(() => {
    if (!stmtSearch) return {} as Record<number, number>;
    const q = trLower(stmtSearch);
    const map: Record<number, number> = {};
    for (const s of visibleStatements) {
      const count = s.transactions.filter((tx) => trLower(tx.description ?? "").includes(q)).length;
      if (count > 0) map[s.id] = count;
    }
    return map;
  }, [stmtSearch, visibleStatements]);

  // A statement is considered paid if its due_date is in the past
  function isPaid(s: { due_date: string | null }): boolean {
    if (!s.due_date) return false;
    return new Date(s.due_date) < new Date(new Date().toDateString()); // compare date-only
  }

  // Turkish-aware lowercase — I(U+0049)→ı, İ(U+0130)→i
  const trLower = (s: string) =>
    s
      .replace(/İ/g, "i")
      .replace(/I/g, "ı")
      .toLowerCase();

  // Fee detection — keywords covering all Turkish bank statement fee types
  const INSURANCE_KEYWORDS = [
    "sigorta",
    "ferdi kaza",
    "hayat sigorta",
    "emeklilik",
    "metlife",
    "viennalife",
    "anadolu hayat",
    "sompo",
    "ray sigorta",
    "turkiye sigorta",
    "türkiye sigorta",
    "allianz",
    "axa",
    "groupama",
    "ergo",
  ];

  const FEE_KEYWORDS = [
    // ── Aidat / Yıllık ücret ──────────────────────────────────────────────────
    "aidat",
    "yıllık ücret", "yillik ucret",
    "yıllık kart",  "yillik kart",
    "yıllık üyelik","yillik uyelik",
    "kart ücreti",  "kart ucreti",
    "kart yenileme",
    // ── Faiz ─────────────────────────────────────────────────────────────────
    "faiz",            // dönem faizi, satış faizi, taksit bakiyesi faizi, nakit avans faizi…
    // ── BSMV / KKDF (vergi ve fon) ───────────────────────────────────────────
    "bsmv",            // Banka ve Sigorta Muameleleri Vergisi
    "kkdf",            // Kaynak Kullanımı Destekleme Fonu
    // ── Gecikme ──────────────────────────────────────────────────────────────
    "gecikme",
    // ── Komisyon / Masraf ────────────────────────────────────────────────────
    "komisyon",
    "masraf",
    "işlem ücreti", "islem ucreti",
    // ── Nakit Avans ──────────────────────────────────────────────────────────
    "nakit avans",     // nakit avans ücreti (with spaces)
    "nakitavans",      // DenizBank/Yapı Kredi — no-space format: NAKİTAVANSÜCRETİ
    // ── SMS / Bildirim ────────────────────────────────────────────────────────
    "sms",
    "bildirim ücreti", "bildirim ucreti",
    // ── Ek kart ──────────────────────────────────────────────────────────────
    "ek kart",
    // ── Yurt dışı / kur farkı ────────────────────────────────────────────────
    "yurt dışı", "yurt disi",
    "kur farkı",  "kur farki",
    // ── Limit / Ekstre ───────────────────────────────────────────────────────
    "limit aşım", "limit asim",
    "ekstre basım", "ekstre basim",
  ];

  // Use Turkish-aware lowercase so İ/I are handled correctly
  function isInsurancePayment(description: string): boolean {
    const d = trLower(description);
    return INSURANCE_KEYWORDS.some((kw) => d.includes(trLower(kw)));
  }

  function isFee(description: string): boolean {
    if (isInsurancePayment(description)) return false;
    const d = trLower(description);
    return FEE_KEYWORDS.some((kw) => d.includes(trLower(kw)));
  }

  /**
   * Returns a human-readable explanation for BSMV/KKDF/compound-interest lines
   * so the user knows which original fee this tax/fund belongs to.
   *
   * Examples:
   *   "KREDİ KARTI YILLIK ÜCRETİ BSMV'Sİ"  → "KREDİ KARTI YILLIK ÜCRETİ üzerinden %5 BSMV vergisi"
   *   "Faiz BSMV"                            → "Faiz üzerinden %5 BSMV vergisi"
   *   "KKDF"                                 → "Faiz/Avans üzerinden Kaynak Kullanımı Destekleme Fonu"
   *   "FAİZ TUTARI FIZ:75.00 VR/FN:22.50"   → "Faiz: 75,00 TL + Vergi/Fon: 22,50 TL"
   */
  function getFeeNote(description: string): string | null {
    const d = description.trim();

    // Pattern: "{PARENT} BSMV'Sİ" / "{PARENT} BSMV'si"
    const bsmvParentMatch = d.match(/^(.+?)\s+BSMV'[Ss][İiIı]$/i);
    if (bsmvParentMatch) {
      const parent = bsmvParentMatch[1].trim();
      if (trLower(parent) !== "faiz") {
        return `"${parent}" üzerinden %5 BSMV vergisi`;
      }
      return "Faiz üzerinden %5 BSMV vergisi";
    }

    // Standalone "Faiz BSMV"
    if (/^faiz\s+bsmv$/i.test(trLower(d))) {
      return "Faiz üzerinden %5 BSMV vergisi";
    }

    // Standalone "KKDF"
    if (/^kkdf$/i.test(d.trim())) {
      return "Faiz/Avans üzerinden Kaynak Kullanımı Destekleme Fonu (%15)";
    }

    // İş Bankası compound format: "FAİZ TUTARI FIZ:75.00 VR/FN:22.50"
    //                          or  "FAIZTUTARIFZ:779.17VR/FN:233.76"
    const faizTutariMatch = d.match(
      /FA[İI]?Z\s*TUTARI?\s*F[İI]?Z?:?\s*([\d.,]+)\s*V[Rr]?\/?F[Nn]?:?\s*([\d.,]+)/i
    );
    if (faizTutariMatch) {
      const faiz = parseFloat(faizTutariMatch[1].replace(",", "."));
      const vfon = parseFloat(faizTutariMatch[2].replace(",", "."));
      return (
        `Faiz: ${faiz.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL` +
        ` + Vergi/Fon (KKDF+BSMV): ${vfon.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL`
      );
    }

    return null;
  }

  // ── Transaction category system (Garanti BBVA categories as reference) ───────
  type TxCat = { name: string; icon: string; color: string };

  const TX_CATEGORIES: (TxCat & { keywords: string[] })[] = [
    // ── Banka ücretleri (öncelikli) ──────────────────────────────────────────
    { name: "Faiz / Komisyon",    icon: "📈", color: "#f87171",
      keywords: ["faiz", "kkdf", "bsmv", "gecikme faiz"] },
    { name: "Aidat Ödemesi",      icon: "💳", color: "#fbbf24",
      keywords: ["aidat", "yıllık ücret", "yillik ucret", "yıllik kart", "yillik kart", "kart ücreti", "kart ucreti", "yıllık üyelik"] },
    { name: "Nakit Avans",        icon: "💵", color: "#fbbf24",
      keywords: ["nakit avans", "nakitavans"] },
    // ── Sigorta / Emeklilik ──────────────────────────────────────────────────
    { name: "Emeklilik/Sigorta",  icon: "🛡", color: "#a78bfa",
      keywords: INSURANCE_KEYWORDS },
    // ── Ödemeler ─────────────────────────────────────────────────────────────
    { name: "Vergi",              icon: "🏛", color: "#94a3b8",
      keywords: ["vergi daire", "vergi dai", "gelir idaresi"] },
    { name: "Kart Ödemesi",       icon: "💰", color: "#34d399",
      keywords: ["hesaptan ödeme", "hesaptan odeme", "otomatik ödeme", "otomatik odeme", "kart ödemesi"] },
    { name: "Kurum Ödemesi",      icon: "🏢", color: "#94a3b8",
      keywords: ["sgk", "elektrik fatura", "doğalgaz", "dogalgaz", "su fatura", "belediye"] },
    { name: "Para Transferi",     icon: "↔", color: "#64748b",
      keywords: ["karttan aktarım", "karttan aktarim", "karttan karta", "eft", "havale"] },
    { name: "Kart Tutar Aktarım", icon: "🔄", color: "#64748b",
      keywords: ["karttan aktarim 5306", "hesaptan aktarım", "hesaptan aktarim", "kart aktarım"] },
    // ── Alışveriş ────────────────────────────────────────────────────────────
    { name: "Market",             icon: "🛒", color: "#4ade80",
      keywords: ["market", "a-101", "a101", "migros", "carrefour", "bim ", "şok ", "gratis"] },
    { name: "Akaryakıt",          icon: "⛽", color: "#f97316",
      keywords: ["akaryakıt", "akaryakit", "opet", "petrol ", "benzin", "yakıt", "yakit", "total "] },
    { name: "Yeme / İçme",        icon: "🍽", color: "#f59e0b",
      keywords: ["restoran", "restaurant", "cafe", "caffe", "kahve", "döner", "pizza", "burger", "çorba", "pide", "balık", "balik", "baliq", "fırın", "firin", "pastane", "profiterol", "büfe", "lokanta", "kebap", "etçi", "etci", "yeme", "yemek", "food"] },
    { name: "Sağlık / Bakım",     icon: "🏥", color: "#2dd4bf",
      keywords: ["hastane", "sağlık", "saglik", "klinik", "eczane", "diş ", "dis klinik", "optik", "güzellik", "guzellik", "kuaför", "kuafor", "berber", "bakım", "bakim"] },
    { name: "Eğitim",             icon: "🎓", color: "#a78bfa",
      keywords: ["okul", "üniversite", "universite", "eğitim", "egitim", "akademi", "kurs ", "final okul"] },
    { name: "Giyim / Aksesuar",   icon: "👗", color: "#ec4899",
      keywords: ["giyim", "tekstil", "hazır giyim", "hazir giyim", "zara", "h&m", "lcw", "bershka", "mango ", "fashion", "aksesuar"] },
    { name: "Elektronik",         icon: "📱", color: "#60a5fa",
      keywords: ["elektronik", "mediamarkt", "vatan bilgisayar", "dyson", "laptop", "bilgisayar", "phone", "apple.", "apple.com"] },
    { name: "E-ticaret",          icon: "🛍", color: "#818cf8",
      keywords: ["trendyol", "hepsiburada", "amazon", "iyzico", "hepsipay", "paycell", "param/", "internet satis", "internet satış", "network istanbul"] },
    { name: "Turizm / Konaklama", icon: "🏨", color: "#34d399",
      keywords: ["otel", "hotel", "tatil", "etstur", "hostel", "airbnb", "booking", "konaklama", "turizm", "pansiyon"] },
    { name: "Seyahat",            icon: "✈", color: "#60a5fa",
      keywords: ["thy", "pegasus", "sunexpress", "anadolujet", "havayolu", "havalimanı", "havalimanı", "airport", "uçak bileti"] },
    { name: "Ulaşım",             icon: "🚗", color: "#fb923c",
      keywords: ["taksi", "taxi", "uber", "bitaksi", "dolmuş", "dolmus", "otobus ", "metro ", "metrobus", "otogar", "kargo", "taşımacı", "tasimaci"] },
    { name: "Telekomünikasyon",   icon: "📡", color: "#22d3ee",
      keywords: ["turkcell", "vodafone", "türk telekom", "turk telekom", "superonline", "gsm", "internet paketi"] },
    { name: "Eğlence / Hobi",     icon: "🎮", color: "#c084fc",
      keywords: ["netflix", "spotify", "disney", "youtube", "twitch", "steam", "playstation", "claude", "anthropic", "openai", "tradingview", "betterme", "amazon prime", "gaming", "eğlence"] },
    { name: "Birikim",            icon: "💰", color: "#34d399",
      keywords: ["birikim", "tasarruf", "mevduat"] },
    { name: "Yatırım",            icon: "📊", color: "#22d3ee",
      keywords: ["yatırım", "yatirim", "borsa", "hisse senet"] },
    { name: "Şans Oyunu",         icon: "🎲", color: "#f43f5e",
      keywords: ["iddaa", "milli piyango", "bahis"] },
  ];

  /** Returns the category for a transaction description, or null if unclassified */
  function categorizeTransaction(description: string): TxCat | null {
    if (!description) return null;
    const d = trLower(description);
    for (const cat of TX_CATEGORIES) {
      if (cat.keywords.some((kw) => d.includes(trLower(kw)))) {
        return { name: cat.name, icon: cat.icon, color: cat.color };
      }
    }
    return null;
  }

  const upcomingPayments = useMemo(() => {
    const now = new Date();
    const in30 = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
    return statements
      .filter((s) => s.due_date && !isPaid(s) && new Date(s.due_date) <= in30)
      .sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""));
  }, [statements]);

  /** Dashboard: yalnızca puan/mil son kullanım hatırlatmaları (son tarihi geçmemiş). */
  const activeDashboardReminders = useMemo(() => {
    type Row = {
      stmtId: number;
      bankName: string | null;
      cardNumber: string | null;
      periodLabel: string;
      periodEnd: string | null;
      createdAt: string | null;
      fileName: string;
      reminder: StatementReminder;
      loyaltyProgram: string;
      remainingValueTry: number | null;
    };
    const rows: Row[] = [];
    for (const s of statements) {
      for (const r of loyaltyReminders(s.statement_reminders)) {
        if (r.expires_on && reminderDeadlinePassed(r.expires_on)) continue;
        const remainingValueTry = r.remaining_value_try ?? fallbackRemainingValueTry(r);
        rows.push({
          stmtId: s.id,
          bankName: s.bank_name,
          cardNumber: s.card_number,
          periodLabel: `${s.period_start ?? "—"} — ${s.period_end ?? "—"}`,
          periodEnd: s.period_end,
          createdAt: s.created_at,
          fileName: s.file_name,
          reminder: r,
          loyaltyProgram: loyaltyProgramOf(r),
          remainingValueTry,
        });
      }
    }
    rows.sort((a, b) => {
      const ea = a.reminder.expires_on;
      const eb = b.reminder.expires_on;
      if (ea && !eb) return -1;
      if (!ea && eb) return 1;
      if (ea && eb) return ea.localeCompare(eb);
      return a.reminder.title.localeCompare(b.reminder.title, "tr");
    });
    return rows;
  }, [statements]);

  // Same data as activeDashboardReminders but keeps expired rows for "last known balance" view.
  const allDashboardLoyaltyRows = useMemo(() => {
    type Row = {
      stmtId: number;
      bankName: string | null;
      cardNumber: string | null;
      periodLabel: string;
      periodEnd: string | null;
      createdAt: string | null;
      fileName: string;
      reminder: StatementReminder;
      loyaltyProgram: string;
      remainingValueTry: number | null;
    };
    const rows: Row[] = [];
    for (const s of statements) {
      for (const r of loyaltyReminders(s.statement_reminders)) {
        const remainingValueTry = r.remaining_value_try ?? fallbackRemainingValueTry(r);
        rows.push({
          stmtId: s.id,
          bankName: s.bank_name,
          cardNumber: s.card_number,
          periodLabel: `${s.period_start ?? "—"} — ${s.period_end ?? "—"}`,
          periodEnd: s.period_end,
          createdAt: s.created_at,
          fileName: s.file_name,
          reminder: r,
          loyaltyProgram: loyaltyProgramOf(r),
          remainingValueTry,
        });
      }
    }
    rows.sort((a, b) => {
      const ea = a.reminder.expires_on;
      const eb = b.reminder.expires_on;
      if (ea && !eb) return -1;
      if (!ea && eb) return 1;
      if (ea && eb) return ea.localeCompare(eb);
      return a.reminder.title.localeCompare(b.reminder.title, "tr");
    });
    return rows;
  }, [statements]);

  const loyaltyBalances = useMemo(() => {
    type Bal = {
      key: string;
      bankName: string | null;
      cardNumber: string | null;
      loyaltyProgram: string;
      remainingValueTry: number;
      stmtId: number;
      expiresOn: string | null;
      periodEnd: string | null;
      createdAt: string | null;
    };
    const byKey = new Map<string, Bal>();
    for (const row of allDashboardLoyaltyRows) {
      if (row.remainingValueTry == null || row.remainingValueTry <= 0) continue;
      const key = `${row.bankName ?? ""}|${row.cardNumber ?? ""}|${row.loyaltyProgram}`;
      const prev = byKey.get(key);
      const nextVal: Bal = {
        key,
        bankName: row.bankName,
        cardNumber: row.cardNumber,
        loyaltyProgram: row.loyaltyProgram,
        remainingValueTry: row.remainingValueTry,
        stmtId: row.stmtId,
        expiresOn: row.reminder.expires_on ?? null,
        periodEnd: row.periodEnd,
        createdAt: row.createdAt,
      };
      if (!prev) {
        byKey.set(key, nextVal);
        continue;
      }
      const prevRank = prev.periodEnd ?? prev.createdAt ?? "";
      const nextRank = nextVal.periodEnd ?? nextVal.createdAt ?? "";
      if (nextRank > prevRank) byKey.set(key, nextVal);
    }
    let items = Array.from(byKey.values());

    // If the same card has both a specific program and generic "Puan/Mil"
    // with the same balance, keep the specific program only.
    const hasSpecificBySignature = new Set<string>();
    for (const it of items) {
      const prog = (it.loyaltyProgram || "").trim().toLowerCase();
      const isGeneric = prog === "puan" || prog === "mil";
      if (isGeneric) continue;
      const amountSig = (Math.round(it.remainingValueTry * 100) / 100).toFixed(2);
      hasSpecificBySignature.add(`${it.bankName ?? ""}|${it.cardNumber ?? ""}|${amountSig}`);
    }
    items = items.filter((it) => {
      const prog = (it.loyaltyProgram || "").trim().toLowerCase();
      const isGeneric = prog === "puan" || prog === "mil";
      if (!isGeneric) return true;
      const amountSig = (Math.round(it.remainingValueTry * 100) / 100).toFixed(2);
      const sig = `${it.bankName ?? ""}|${it.cardNumber ?? ""}|${amountSig}`;
      return !hasSpecificBySignature.has(sig);
    });

    items = items.sort((a, b) => {
      if ((a.expiresOn ?? "") !== (b.expiresOn ?? "")) {
        return (a.expiresOn ?? "9999-12-31").localeCompare(b.expiresOn ?? "9999-12-31");
      }
      return b.remainingValueTry - a.remainingValueTry;
    });
    const totalTry = items.reduce((sum, x) => sum + x.remainingValueTry, 0);
    return { items, totalTry };
  }, [allDashboardLoyaltyRows]);

  const loyaltyBankProgramBalances = useMemo(() => {
    type Group = {
      key: string;
      bankName: string;
      loyaltyProgram: string;
      totalTry: number;
      cardCount: number;
    };
    const byKey = new Map<string, { bankName: string; loyaltyProgram: string; totalTry: number; cards: Set<string> }>();
    for (const it of loyaltyBalances.items) {
      const bankName = (it.bankName ?? "Bilinmiyor").trim() || "Bilinmiyor";
      const loyaltyProgram = it.loyaltyProgram || "Puan";
      const key = `${bankName}|${loyaltyProgram}`;
      const prev = byKey.get(key) ?? { bankName, loyaltyProgram, totalTry: 0, cards: new Set<string>() };
      prev.totalTry += it.remainingValueTry;
      prev.cards.add(it.cardNumber ?? "");
      byKey.set(key, prev);
    }
    return Array.from(byKey.values())
      .map<Group>((g) => ({
        key: `${g.bankName}|${g.loyaltyProgram}`,
        bankName: g.bankName,
        loyaltyProgram: g.loyaltyProgram,
        totalTry: g.totalTry,
        cardCount: g.cards.size,
      }))
      .sort((a, b) => {
        const bankCmp = a.bankName.localeCompare(b.bankName, "tr");
        if (bankCmp !== 0) return bankCmp;
        return b.totalTry - a.totalTry;
      });
  }, [loyaltyBalances.items]);

  // Total debt = only unpaid (active) statements
  const totalDebt = useMemo(
    () => statements.filter((s) => !isPaid(s)).reduce((acc, s) => acc + (s.total_due_try ?? 0), 0),
    [statements]
  );

  // Group filtered statements by bank, preserving sort by most recent period_end
  const statementsByBank = useMemo(() => {
    const groups = new Map<string, typeof visibleStatements>();
    for (const s of visibleStatements) {
      const bank = s.bank_name ?? "Bilinmiyor";
      if (!groups.has(bank)) groups.set(bank, []);
      groups.get(bank)!.push(s);
    }
    // Sort each group newest-first
    for (const arr of groups.values()) {
      arr.sort((a, b) => (b.period_end ?? "").localeCompare(a.period_end ?? ""));
    }
    // Sort banks: most total debt first
    return new Map(
      [...groups.entries()].sort(
        (a, b) =>
          b[1].reduce((s, x) => s + (x.total_due_try ?? 0), 0) -
          a[1].reduce((s, x) => s + (x.total_due_try ?? 0), 0)
      )
    );
  }, [visibleStatements]);

  // Per-bank totals for dashboard — debt only from unpaid statements
  const bankSummaries = useMemo(() => {
    return [...statementsByBank.entries()].map(([bank, stmts]) => {
      const unpaid = stmts.filter((s) => !isPaid(s));
      const paid = stmts.filter((s) => isPaid(s));
      return {
        bank,
        total: unpaid.reduce((s, x) => s + (x.total_due_try ?? 0), 0),
        count: stmts.length,
        unpaidCount: unpaid.length,
        paidCount: paid.length,
        txCount: stmts.reduce((s, x) => s + x.transaction_count, 0),
        nextDue: unpaid
          .filter((s) => s.due_date)
          .sort((a, b) => (a.due_date ?? "").localeCompare(b.due_date ?? ""))[0]?.due_date ?? null,
      };
    });
  }, [statementsByBank]);

  function daysUntil(dateStr: string): number {
    return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86_400_000);
  }

  function daysLeftUntilDate(dateStr: string): number {
    return Math.ceil((new Date(`${dateStr}T12:00:00`).getTime() - Date.now()) / 86_400_000);
  }

  function fmtTry(n: number | null) {
    if (n == null) return "—";
    return n.toLocaleString("tr-TR", { minimumFractionDigits: 2 }) + " TL";
  }

  const tabTitle: Record<AppTab, string> = {
    dashboard: "Özet",
    statements: "Ekstreler",
    documents: "Dosyalar",
    search: "Arama",
    logs: "Sistem Logları",
    mail: "Mail & Sync",
    settings: "Ayarlar",
  };

  // Global search results — flattened transactions across all statements
  type SearchHit = {
    tx_date: string | null;
    description: string;
    amount: number;
    currency: string;
    bank_name: string;
    card_number: string | null;
    period_end: string | null;
    stmt_id: number;
  };

  const globalSearchResults = useMemo((): SearchHit[] => {
    const q = trLower(globalSearch.trim());
    const active = feeMode || q.length >= 2;
    if (!active) return [];
    // Terms: split by space for OR matching (each term must match independently)
    const terms = q.length >= 2 ? q.split(/\s+/).filter(Boolean) : [];
    const hits: SearchHit[] = [];
    for (const stmt of statements) {
      for (const tx of stmt.transactions) {
        const desc = trLower(tx.description ?? "");
        const matchesFee = feeMode && tx.amount > 0 && isFee(tx.description);
        const matchesText = terms.length > 0 && terms.some((t) => desc.includes(t));
        if (matchesFee || matchesText) {
          hits.push({
            tx_date: tx.date,
            description: tx.description,
            amount: tx.amount,
            currency: tx.currency,
            bank_name: stmt.bank_name ?? "Bilinmiyor",
            card_number: stmt.card_number,
            period_end: stmt.period_end,
            stmt_id: stmt.id,
          });
        }
      }
    }
    // Sort newest first
    hits.sort((a, b) => (b.tx_date ?? "").localeCompare(a.tx_date ?? ""));
    return hits;
  }, [globalSearch, feeMode, statements]);

  // Per-merchant summary for search results
  const searchSummary = useMemo(() => {
    if (globalSearchResults.length === 0) return null;
    const totalSpend = globalSearchResults.filter((h) => h.amount > 0).reduce((s, h) => s + h.amount, 0);
    const totalCredit = globalSearchResults.filter((h) => h.amount < 0).reduce((s, h) => s + Math.abs(h.amount), 0);
    const bankSet = new Set(globalSearchResults.map((h) => h.bank_name));
    return { totalSpend, totalCredit, bankCount: bankSet.size, txCount: globalSearchResults.length };
  }, [globalSearchResults]);

  const isSearchActive = feeMode || globalSearch.trim().length >= 2;

  return (
    <div className="shell">
      {/* ── Desktop sidebar ── */}
      <aside className="sidebar">
        <div className="sidebarLogo">
          <svg className="logoIcon" width="38" height="38" viewBox="0 0 38 38" fill="none" aria-hidden>
            {/* Card body */}
            <rect x="3" y="9" width="32" height="21" rx="4.5" fill="#0d1f38" stroke="#38bdf8" strokeWidth="1.5"/>
            {/* Chip */}
            <rect x="8" y="15" width="8" height="6" rx="1.5" fill="none" stroke="#38bdf8" strokeWidth="1.2"/>
            <line x1="12" y1="15" x2="12" y2="21" stroke="#38bdf8" strokeWidth="0.8" strokeOpacity="0.6"/>
            <line x1="8"  y1="18" x2="16" y2="18" stroke="#38bdf8" strokeWidth="0.8" strokeOpacity="0.6"/>
            {/* Contactless waves */}
            <path d="M21 16 Q24 18 21 21" stroke="#38bdf8" strokeWidth="1.2" strokeLinecap="round" fill="none" strokeOpacity="0.7"/>
            <path d="M23.5 14.5 Q28 18 23.5 22.5" stroke="#38bdf8" strokeWidth="1.2" strokeLinecap="round" fill="none" strokeOpacity="0.45"/>
            {/* Bottom dots (card numbers placeholder) */}
            <rect x="8"  y="25" width="5" height="2" rx="1" fill="#38bdf8" fillOpacity="0.35"/>
            <rect x="15" y="25" width="5" height="2" rx="1" fill="#38bdf8" fillOpacity="0.35"/>
            <rect x="22" y="25" width="5" height="2" rx="1" fill="#38bdf8" fillOpacity="0.35"/>
          </svg>
          <div>
            <div className="logoTitle">EkstreHub</div>
            <div className="logoSub">Kredi Kartı Takip</div>
          </div>
        </div>
        <nav className="sidebarNav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`navItem${activeTab === item.id ? " navActive" : ""}`}
              onClick={() => setActiveTab(item.id)}
            >
              <span className="navIcon">{item.icon}</span>
              <span>{item.label}</span>
              {item.id === "statements" && statements.length > 0 && (
                <span className="navBadge">{statements.length}</span>
              )}
              {item.id === "documents" && ingestionStats != null && ingestionStats.non_parsed > 0 && (
                <span className="navBadge navBadgeWarn">{ingestionStats.non_parsed}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebarFooter">
          <span className={`statusDot ${loadState === "success" ? "dotOk" : loadState === "error" ? "dotErr" : "dotMuted"}`} />
          <span className="statusText">{statusLabel}</span>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="main">
        <header className="topbar">
          <h1 className="topbarTitle">{tabTitle[activeTab]}</h1>
          <div className="topbarActions">
            {errorMessage ? <span className="topbarError">{errorMessage}</span> : null}
            <button className="iconBtn" onClick={reloadCoreData} title="Yenile" aria-label="Yenile">↺</button>
          </div>
        </header>

        <div className="content">
          {/* ─── ÖZET (dashboard) ─── */}
          {activeTab === "dashboard" && (
            <>
              <div className="kpiGrid">
                <div className="kpiCard">
                  <p className="kpiLabel">Toplam Borç</p>
                  <p className="kpiValue">{totalDebt > 0 ? fmtTry(totalDebt) : "—"}</p>
                  <p className="kpiSub">
                    {statements.filter((s) => !isPaid(s)).length} aktif ekstre
                    {statements.filter((s) => isPaid(s)).length > 0 && (
                      <span style={{ color: "var(--ok)", marginLeft: 6 }}>
                        · {statements.filter((s) => isPaid(s)).length} ödendi
                      </span>
                    )}
                  </p>
                </div>
                <div className="kpiCard">
                  <p className="kpiLabel">Toplam İşlem</p>
                  <p className="kpiValue">{statements.reduce((a, s) => a + s.transaction_count, 0)}</p>
                  <p className="kpiSub">{statements.length} dosyadan</p>
                </div>
                <div className={`kpiCard${upcomingPayments.length > 0 ? " kpiCardWarn" : ""}`}>
                  <p className="kpiLabel">Yaklaşan Ödeme</p>
                  {upcomingPayments.length > 0 ? (
                    <>
                      <p className="kpiValue kpiSmall">{upcomingPayments.length} kart</p>
                      <p className="kpiSub">
                        En yakın: {upcomingPayments[0].due_date} · {upcomingPayments[0].bank_name} · {daysUntil(upcomingPayments[0].due_date!)} gün
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="kpiValue kpiSmall">—</p>
                      <p className="kpiSub">30 gün içinde ödeme yok</p>
                    </>
                  )}
                </div>
                <div className="kpiCard">
                  <p className="kpiLabel">Son Sync</p>
                  {latestRuns.length > 0 ? (
                    <>
                      <p className="kpiValue kpiSmall">Run #{latestRuns[0].id}</p>
                      <p className="kpiSub">
                        <span className={statusBadge(latestRuns[0].status)}>{latestRuns[0].status}</span>
                        {" · "}{latestRuns[0].scanned_messages} mesaj
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="kpiValue kpiSmall">—</p>
                      <p className="kpiSub">Henüz sync çalışmadı</p>
                    </>
                  )}
                </div>
                <div
                  className={`kpiCard${loyaltyBankProgramBalances.length > 0 ? " kpiCardWarn kpiCardClickable" : ""}`}
                  role={loyaltyBankProgramBalances.length > 0 ? "button" : undefined}
                  tabIndex={loyaltyBankProgramBalances.length > 0 ? 0 : undefined}
                  onClick={() => {
                    if (loyaltyBankProgramBalances.length === 0) return;
                    const el = document.querySelector(".pointsBalanceSection");
                    el?.scrollIntoView({ behavior: "smooth", block: "start" });
                  }}
                  onKeyDown={(e) => {
                    if (e.key !== "Enter" || loyaltyBankProgramBalances.length === 0) return;
                    document.querySelector(".pointsBalanceSection")?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <p className="kpiLabel">Puan / Mil</p>
                  <p className="kpiValue kpiSmall">
                    {loyaltyBalances.totalTry > 0 ? fmtTry(loyaltyBalances.totalTry) : "—"}
                  </p>
                  <p className="kpiSub">
                    {loyaltyBankProgramBalances.length > 0
                      ? `${loyaltyBankProgramBalances.length} banka/program bakiyesi`
                      : "Harcanabilir bakiye bulunamadı"}
                  </p>
                </div>
              </div>

              {loyaltyBankProgramBalances.length > 0 && (
                <section className="section">
                  <div className="sectionHeader">
                    <div>
                      <h2 className="sectionTitle">Banka Bazlı Puan / Mil</h2>
                      <p className="sectionSub">Yapı Kredi puan, İş Bankası mil/puan gibi tüm programlar tek yerde.</p>
                    </div>
                    <button className="linkBtn" onClick={() => setActiveTab("statements")}>
                      Ekstreler →
                    </button>
                  </div>
                  <div className="bankGrid">
                    {loyaltyBankProgramBalances.map((row) => (
                      <div key={row.key} className="bankCard">
                        <div className="bankCardTop">
                          <div className="stmtBankBadge">{row.bankName}</div>
                          <div className="bankCardAmount">{fmtTry(row.totalTry)}</div>
                        </div>
                        <div className="bankCardRow">
                          <span className="bankCardMeta">{row.loyaltyProgram}</span>
                          <span className="bankCardMeta">{row.cardCount} kart</span>
                        </div>
                        <div className="bankCardFooter">Son bilinen harcanabilir bakiye</div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {upcomingPayments.length > 0 && (
                <section className="section dueFocusSection">
                  <div className="sectionHeader">
                    <div>
                      <h2 className="sectionTitle">Yaklaşan Son Ödemeler</h2>
                      <p className="sectionSub">
                        Önümüzdeki 30 gün içinde son ödeme tarihi yaklaşan kartlar.
                      </p>
                    </div>
                    <button className="linkBtn" onClick={() => setActiveTab("statements")}>
                      Ekstreler →
                    </button>
                  </div>
                  <ul className="dueFocusList">
                    {upcomingPayments.slice(0, 8).map((s) => {
                      const days = daysUntil(s.due_date!);
                      const urgent = days >= 0 && days <= 7;
                      return (
                        <li key={s.id} className={`dueFocusRow${urgent ? " dueFocusRowUrgent" : ""}`}>
                          <div className="dueFocusMain">
                            <div className="dueFocusTitleRow">
                              <span className="stmtBankBadge">{s.bank_name ?? "—"}</span>
                              <span className="dueFocusCard">{maskedCardLabel(s.card_number)}</span>
                              <span className={`dueFocusDays${urgent ? " dueFocusDaysUrgent" : ""}`}>
                                {days} gün
                              </span>
                            </div>
                            <div className="dueFocusMeta">
                              Son ödeme: <strong>{s.due_date}</strong>
                              <span className="pointsReminderSep">·</span>
                              Dönem: {s.period_start ?? "—"} — {s.period_end ?? "—"}
                            </div>
                          </div>
                          <div className="dueFocusAmount">
                            <div className="dueFocusTotal">{fmtTry(s.total_due_try)}</div>
                            <div className="dueFocusMin">Min: {fmtTry(s.minimum_due_try)}</div>
                          </div>
                          <button
                            type="button"
                            className="pointsReminderOpenBtn"
                            onClick={() => {
                              setActiveTab("statements");
                              setExpandedStatementId(s.id);
                            }}
                          >
                            Aç
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}

              <section className="section pointsBalanceSection">
                <div className="sectionHeader pointsReminderSectionHeader">
                  <div>
                    <h2 className="sectionTitle">Harcanabilir Puan / Mil Bakiyesi</h2>
                    <p className="sectionSub">Banka ve program bazında son bilinen kalan bakiye (ekstrelerden).</p>
                  </div>
                  <button
                    type="button"
                    className="linkBtn"
                    onClick={() => {
                      setActiveTab("statements");
                    }}
                  >
                    Ekstreler →
                  </button>
                </div>
                {loyaltyBankProgramBalances.length === 0 ? (
                  <p className="muted">Henüz harcanabilir puan/mil bakiyesi çıkarılamadı. Ekstrelerde yeniden çöz çalıştır.</p>
                ) : (
                  <ul className="pointsReminderList">
                    {loyaltyBankProgramBalances.map((row) => (
                      <li key={row.key} className="pointsReminderRow pointsReminderRowPoints">
                        <div className="pointsReminderIcon" aria-hidden>🏦</div>
                        <div className="pointsReminderBody">
                          <div className="pointsReminderTitleRow">
                            <span className="pointsReminderTitle">{row.bankName}</span>
                            <span className="pointsReminderKind">{row.loyaltyProgram}</span>
                            <span className="pointsReminderKind">{fmtTry(row.totalTry)}</span>
                          </div>
                          <div className="pointsReminderMeta">
                            <span className="pointsReminderBank">{row.cardCount} kart</span>
                            <span className="pointsReminderSep">·</span>
                            <span className="pointsReminderPeriod">Son bilinen harcanabilir toplam bakiye</span>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="section pointsReminderSection">
                  <div className="sectionHeader pointsReminderSectionHeader">
                    <div>
                      <h2 className="sectionTitle">Puan / Mil Son Kullanım</h2>
                      <p className="sectionSub">
                        Sadece harcanması gereken puan/mil bildirimleri.
                      </p>
                    </div>
                    <button
                      type="button"
                      className="linkBtn"
                      onClick={() => {
                        setActiveTab("statements");
                      }}
                    >
                      Ekstreler →
                    </button>
                  </div>
                  {activeDashboardReminders.length === 0 ? (
                    <p className="muted">Puan/mil kaydı bulunamadı. Ekstreler için yeniden çöz çalıştır.</p>
                  ) : (
                  <ul className="pointsReminderList">
                    {loyaltyBalances.items.length > 0 && (
                      <li className="pointsReminderRow pointsReminderRowPoints">
                        <div className="pointsReminderIcon" aria-hidden>Σ</div>
                        <div className="pointsReminderBody">
                          <div className="pointsReminderTitleRow">
                            <span className="pointsReminderTitle">Toplam kalan puan/mil değeri</span>
                          </div>
                          <div className="pointsReminderMeta" style={{ flexWrap: "wrap", rowGap: 6 }}>
                            <span className="pointsReminderBank" style={{ fontWeight: 700 }}>
                              {fmtTry(loyaltyBalances.totalTry)}
                            </span>
                            {loyaltyBalances.items.map((it) => (
                              <span key={it.key} className="pointsReminderFile" style={{ borderStyle: "solid" }}>
                                {(it.bankName ?? "—")} · {maskedCardLabel(it.cardNumber)} · {it.loyaltyProgram}: {fmtTry(it.remainingValueTry)}
                              </span>
                            ))}
                          </div>
                        </div>
                      </li>
                    )}
                    {activeDashboardReminders.map((row, idx) => {
                      const { reminder: r } = row;
                      const exp = r.expires_on;
                      const days = exp ? daysLeftUntilDate(exp) : null;
                      const urgent = exp != null && days != null && days >= 0 && days <= 30;
                      return (
                        <li
                          key={`${row.stmtId}-${idx}-${r.title.slice(0, 24)}`}
                          className={`pointsReminderRow pointsReminderRowPoints${urgent ? " pointsReminderRowUrgent" : ""}`}
                        >
                          <div className="pointsReminderIcon" aria-hidden>
                            🎁
                          </div>
                          <div className="pointsReminderBody">
                            <div className="pointsReminderTitleRow">
                              <span className="pointsReminderTitle">{r.title}</span>
                              <span className="pointsReminderKind">
                                {REMINDER_KIND_LABEL[r.kind] ?? r.kind}
                              </span>
                              {row.remainingValueTry != null && row.remainingValueTry > 0 && (
                                <span className="pointsReminderKind">{fmtTry(row.remainingValueTry)}</span>
                              )}
                            </div>
                            <div className="pointsReminderMeta">
                              <span className="pointsReminderBank">{row.bankName ?? "—"}</span>
                              <span className="pointsReminderSep">·</span>
                              <span className="pointsReminderPeriod">{maskedCardLabel(row.cardNumber)}</span>
                              <span className="pointsReminderSep">·</span>
                              <span className="pointsReminderPeriod">{row.loyaltyProgram}</span>
                              <span className="pointsReminderSep">·</span>
                              <span className="pointsReminderPeriod">{row.periodLabel}</span>
                              <span className="pointsReminderSep">·</span>
                              <span className="pointsReminderFile" title={row.fileName}>
                                {row.fileName.length > 42 ? `${row.fileName.slice(0, 40)}…` : row.fileName}
                              </span>
                            </div>
                            {exp != null && (
                              <div className="pointsReminderDateRow">
                                <span className={urgent ? "pointsReminderUrgent" : "pointsReminderDateLabel"}>
                                  Son kullanma: {exp}
                                  {days != null && days >= 0 && (
                                    <strong> ({days} gün kaldı)</strong>
                                  )}
                                </span>
                              </div>
                            )}
                          </div>
                          <button
                            type="button"
                            className="pointsReminderOpenBtn"
                            onClick={() => {
                              setActiveTab("statements");
                              setExpandedStatementId(row.stmtId);
                            }}
                          >
                            Aç
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                  )}
                </section>

              {bankSummaries.length > 0 ? (
                <>
                  {/* Per-bank summary cards */}
                  <section className="section">
                    <div className="sectionHeader">
                      <h2 className="sectionTitle">Bankalar</h2>
                      <button className="linkBtn" onClick={() => setActiveTab("statements")}>
                        Tüm ekstreler ({statements.length}) →
                      </button>
                    </div>
                    <div className="bankGrid">
                      {bankSummaries.map(({ bank, total, count, unpaidCount, paidCount, txCount, nextDue }) => (
                        <div
                          key={bank}
                          className={`bankCard${unpaidCount === 0 ? " bankCardPaid" : ""}`}
                          role="button"
                          tabIndex={0}
                          onClick={() => { setStmtBankFilter(bank); setActiveTab("statements"); }}
                          onKeyDown={(e) => e.key === "Enter" && (setStmtBankFilter(bank), setActiveTab("statements"))}
                        >
                          <div className="bankCardTop">
                            <div className="stmtBankBadge">{bank}</div>
                            <div className="bankCardAmount">
                              {unpaidCount > 0 ? fmtTry(total) : <span className="paidLabel">✓ Ödendi</span>}
                            </div>
                          </div>
                          <div className="bankCardRow">
                            <span className="bankCardMeta">
                              {count} ekstre · {txCount} işlem
                              {paidCount > 0 && unpaidCount > 0 && (
                                <span style={{ color: "var(--ok)", marginLeft: 6 }}>· {paidCount} ödendi</span>
                              )}
                            </span>
                            {nextDue && (
                              <span className={`bankCardMeta ${daysUntil(nextDue) <= 7 ? "bankCardWarn" : ""}`}>
                                Son ödeme: {nextDue}
                                {daysUntil(nextDue) >= 0 && daysUntil(nextDue) <= 30 && (
                                  <strong> ({daysUntil(nextDue)} gün)</strong>
                                )}
                              </span>
                            )}
                          </div>
                          <div className="bankCardFooter">Detay →</div>
                        </div>
                      ))}
                    </div>
                  </section>

                  {/* Most recent statement per bank */}
                  <section className="section">
                    <h2 className="sectionTitle" style={{ marginBottom: 12 }}>Son Ekstreler</h2>
                    <div className="stmtList">
                      {[...statementsByBank.entries()].map(([bank, stmts]) => {
                        const latest = stmts[0];
                        return (
                          <div
                            key={bank}
                            className="stmtCard stmtCardClickable"
                            role="button"
                            tabIndex={0}
                            onClick={() => { setActiveTab("statements"); setExpandedStatementId(latest.id); }}
                            onKeyDown={(e) => e.key === "Enter" && (setActiveTab("statements"), setExpandedStatementId(latest.id))}
                          >
                            <div className="stmtCardHeader">
                              <div className="stmtBankBadge">{latest.bank_name ?? "?"}</div>
                              <div className="stmtMain">
                                <div className="stmtTitle">
                                  {latest.period_start} — {latest.period_end}
                                  {latest.card_number && (
                                    <span className="cardNumBadge">💳 {latest.card_number}</span>
                                  )}
                                </div>
                                <div className="stmtPeriod">
                                  {latest.transaction_count} işlem · Son ödeme:{" "}
                                  <strong style={{ color: "var(--text2)" }}>{latest.due_date ?? "—"}</strong>
                                  {stmts.length > 1 && (
                                    <span className="bankHistoryHint"> · {stmts.length} dönem</span>
                                  )}
                                </div>
                              </div>
                              <div className="stmtRight">
                                <div className="stmtAmount">{fmtTry(latest.total_due_try)}</div>
                                {latest.due_date && daysUntil(latest.due_date) >= 0 && daysUntil(latest.due_date) <= 7 && (
                                  <div className="dueBadgeWarn">{daysUntil(latest.due_date)} gün</div>
                                )}
                              </div>
                              <span className="stmtChevron">›</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                </>
              ) : (
                <div className="emptyState">
                  <p className="emptyIcon">📄</p>
                  <p className="emptyTitle">Henüz ekstre yok</p>
                  <p className="emptySub">Mail hesabı ekle ve sync çalıştır.</p>
                  <button className="btn btnPrimary" onClick={() => setActiveTab("mail")}>Mail Hesabı Ekle →</button>
                </div>
              )}

              {health && (
                <section className="section">
                  <h2 className="sectionTitle" style={{ marginBottom: 10 }}>Sistem Durumu</h2>
                  <div className="healthGrid">
                    <div className="healthItem">
                      <span className="healthLabel">Veritabanı</span>
                      <span className={`healthValue ${health.db_available ? "valOk" : "valErr"}`}>
                        {health.db_available ? "● Hazır" : "● Bağlanamıyor"}
                      </span>
                    </div>
                    <div className="healthItem">
                      <span className="healthLabel">Mail Ingestion</span>
                      <span className={`healthValue ${health.mail_ingestion_enabled ? "valOk" : "valMuted"}`}>
                        {health.mail_ingestion_enabled ? "● Açık" : "● Kapalı"}
                      </span>
                    </div>
                    <div className="healthItem">
                      <span className="healthLabel">IMAP</span>
                      <span className="healthValue valMuted">{health.masked_imap_user || "—"}</span>
                    </div>
                    <div className="healthItem">
                      <span className="healthLabel">Ortam</span>
                      <span className="healthValue valMuted">{health.environment}</span>
                    </div>
                    <div className="healthItem">
                      <span className="healthLabel">Sürüm</span>
                      <span className="healthValue valMuted" title="HA add-on config.yaml ile aynı">
                        {health.addon_version ?? "—"}
                      </span>
                    </div>
                  </div>
                </section>
              )}
            </>
          )}

          {/* ─── EKSTRELER ─── */}
          {activeTab === "statements" && (
            <>
              <div className="filterBar">
                <input
                  className="searchInput"
                  placeholder="Banka, dönem veya işlem açıklaması ara..."
                  value={stmtSearch}
                  onChange={(e) => setStmtSearch(e.target.value)}
                />
                {bankNames.length > 1 && (
                  <select className="filterSelect" value={stmtBankFilter} onChange={(e) => setStmtBankFilter(e.target.value)}>
                    <option value="all">Tüm bankalar</option>
                    {bankNames.map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                )}
              </div>

              {/* Bulk selection toolbar */}
              {selectedStmtIds.size > 0 && (
                <div className="bulkActionBar">
                  <span className="bulkCount">{selectedStmtIds.size} ekstre seçildi</span>
                  <button
                    type="button"
                    className="bulkReparseBtn"
                    disabled={isDeletingStmts || isReparsingStatements || !llmReadyForReparse}
                    title={!llmReadyForReparse ? "Ayarlar → AI Parser: LLM açık ve API URL dolu olmalı" : "Mailden PDF tekrar alınır, LLM ile parse"}
                    onClick={() => void handleReparseSelectedStatements()}
                  >
                    {isReparsingStatements ? "Yeniden çözülüyor…" : "↻ Seçilenleri yeniden çöz"}
                  </button>
                  <button
                    className="bulkDeleteBtn"
                    disabled={isDeletingStmts || isReparsingStatements}
                    onClick={() => confirmDeleteStatements(
                      Array.from(selectedStmtIds),
                      `${selectedStmtIds.size} ekstre`
                    )}
                  >
                    🗑 Seçilenleri Sil
                  </button>
                  <button
                    className="bulkCancelBtn"
                    disabled={isReparsingStatements}
                    onClick={() => setSelectedStmtIds(new Set())}
                  >
                    İptal
                  </button>
                </div>
              )}

              {visibleStatements.length === 0 ? (
                <div className="emptyState">
                  <p className="emptyIcon">🔍</p>
                  <p className="emptyTitle">{stmtSearch || stmtBankFilter !== "all" ? "Sonuç bulunamadı" : "Henüz ekstre yok"}</p>
                  <p className="emptySub">
                    {stmtSearch
                      ? `"${stmtSearch}" ile eşleşen ekstre veya işlem yok.`
                      : "Mail & Sync sekmesinden sync çalıştır."}
                  </p>
                </div>
              ) : (
                <div>
                  {[...statementsByBank.entries()].map(([bank, bankStmts]) => (
                    <section key={bank} className="section">
                      {/* Bank group header */}
                      <div className="bankGroupHeader">
                        <div className="stmtBankBadge">{bank}</div>
                        <div className="bankGroupMeta">
                          {bankStmts.length} ekstre · {bankStmts.reduce((s, x) => s + x.transaction_count, 0)} işlem
                          {bankStmts.filter((s) => isPaid(s)).length > 0 && (
                            <span style={{ color: "var(--ok)", marginLeft: 8 }}>
                              · {bankStmts.filter((s) => isPaid(s)).length} ödendi
                            </span>
                          )}
                        </div>
                        <div className="bankGroupTotal">
                          {fmtTry(bankStmts.filter((s) => !isPaid(s)).reduce((s, x) => s + (x.total_due_try ?? 0), 0))}
                          {bankStmts.some((s) => isPaid(s)) && (
                            <span className="paidTotalNote"> aktif borç</span>
                          )}
                        </div>
                      </div>

                      <div className="stmtList">
                        {bankStmts.map((stmt) => {
                    const paid = isPaid(stmt);
                    // Auto-expand if stmtSearch matched transactions inside this statement
                    const hasMatchingTx = (stmtMatchingTxCount[stmt.id] ?? 0) > 0;
                    const isOpen = expandedStatementId === stmt.id || (!!stmtSearch && hasMatchingTx);
                    // Per-statement override has priority; fall back to global stmtSearch
                    const txQ = (txSearch[stmt.id] !== undefined
                      ? txSearch[stmt.id]
                      : stmtSearch
                    ).toLowerCase();
                    const visibleTx = txQ
                      ? stmt.transactions.filter((tx) => tx.description?.toLowerCase().includes(txQ))
                      : stmt.transactions;

                    // Fee summary for this statement
                    const feeTxList = stmt.transactions.filter((tx) => tx.amount > 0 && isFee(tx.description));
                    const feeTotalTRY = feeTxList
                      .filter((tx) => tx.currency === "TRY")
                      .reduce((s, tx) => s + tx.amount, 0);

                    return (
                      <div key={stmt.id} className={`stmtCard${paid ? " stmtCardPaid" : ""}${selectedStmtIds.has(stmt.id) ? " stmtCardSelected" : ""}`}>
                        {/* Checkbox + delete row */}
                        <div className="stmtSelectRow">
                          <label className="stmtCheckboxLabel" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              className="stmtCheckbox"
                              checked={selectedStmtIds.has(stmt.id)}
                              onChange={(e) => {
                                e.stopPropagation();
                                setSelectedStmtIds((prev) => {
                                  const next = new Set(prev);
                                  if (e.target.checked) next.add(stmt.id);
                                  else next.delete(stmt.id);
                                  return next;
                                });
                              }}
                            />
                            <span className="stmtCheckboxText">Seç</span>
                          </label>
                          <div className="stmtBankSelectWrap" onClick={(e) => e.stopPropagation()}>
                            <label className="stmtBankSelectLabel" htmlFor={`stmt-bank-${stmt.id}`}>
                              Banka
                            </label>
                            <select
                              id={`stmt-bank-${stmt.id}`}
                              className="stmtBankSelect"
                              value={stmt.bank_name ?? ""}
                              disabled={bankPatchingId === stmt.id}
                              title="Otomatik tespit yanlışsa (ör. PDF’te logo, metinde Param) düzelt"
                              onChange={(e) => {
                                const v = e.target.value;
                                if (!v || v === stmt.bank_name) return;
                                void (async () => {
                                  setBankPatchingId(stmt.id);
                                  try {
                                    await patchStatementBank(stmt.id, v);
                                    await reloadCoreData();
                                  } catch (err) {
                                    pushLog(
                                      "error",
                                      "parser",
                                      err instanceof Error ? err.message : String(err)
                                    );
                                  } finally {
                                    setBankPatchingId(null);
                                  }
                                })();
                              }}
                            >
                              {!stmt.bank_name && (
                                <option value="">— Seçin —</option>
                              )}
                              {statementBankSelectOptions(stmt.bank_name).map((b) => (
                                <option key={b} value={b}>
                                  {b}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="stmtCardActions">
                            {stmt.doc_type === "pdf" && (
                              <a
                                className="stmtPdfLink"
                                href={apiUrlPath(`api/statements/${stmt.id}/pdf`)}
                                target="_blank"
                                rel="noopener noreferrer"
                                title="Posta kutusundan orijinal PDF (doğrulama için)"
                                onClick={(e) => e.stopPropagation()}
                              >
                                Orijinal PDF
                              </a>
                            )}
                            {stmt.doc_type === "pdf" && (
                              <button
                                type="button"
                                className="stmtReparseBtn"
                                title={
                                  !llmReadyForReparse
                                    ? "AI Parser: LLM açık ve API URL gerekli"
                                    : "Mailden PDF tekrar al, LLM ile yeniden parse et"
                                }
                                disabled={
                                  isDeletingStmts
                                  || isReparsingStatements
                                  || reparseStmtId === stmt.id
                                  || !llmReadyForReparse
                                }
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void handleReparseStatement(stmt);
                                }}
                              >
                                {reparseStmtId === stmt.id ? "…" : "↻ Yeniden çöz"}
                              </button>
                            )}
                            <button
                              type="button"
                              className="stmtDeleteBtn"
                              title="Bu ekstreyi sil"
                              disabled={isDeletingStmts || isReparsingStatements || reparseStmtId === stmt.id}
                              onClick={(e) => {
                                e.stopPropagation();
                                const label = `${stmt.bank_name ?? "Ekstre"} ${stmt.period_start ?? ""}–${stmt.period_end ?? ""}`;
                                confirmDeleteStatements([stmt.id], label);
                              }}
                            >
                              🗑
                            </button>
                          </div>
                        </div>
                        <div
                          role="button"
                          tabIndex={0}
                          className="stmtCardHeader"
                          onClick={() => setExpandedStatementId(isOpen ? null : stmt.id)}
                          onKeyDown={(e) => e.key === "Enter" && setExpandedStatementId(isOpen ? null : stmt.id)}
                        >
                          <div className="stmtMain">
                            <div className="stmtTitle">
                              {stmt.period_start} — {stmt.period_end}
                              {stmt.card_number && (
                                <span className="cardNumBadge">💳 {stmt.card_number}</span>
                              )}
                              {stmt.parse_notes.includes("llm_parsed") && (
                                <span className="parseNoteBadge parseNoteLlm" title="Bu ekstre yapay zeka (LLM) tarafından parse edildi">
                                  AI
                                </span>
                              )}
                              {stmt.parse_notes.includes("llm_timeout") && (
                                <span
                                  className="parseNoteBadge parseNoteError"
                                  title="LLM zaman aşımı — Ayarlar → AI Parser’da süreyi 240–300 sn yapıp Yeniden çöz"
                                >
                                  ⏱ LLM timeout
                                </span>
                              )}
                              {stmt.parse_notes.includes("no_transactions_found") && !stmt.parse_notes.includes("llm_timeout") && (
                                <span className="parseNoteBadge parseNoteError" title="İşlem bulunamadı — PDF formatı tanınamıyor olabilir">
                                  ! İşlem yok
                                </span>
                              )}
                              {countActiveReminders(stmt.statement_reminders) > 0 && (
                                <span
                                  className="parseNoteBadge parseNoteReminder"
                                  title="PDF’teki puan/mil sadakat son kullanım hatırlatmaları"
                                >
                                  📌 {countActiveReminders(stmt.statement_reminders)} hatırlatma
                                </span>
                              )}
                            </div>
                            <div className="stmtPeriod">
                              {stmtMatchingTxCount[stmt.id] != null ? (
                                <span style={{ color: "var(--accent)", fontWeight: 600 }}>
                                  {stmtMatchingTxCount[stmt.id]} eşleşen işlem
                                </span>
                              ) : (
                                <>{stmt.transaction_count} işlem</>
                              )}
                              {" · "}Son ödeme:{" "}
                              <strong style={{ color: "var(--text2)" }}>{stmt.due_date ?? "—"}</strong>
                              {feeTxList.length > 0 && (
                                <span
                                  className="feeSummaryBadge"
                                  title={feeTxList.map((t) => t.description).join(", ")}
                                >
                                  ⚠ {feeTxList.length} ücret
                                  {feeTotalTRY > 0 && ` · ${feeTotalTRY.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL`}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="stmtRight">
                            {paid ? (
                              <div className="paidBadge">✓ Ödendi</div>
                            ) : (
                              <>
                                <div className="stmtAmount">{fmtTry(stmt.total_due_try)}</div>
                                {stmt.minimum_due_try != null && (
                                  <div className="stmtMinPay">Min: {fmtTry(stmt.minimum_due_try)}</div>
                                )}
                                {stmt.due_date && daysUntil(stmt.due_date) <= 7 && daysUntil(stmt.due_date) >= 0 && (
                                  <div className="dueBadgeWarn">{daysUntil(stmt.due_date)} gün kaldı</div>
                                )}
                              </>
                            )}
                          </div>
                          <span className="stmtChevron">{isOpen ? "▼" : "›"}</span>
                        </div>

                        {isOpen && (
                          <div className="txWrapper">
                            {loyaltyReminders(stmt.statement_reminders).length > 0 && (
                              <div className="stmtReminders">
                                <div className="stmtRemindersTitle">Puan / Mil hatırlatmaları</div>
                                <p className="stmtRemindersHint">
                                  Yalnızca sadakat puanı/mil son kullanım bildirimleri gösterilir.
                                </p>
                                <ul className="stmtRemindersList">
                                  {loyaltyReminders(stmt.statement_reminders).map((r, ri) => {
                                    const expired = r.expires_on ? reminderDeadlinePassed(r.expires_on) : false;
                                    const kind = REMINDER_KIND_LABEL[r.kind] ?? r.kind;
                                    return (
                                      <li
                                        key={ri}
                                        className={`stmtReminder${expired ? " stmtReminderExpired" : ""}`}
                                      >
                                        <div className="stmtReminderHead">
                                          <strong className="stmtReminderTitle">{r.title}</strong>
                                          <span className="stmtReminderKind">{kind}</span>
                                          {r.expires_on && (
                                            <span className={expired ? "stmtReminderDateExpired" : "stmtReminderDate"}>
                                              {expired ? "Süresi doldu · " : "Son tarih · "}
                                              {r.expires_on}
                                            </span>
                                          )}
                                        </div>
                                        <div className="stmtReminderText">{r.text}</div>
                                      </li>
                                    );
                                  })}
                                </ul>
                              </div>
                            )}
                            {stmt.transactions.length > 8 && (
                              <div className="txFilterBar">
                                <input
                                  className="txSearchInput"
                                  placeholder="İşlem ara..."
                                  value={txSearch[stmt.id] ?? ""}
                                  onChange={(e) =>
                                    setTxSearch((prev) => ({ ...prev, [stmt.id]: e.target.value }))
                                  }
                                />
                                {txQ && (
                                  <span className="txCount">
                                    {visibleTx.length}/{stmt.transactions.length} işlem
                                  </span>
                                )}
                              </div>
                            )}
                            <table className="txTable">
                              <thead>
                                <tr>
                                  <th>Tarih</th>
                                  <th>Açıklama</th>
                                  <th className="txAmountCol">Tutar</th>
                                  <th className="txCurrencyCol">Para</th>
                                </tr>
                              </thead>
                              <tbody>
                                {visibleTx.map((tx, i) => (
                                  <tr key={i} className={`${tx.amount < 0 ? "txCreditRow" : ""}${isFee(tx.description) ? " txFeeRow" : ""}`}>
                                    <td className="txDate">{tx.date ?? "—"}</td>
                                    <td className="txDesc">
                                      {isFee(tx.description) && <span className="txFeeBadge">ücret</span>}
                                      {(() => {
                                        const cat = categorizeTransaction(tx.description);
                                        return cat ? (
                                          <span className="txCatBadge" style={{ color: cat.color, borderColor: cat.color + "55", background: cat.color + "18" }}>
                                            {cat.icon} {cat.name}
                                          </span>
                                        ) : null;
                                      })()}
                                      {tx.description}
                                      {getFeeNote(tx.description) && (
                                        <div className="txFeeNote">↳ {getFeeNote(tx.description)}</div>
                                      )}
                                    </td>
                                    <td
                                      className="txAmountCol"
                                      style={{ color: tx.amount < 0 ? "var(--ok)" : undefined }}
                                    >
                                      {tx.amount < 0 ? "+" : ""}
                                      {Math.abs(tx.amount).toLocaleString("tr-TR", { minimumFractionDigits: 2 })}
                                    </td>
                                    <td className="txCurrencyCol">{tx.currency}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    );
                  })}
                      </div>
                    </section>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ─── DOSYALAR (tüm ekler, parse durumu) ─── */}
          {activeTab === "documents" && (
            <div className="docQueuePage">
              <section className="section">
                <p className="muted" style={{ marginBottom: 16 }}>
                  Mail sync ile indirilen <strong>tüm PDF/CSV dosyaları</strong> burada. <strong>Ekstreler</strong>{" "}
                  sekmesinde yalnızca <em>başarılı</em> analizler listelenir; burada{" "}
                  <strong>henüz analiz edilemeyen veya hatalı</strong> ekleri de görürsün (ör. 11 dosya / 9 başarılı → 2
                  satır burada).
                </p>
                <div className="docQueueKpiRow">
                  <div className="docQueueKpi">
                    <span className="docQueueKpiVal">{ingestionStats?.total ?? "—"}</span>
                    <span className="docQueueKpiLbl">Toplam dosya</span>
                  </div>
                  <div className="docQueueKpi docQueueKpiOk">
                    <span className="docQueueKpiVal">{ingestionStats?.parsed ?? "—"}</span>
                    <span className="docQueueKpiLbl">Başarılı analiz</span>
                  </div>
                  <div className="docQueueKpi docQueueKpiWarn">
                    <span className="docQueueKpiVal">{ingestionStats?.parse_failed ?? "—"}</span>
                    <span className="docQueueKpiLbl">Hatalı</span>
                  </div>
                  <div className="docQueueKpi docQueueKpiMuted">
                    <span className="docQueueKpiVal">{ingestionStats?.pending ?? "—"}</span>
                    <span className="docQueueKpiLbl">Bekliyor</span>
                  </div>
                  <div className="docQueueKpi docQueueKpiMuted">
                    <span className="docQueueKpiVal">{ingestionStats?.non_parsed ?? "—"}</span>
                    <span className="docQueueKpiLbl">Başarısız toplam</span>
                  </div>
                </div>
                <div className="filterBar" style={{ marginTop: 18 }}>
                  <span className="muted" style={{ marginRight: 10 }}>Liste:</span>
                  <select
                    className="filterSelect"
                    value={ingestionDocFilter}
                    onChange={(e) => setIngestionDocFilter(e.target.value)}
                  >
                    <option value="all">Tüm dosyalar</option>
                    <option value="non_parsed">Analiz edilmeyen / hatalı / bekleyen</option>
                    <option value="parsed">Sadece başarılı</option>
                    <option value="parse_failed">Sadece hatalı</option>
                  </select>
                </div>
                <div className="docQueueTableWrap">
                  <table className="docQueueTable">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Dosya</th>
                        <th>Tür</th>
                        <th>Durum</th>
                        <th>Banka (tahmin)</th>
                        <th>İşlem sayısı</th>
                        <th>Boyut</th>
                        <th>Notlar</th>
                        <th>Mail konusu</th>
                        <th>Aksiyon</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ingestionDocs.map((row) => {
                        const stLabel =
                          row.parse_status === "parsed"
                            ? "Başarılı"
                            : row.parse_status === "parse_failed"
                              ? "Hata"
                              : row.parse_status === "pending"
                                ? "Bekliyor"
                                : row.parse_status === "unsupported"
                                  ? "Desteklenmiyor"
                                  : row.parse_status;
                        return (
                          <tr key={row.id}>
                            <td className="docQueueMono">{row.id}</td>
                            <td className="docQueueFile">{row.file_name}</td>
                            <td>{row.doc_type}</td>
                            <td>
                              <span
                                className={
                                  row.parse_status === "parsed"
                                    ? "docStatus docStatusOk"
                                    : row.parse_status === "parse_failed"
                                      ? "docStatus docStatusErr"
                                      : "docStatus docStatusMuted"
                                }
                              >
                                {stLabel}
                              </span>
                            </td>
                            <td>{row.bank_name ?? "—"}</td>
                            <td>{row.transaction_count}</td>
                            <td className="docQueueMono">{Math.round(row.file_size_bytes / 1024)} KB</td>
                            <td className="docQueueNotes">{row.parse_notes?.length ? row.parse_notes.join(", ") : "—"}</td>
                            <td className="docQueueSubj">{row.email_subject ?? "—"}</td>
                            <td className="docQueueActions">
                              {row.doc_type === "pdf" && (
                                <a
                                  className="stmtPdfLink"
                                  href={apiUrlPath(`api/statements/${row.id}/pdf`)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                >
                                  PDF
                                </a>
                              )}
                              {row.doc_type === "pdf" && (
                                <button
                                  type="button"
                                  className="stmtReparseBtn"
                                  disabled={isReparsingStatements || reparseStmtId === row.id || !llmReadyForReparse}
                                  title={!llmReadyForReparse ? "AI Parser gerekli" : "Yeniden çöz"}
                                  onClick={() => void handleReparseStatement(row)}
                                >
                                  {reparseStmtId === row.id ? "…" : "↻"}
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {ingestionDocs.length === 0 && (
                    <p className="muted" style={{ padding: "12px 14px" }}>
                      Bu filtreye uygun dosya yok.
                    </p>
                  )}
                </div>
              </section>
            </div>
          )}

          {/* ─── GLOBAL SEARCH ─── */}
          {activeTab === "search" && (
            <div className="pageSearch">
              <div className="searchBarWrap">
                <span className="searchBarIcon">⌕</span>
                <input
                  className="searchBarInput"
                  type="text"
                  placeholder="İşlem ara… örn: Acıbadem, Netflix, Migros"
                  value={globalSearch}
                  onChange={(e) => setGlobalSearch(e.target.value)}
                  autoFocus
                />
                {globalSearch && (
                  <button className="searchBarClear" onClick={() => setGlobalSearch("")}>✕</button>
                )}
              </div>

              {/* Quick filter chips */}
              <div className="searchQuickFilters">
                <span className="searchQuickLabel">Hızlı:</span>
                <button
                  className={`searchQuickChip searchQuickFee${feeMode ? " active" : ""}`}
                  onClick={() => { setFeeMode((v) => !v); setGlobalSearch(""); }}
                >
                  ⚠ Tüm Ücretler
                </button>
                {[
                  { label: "💳 Aidat/Yıllık", q: "aidat yıllık" },
                  { label: "📈 Faiz/KKDF",    q: "faiz kkdf bsmv" },
                  { label: "💵 Nakit Avans",  q: "nakit avans" },
                  { label: "🏦 Komisyon",     q: "komisyon masraf" },
                  { label: "📱 SMS",          q: "sms bildirim" },
                  { label: "🛡 Sigorta",      q: "sigorta emeklilik" },
                  { label: "💸 Gecikme",      q: "gecikme" },
                ].map((chip) => (
                  <button
                    key={chip.q}
                    className={`searchQuickChip${globalSearch === chip.q ? " active" : ""}`}
                    onClick={() => { setFeeMode(false); setGlobalSearch(globalSearch === chip.q ? "" : chip.q); }}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>

              {isSearchActive && searchSummary && (
                <div className="searchSummaryRow">
                  <span className="searchSummaryChip">{searchSummary.txCount} işlem</span>
                  <span className="searchSummaryChip searchSummaryTotal">
                    {feeMode ? "Toplam ücret: " : "Toplam harcama: "}
                    {searchSummary.totalSpend.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL
                  </span>
                  {searchSummary.totalCredit > 0 && (
                    <span className="searchSummaryChip searchSummaryCredit">
                      İade: {searchSummary.totalCredit.toLocaleString("tr-TR", { minimumFractionDigits: 2 })} TL
                    </span>
                  )}
                  <span className="searchSummaryChip">{searchSummary.bankCount} banka</span>
                </div>
              )}

              {isSearchActive && globalSearchResults.length === 0 && (
                <div className="searchEmpty">
                  <div className="searchEmptyIcon">⌕</div>
                  <div>{feeMode ? "Ücret işlemi bulunamadı" : `"${globalSearch}" için sonuç bulunamadı`}</div>
                </div>
              )}

              {!isSearchActive && (
                <div className="searchEmpty">
                  <div className="searchEmptyIcon">⌕</div>
                  <div>Aramak istediğiniz işlem veya mağazayı yazın</div>
                  <div className="searchEmptyHint">Örneğin: Acıbadem, Migros, Netflix, Fuel Oil…</div>
                </div>
              )}

              {globalSearchResults.length > 0 && (
                <div className="searchResultList">
                  {globalSearchResults.map((hit, i) => (
                    <div key={i} className={`searchResultItem${hit.amount < 0 ? " searchResultCredit" : ""}${isFee(hit.description) ? " searchResultFee" : ""}`}>
                      <div className="searchResultLeft">
                        <div className="searchResultDesc">
                          {isFee(hit.description) && <span className="txFeeBadge">ücret</span>}
                          {(() => {
                            const cat = categorizeTransaction(hit.description);
                            return cat ? (
                              <span className="txCatBadge" style={{ color: cat.color, borderColor: cat.color + "55", background: cat.color + "18" }}>
                                {cat.icon} {cat.name}
                              </span>
                            ) : null;
                          })()}
                          {hit.description}
                        </div>
                        {getFeeNote(hit.description) && (
                          <div className="searchResultFeeNote">
                            ↳ {getFeeNote(hit.description)}
                          </div>
                        )}
                        <div className="searchResultMeta">
                          <span className="searchResultBank">{hit.bank_name}</span>
                          {hit.card_number && (
                            <span className="searchResultCard">•••• {hit.card_number.replace(/\s/g, "").slice(-4)}</span>
                          )}
                          {hit.tx_date && <span className="searchResultDate">{hit.tx_date}</span>}
                        </div>
                      </div>
                      <div className={`searchResultAmount${hit.amount < 0 ? " credit" : ""}`}>
                        {hit.amount < 0 ? "+" : ""}
                        {Math.abs(hit.amount).toLocaleString("tr-TR", { minimumFractionDigits: 2 })}
                        <span className="searchResultCurrency"> {hit.currency}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ─── LOGS ─── */}
          {activeTab === "logs" && (
            <div className="logsPage">
              {/* Status cards */}
              <div className="logsStatusRow">
                <div className="logsStatCard">
                  <div className="logsStatCardLabel">Otomatik Sync</div>
                  <div className="logsStatCardValue">
                    {activityLog?.auto_sync.enabled ? (
                      <span className="logStatusBadge logStatusOk">
                        Aktif · her {activityLog.auto_sync.interval_minutes} dk
                      </span>
                    ) : (
                      <span className="logStatusBadge logStatusMuted">Kapalı</span>
                    )}
                  </div>
                  {activityLog?.auto_sync.next_sync_at && activityLog.auto_sync.enabled && (
                    <div className="logsStatCardSub">
                      Sonraki: {(() => {
                        const diff = Math.max(0, Math.round((new Date(activityLog.auto_sync.next_sync_at).getTime() - Date.now()) / 60000));
                        return diff === 0 ? "Az sonra" : `~${diff} dk sonra`;
                      })()}
                    </div>
                  )}
                </div>

                <div className="logsStatCard">
                  <div className="logsStatCardLabel">Son Mail Kontrolü</div>
                  <div className="logsStatCardValue">
                    {activityLog?.auto_sync.last_auto_sync_at ? (
                      <span className="logStatusBadge logStatusInfo">
                        {(() => {
                          const diff = Math.round((Date.now() - new Date(activityLog.auto_sync.last_auto_sync_at!).getTime()) / 60000);
                          if (diff < 1) return "Az önce";
                          if (diff < 60) return `${diff} dk önce`;
                          return `${Math.round(diff / 60)} saat önce`;
                        })()}
                      </span>
                    ) : (
                      <span className="logStatusBadge logStatusMuted">Henüz yok</span>
                    )}
                  </div>
                </div>

                <div className="logsStatCard">
                  <div className="logsStatCardLabel">Belgeler</div>
                  <div className="logsStatCardValue">
                    <span className="logStatusBadge logStatusOk">{activityLog?.stats.parsed_docs ?? "—"} parse edildi</span>
                    {(activityLog?.stats.failed_docs ?? 0) > 0 && (
                      <span className="logStatusBadge logStatusErr" style={{ marginLeft: 6 }}>
                        {activityLog!.stats.failed_docs} hatalı
                      </span>
                    )}
                  </div>
                  <div className="logsStatCardSub">Toplam {activityLog?.stats.total_docs ?? "—"} belge</div>
                </div>
              </div>

              {/* Filter + refresh toolbar */}
              <div className="logsToolbar">
                <div className="logsFilterChips">
                  {(["all", "mail_sync", "document_parse"] as const).map((f) => (
                    <button
                      key={f}
                      type="button"
                      className={`logsFilterChip${activityFilter === f ? " active" : ""}`}
                      onClick={() => setActivityFilter(f)}
                    >
                      {f === "all" ? "Tümü" : f === "mail_sync" ? "✉ Mail Sync" : "📄 Parse"}
                    </button>
                  ))}
                </div>
                <button
                  type="button"
                  className="logsRefreshBtn"
                  onClick={() => setActivityRefreshTick((t) => t + 1)}
                  disabled={isLoadingActivity}
                  title="Yenile"
                >
                  <span style={{ display: "inline-block", transition: "transform 0.4s", transform: isLoadingActivity ? "rotate(360deg)" : "none" }}>↺</span>
                  {isLoadingActivity ? " Yükleniyor…" : " Yenile"}
                </button>
              </div>

              {/* Görünüm + dışa aktarım (tablo / kart / düz metin — Excel’e uygun TSV) */}
              <div className="logsViewBar">
                <div className="logsViewModeBtns" role="tablist" aria-label="Log görünümü">
                  {(["table", "text", "cards"] as const).map((mode) => (
                    <button
                      key={mode}
                      type="button"
                      role="tab"
                      className={`logsViewModeBtn${activityViewMode === mode ? " active" : ""}`}
                      onClick={() => setActivityViewMode(mode)}
                    >
                      {mode === "table" ? "Tablo" : mode === "text" ? "Düz metin" : "Kartlar"}
                    </button>
                  ))}
                </div>
                <div className="logsExportBtns">
                  <button
                    type="button"
                    className="btn btnPrimary"
                    disabled={!activityLog}
                    title="Sekmeyle ayrılmış metin; Excel’e yapıştırılabilir"
                    onClick={async () => {
                      try {
                        const t = buildActivityLogPlainText(activityLog, activityFilter);
                        await copyTextRobust(t);
                        pushLog("info", "system", "Aktivite logu panoya kopyalandı (TSV)");
                      } catch {
                        pushLog("error", "system", "Kopyalama başarısız");
                      }
                    }}
                  >
                    Panoya kopyala
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={!activityLog}
                    onClick={() => {
                      const t = buildActivityLogPlainText(activityLog, activityFilter);
                      downloadTextFile(`ekstrehub-activity-${Date.now()}.txt`, t);
                    }}
                  >
                    .txt indir
                  </button>
                </div>
              </div>

              <div className="logsBody">
                {activityLogError ? (
                  <div className="logsEmpty" style={{ color: "var(--err)", marginBottom: 12 }}>
                    <strong>Yükleme hatası:</strong> {activityLogError}
                    <div className="muted" style={{ marginTop: 8, fontSize: "0.88rem" }}>
                      Ağ veya sunucu sorunu olabilir. <strong>Yenile</strong> ile tekrar deneyin.
                    </div>
                  </div>
                ) : null}
                {!activityLog && isLoadingActivity && (
                  <div className="logsEmpty">Yükleniyor…</div>
                )}
                {activityLog && filteredActivityEvents.length === 0 && (() => {
                  const total = activityLog.activities.length;
                  if (total === 0) {
                    return (
                      <div className="logsEmpty" style={{ textAlign: "left", maxWidth: 520, margin: "0 auto" }}>
                        <p style={{ marginBottom: 10 }}>
                          <strong>Henüz kayıt yok.</strong> Bu ekranda mail taraması ve ekstre işleme özeti görünür.
                        </p>
                        <ul style={{ margin: 0, paddingLeft: 18, color: "var(--text3)", fontSize: "0.9rem" }}>
                          <li>
                            <strong>Mail tarandı mı?</strong> <strong>Mail &amp; Sync</strong> sekmesinde hesabı seçip{" "}
                            <strong>Senkronize Et</strong> çalıştırın veya otomatik sync’i açın.
                          </li>
                          <li>
                            <strong>Sayılar:</strong> <em>Taranan</em> = bakılan e-posta; <em>Kaydedilen</em> = eklenen ekstre
                            eki; <em>Parse</em> = PDF/CSV’nin işlenmesi.
                          </li>
                          <li>
                            Ekstre indirildiyse <strong>Özet</strong> ve <strong>Ekstreler</strong> sekmelerine de bakın.
                          </li>
                        </ul>
                      </div>
                    );
                  }
                  return (
                    <div className="logsEmpty">
                      Bu filtrede kayıt yok.{" "}
                      <button type="button" className="btn" onClick={() => setActivityFilter("all")}>Tümü</button>
                    </div>
                  );
                })()}

                {activityLog && filteredActivityEvents.length > 0 && activityViewMode === "table" && (
                  <div className="logTableWrap">
                    <table className="logDataTable">
                      <thead>
                        <tr>
                          <th>Zaman</th>
                          <th>Tür</th>
                          <th>Durum</th>
                          <th>Kimlik</th>
                          <th>Hesap / dosya</th>
                          <th>Özet</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredActivityEvents.map((ev) => {
                          if (ev.type === "mail_sync") {
                            const acc = [ev.account_label, ev.imap_user].filter(Boolean).join(" · ") || `hesap #${ev.mail_account_id ?? "—"}`;
                            const sum = formatMailSyncSummaryLine(ev);
                            return (
                              <tr key={ev.id}>
                                <td className="logTdMono" title={ev.timestamp ?? ""}>{fmtActivityDate(ev.timestamp)}</td>
                                <td>mail_sync</td>
                                <td><span className="logTdStatus">{ev.status}</span></td>
                                <td className="logTdMono">run#{ev.run_id}</td>
                                <td className="logTdBreak">{acc}</td>
                                <td className="logTdBreak" title="Taranan = yeni mail + tekrar mail + hata. Yeni ekstre = ilk kez kaydedilen PDF/CSV.">
                                  {sum}{ev.notes ? ` · ${ev.notes}` : ""}
                                </td>
                              </tr>
                            );
                          }
                          const evd = ev;
                          const notes = (evd.parse_notes || []).join(", ");
                          const sum = `${evd.transaction_count} işlem · ${(evd.file_size_bytes / 1024).toFixed(0)} KB${notes ? ` · ${notes}` : ""}`;
                          return (
                            <tr key={evd.id} className={evd.status === "parse_failed" ? "logRowErr" : ""}>
                              <td className="logTdMono" title={evd.timestamp ?? ""}>{fmtActivityDate(evd.timestamp)}</td>
                              <td>{evd.doc_type}_parse</td>
                              <td><span className="logTdStatus">{evd.status}</span></td>
                              <td className="logTdMono">doc#{evd.doc_id}</td>
                              <td className="logTdBreak">{evd.bank_name ?? "—"} · {evd.file_name}</td>
                              <td className="logTdBreak">{sum}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {activityLog && filteredActivityEvents.length > 0 && activityViewMode === "text" && (
                  <textarea
                    className="logPlainTextArea"
                    readOnly
                    spellCheck={false}
                    aria-label="Aktivite günlüğü düz metin"
                    value={buildActivityLogPlainText(activityLog, activityFilter)}
                  />
                )}

                {activityLog && filteredActivityEvents.length > 0 && activityViewMode === "cards" && (
                  <div className="logsTimeline">
                    {filteredActivityEvents.map((ev) => {
                      if (ev.type === "mail_sync") {
                        const statusClass = ev.status === "completed" ? "logStatusOk" : ev.status === "running" ? "logStatusInfo" : "logStatusErr";
                        const statusLabel = ev.status === "completed" ? "tamamlandı" : ev.status === "running" ? "çalışıyor" : ev.status === "completed_with_errors" ? "uyarıyla tamamlandı" : "başarısız";
                        return (
                          <div key={ev.id} className="logsItem logsItemSync">
                            <div className="logsItemIcon">✉</div>
                            <div className="logsItemBody">
                              <div className="logsItemHeader">
                                <span className="logsItemType">Mail Sync</span>
                                <span className={`logStatusBadge ${statusClass}`}>{statusLabel}</span>
                                {ev.duration_seconds != null && (
                                  <span className="logsItemMeta">{ev.duration_seconds < 60 ? `${ev.duration_seconds}s` : `${Math.floor(ev.duration_seconds / 60)}m`}</span>
                                )}
                                <span className="logsItemTime" title={ev.timestamp ?? ""}>{fmtActivityDate(ev.timestamp)} · {relActivityAge(ev.timestamp)}</span>
                              </div>
                              {(ev.mail_account_id != null || ev.account_label || ev.imap_user) && (
                                <div style={{ fontSize: "0.78rem", color: "var(--text3)", marginBottom: 6, lineHeight: 1.35 }}>
                                  {ev.mail_account_id != null && <span>Hesap #{ev.mail_account_id}</span>}
                                  {ev.mail_account_id != null && (ev.account_label || ev.imap_user) ? " — " : ""}
                                  {[ev.account_label, ev.imap_user].filter(Boolean).join(" · ")}
                                </div>
                              )}
                              {ev.notes ? (
                                <p className="muted" style={{ fontSize: "0.78rem", margin: "0 0 8px", lineHeight: 1.35 }}>{ev.notes}</p>
                              ) : null}
                              <div className="logsItemDetail" title="Taranan = yeni mail + tekrar mail + hata">
                                <span className="logsChip logsChipNeutral">Taranan: {ev.scanned}</span>
                                <span className="logsChip logsChipNeutral">Yeni mail: {ev.processed}</span>
                                <span className="logsChip logsChipMuted">Tekrar mail: {ev.duplicates}</span>
                                <span className="logsChip logsChipGreen">Yeni ekstre: {ev.saved}</span>
                                {(ev.duplicate_documents ?? 0) > 0 && (
                                  <span className="logsChip logsChipMuted">Tekrar ekstre: {ev.duplicate_documents}</span>
                                )}
                                {(ev.skipped_attachments ?? 0) > 0 && (
                                  <span className="logsChip logsChipMuted">Atlanan ek: {ev.skipped_attachments}</span>
                                )}
                                {ev.failed > 0 && <span className="logsChip logsChipRed">Hata: {ev.failed}</span>}
                              </div>
                            </div>
                          </div>
                        );
                      }
                      const isOk = ev.status === "parsed";
                      const isFailed = ev.status === "parse_failed";
                      const statusClass = isOk ? "logStatusOk" : isFailed ? "logStatusErr" : "logStatusMuted";
                      const statusLabel = isOk ? "parse edildi" : isFailed ? "hatalı" : ev.status === "unsupported" ? "desteklenmiyor" : "bekliyor";
                      return (
                        <div key={ev.id} className={`logsItem logsItemParse${isFailed ? " logsItemFailed" : ""}`}>
                          <div className="logsItemIcon">{ev.doc_type === "pdf" ? "📄" : ev.doc_type === "csv" ? "📊" : "📎"}</div>
                          <div className="logsItemBody">
                            <div className="logsItemHeader">
                              <span className="logsItemType">{ev.doc_type.toUpperCase()} Parse</span>
                              <span className={`logStatusBadge ${statusClass}`}>{statusLabel}</span>
                              {isOk && ev.transaction_count > 0 && (
                                <span className="logsChip logsChipGreen">{ev.transaction_count} işlem</span>
                              )}
                              <span className="logsItemTime" title={ev.timestamp ?? ""}>{fmtActivityDate(ev.timestamp)} · {relActivityAge(ev.timestamp)}</span>
                            </div>
                            <div className="logsItemDetail">
                              {ev.bank_name && <span className="logsChip logsChipBank">{ev.bank_name}</span>}
                              <span className="logsItemFileName" title={ev.email_subject ?? ""}>{ev.file_name}</span>
                              <span className="logsChip logsChipMuted">{(ev.file_size_bytes / 1024).toFixed(0)} KB</span>
                            </div>
                            {ev.parse_notes.length > 0 && (
                              <div className="logsParseNotes">
                                {ev.parse_notes.map((n, i) => (
                                  <span key={i} className={`parseNoteBadge ${n === "llm_parsed" ? "pnLlm" : n === "no_transactions_found" ? "pnWarn" : "pnDefault"}`}>
                                    {n}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ─── MAIL & SYNC ─── */}
          {activeTab === "mail" && (
            <>
              <section className="section">
                <div className="sectionHeader">
                  <h2 className="sectionTitle">Mail Hesapları</h2>
                </div>
                {syncInfo ? <div className="okMsg">{syncInfo}</div> : null}
                {mailAccounts.length > 0 ? (
                  <div className="mailAccountRow">
                    <select
                      className="filterSelect flexGrow"
                      value={selectedMailAccountId ?? ""}
                      onChange={(e) => setSelectedMailAccountId(Number(e.target.value))}
                    >
                      {mailAccounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          #{a.id} {a.account_label} ({a.provider} / {a.auth_mode})
                        </option>
                      ))}
                    </select>
                    <button
                      className="btn btnPrimary"
                      onClick={handleSyncSelectedAccount}
                      disabled={!selectedMailAccountId || isSyncing}
                    >
                      {isSyncing ? "Sync çalışıyor..." : "▶ Sync Başlat"}
                    </button>
                  </div>
                ) : (
                  <p className="muted">Henüz tanımlı mail hesabı yok.</p>
                )}

                {/* Mail account settings panel for selected account */}
                {selectedMailAccountId && (() => {
                  const acct = mailAccounts.find((a) => a.id === selectedMailAccountId);
                  if (!acct) return null;
                  const isEditing = editingMailboxId === acct.id;
                  return (
                    <div className="mailAccountSettings">
                      <div className="mailAccountSettingsRow">
                        <span className="mailAccountSettingsLabel">Posta kutusu</span>
                        {isEditing ? (
                          <div className="mailboxEditInline">
                            <input
                              className="mailboxInput"
                              value={editMailboxValue}
                              onChange={(e) => setEditMailboxValue(e.target.value)}
                              placeholder="INBOX veya [Gmail]/All Mail"
                            />
                            <button
                              className="btn btnPrimary"
                              style={{ fontSize: "0.78rem", padding: "4px 10px" }}
                              onClick={async () => {
                                try {
                                  const updated = await patchMailAccount(acct.id, { mailbox: editMailboxValue });
                                  setMailAccounts((prev) => prev.map((a) => a.id === updated.id ? updated : a));
                                  setEditingMailboxId(null);
                                  setSyncInfo(`Posta kutusu "${updated.mailbox}" olarak güncellendi.`);
                                } catch (e) {
                                  setErrorMessage(String(e));
                                }
                              }}
                            >Kaydet</button>
                            <button
                              className="btn"
                              style={{ fontSize: "0.78rem", padding: "4px 10px" }}
                              onClick={() => setEditingMailboxId(null)}
                            >İptal</button>
                          </div>
                        ) : (
                          <div className="mailboxEditInline">
                            <code className="mailboxCode">{acct.mailbox}</code>
                            <button
                              className="btn"
                              style={{ fontSize: "0.78rem", padding: "4px 10px" }}
                              onClick={() => { setEditingMailboxId(acct.id); setEditMailboxValue(acct.mailbox); }}
                            >Düzenle</button>
                          </div>
                        )}
                      </div>
                      <div className="mailAccountSettingsRow">
                        <span className="mailAccountSettingsLabel">Gmail için önerilen kutular</span>
                        <div className="mailboxPresets">
                          {["INBOX", "[Gmail]/All Mail", "[Gmail]/Promotions", "[Gmail]/Spam"].map((box) => (
                            <button
                              key={box}
                              className={`mailboxPresetBtn${acct.mailbox === box ? " active" : ""}`}
                              onClick={async () => {
                                try {
                                  const updated = await patchMailAccount(acct.id, { mailbox: box });
                                  setMailAccounts((prev) => prev.map((a) => a.id === updated.id ? updated : a));
                                  setSyncInfo(`Posta kutusu "${box}" olarak güncellendi.`);
                                } catch (e) {
                                  setErrorMessage(String(e));
                                }
                              }}
                            >{box}</button>
                          ))}
                        </div>
                      </div>
                      <div className="mailAccountSettingsRow" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                        <span className="mailAccountSettingsLabel">Tarama kapsamı (Gmail’de çok önemli)</span>
                        <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer", fontSize: "0.9rem" }}>
                          <input
                            type="checkbox"
                            checked={acct.unseen_only}
                            style={{ marginTop: 3 }}
                            onChange={async (e) => {
                              try {
                                const updated = await patchMailAccount(acct.id, { unseen_only: e.target.checked });
                                setMailAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
                                setSyncInfo(
                                  updated.unseen_only
                                    ? "Sadece okunmamış (UNSEEN) mailler taranacak."
                                    : "Son N mail taranacak (okunmuşlar dahil). Şimdi «Sync Başlat» ile dene.",
                                );
                              } catch (err) {
                                setErrorMessage(String(err));
                              }
                            }}
                          />
                          <span>
                            <strong>Sadece okunmamış (UNSEEN)</strong>
                            <span className="muted" style={{ display: "block", fontSize: "0.82rem", marginTop: 4, lineHeight: 1.35 }}>
                              Açıkken yalnızca henüz okunmamış postalar alınır. Telefonda veya Gmail’de ekstreyi açtıysan «okunmuş» sayılır ve{" "}
                              <strong>tarama 0</strong> görebilirsin — bu kutuyu kapatıp tekrar sync et.
                            </span>
                          </span>
                        </label>
                      </div>
                      <div className="mailAccountSettingsRow">
                        <span className="mailAccountSettingsLabel">Maksimum mail (son N)</span>
                        <select
                          className="filterSelect"
                          style={{ maxWidth: 140 }}
                          value={acct.fetch_limit}
                          onChange={async (e) => {
                            const n = Number(e.target.value);
                            try {
                              const updated = await patchMailAccount(acct.id, { fetch_limit: n });
                              setMailAccounts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
                              setSyncInfo(`Tarama limiti ${n} mail olarak kaydedildi.`);
                            } catch (err) {
                              setErrorMessage(String(err));
                            }
                          }}
                        >
                          {(() => {
                            const presets = [20, 50, 100, 200];
                            const opts = presets.includes(acct.fetch_limit)
                              ? presets
                              : [acct.fetch_limit, ...presets].sort((a, b) => a - b);
                            return opts.map((n) => (
                              <option key={n} value={n}>
                                {n} mail
                              </option>
                            ));
                          })()}
                        </select>
                      </div>
                      <div className="mailAccountSettingsRow" style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--border, #333)" }}>
                        <button
                          type="button"
                          className="btn"
                          style={{ color: "#e57373", borderColor: "#5c3333" }}
                          disabled={isDeletingMailAccount || isSyncing}
                          onClick={() => handleDeleteMailAccount(acct.id, acct.account_label)}
                        >
                          {isDeletingMailAccount ? "Siliniyor…" : "🗑 Bu mail hesabını sil"}
                        </button>
                      </div>
                    </div>
                  );
                })()}
              </section>

              <section className="section">
                <div className="sectionHeader">
                  <h2 className="sectionTitle">Sync Geçmişi</h2>
                  <select
                    className="filterSelect filterSelectSm"
                    value={runStatusFilter}
                    onChange={(e) => setRunStatusFilter(e.target.value as IngestionRunStatus | "all")}
                  >
                    <option value="all">Tüm durumlar</option>
                    <option value="running">Çalışıyor</option>
                    <option value="completed">Tamamlandı</option>
                    <option value="completed_with_errors">Hata ile tamamlandı</option>
                    <option value="failed">Başarısız</option>
                  </select>
                </div>
                {visibleRuns.length > 0 ? (
                  <div className="runList">
                    {visibleRuns.map((run) => (
                      <div className="runItem" key={run.id}>
                        <div className="runLeft">
                          <span className="runId">Run #{run.id}</span>
                          <span className={statusBadge(run.status)}>{run.status}</span>
                        </div>
                        <div className="runStats">
                          <span className="runStat">Taranan <strong>{run.scanned_messages}</strong></span>
                          <span className="runStat">Kaydedilen <strong>{run.saved_documents}</strong></span>
                          <span className="runStat">Tekrar <strong>{run.duplicate_documents}</strong></span>
                          <span className="runStat">Hata <strong>{run.failed_messages}</strong></span>
                        </div>
                      </div>
                    ))}
                    {nextCursor && (
                      <button className="btn" onClick={loadMoreRuns} disabled={isLoadingMore}>
                        {isLoadingMore ? "Yükleniyor..." : "Daha Fazla"}
                      </button>
                    )}
                  </div>
                ) : (
                  <p className="muted">Run kaydı yok.</p>
                )}
              </section>

              <section className="section">
                <h2 className="sectionTitle" style={{ marginBottom: 14 }}>Yeni Mail Hesabı Ekle</h2>
                <div className="formGrid">
                  <select
                    className="filterSelect"
                    value={formProvider}
                    onChange={(e) => {
                      const v = e.target.value as "gmail" | "outlook" | "custom";
                      setFormProvider(v);
                      if (v !== "gmail") setGmailImapManual(false);
                    }}
                  >
                    <option value="gmail">Gmail</option>
                    <option value="outlook">Outlook / Office 365</option>
                    <option value="custom">Özel IMAP</option>
                  </select>

                  <input className="formInput" placeholder="Hesap adı (örn: Kart Maili)" value={formLabel} onChange={(e) => setFormLabel(e.target.value)} />

                  {formProvider === "gmail" && (
                    <>
                      <p className="muted" style={{ gridColumn: "1 / -1", marginBottom: 0 }}>
                        <strong>Neden Mail uygulaması anahtar sormuyor?</strong> Apple, Google ile kayıtlı kendi OAuth
                        uygulamasını iPhone/Mac’e gömüyor; sen sadece hesabını seçiyorsun. EkstreHub küçük bir üçüncü
                        parti uygulama — Google aynı güvenliği ister: <em>bir kez</em> (ev sunucunda) Client ID/Secret
                        tanımlanır; sonra bu ekrandan kimse anahtar girmez, tıpkı Mail’deki gibi sadece Google hesabını
                        seçersin. Anahtar istemiyorsan: aşağıdan <strong>uygulama şifresi</strong> ile IMAP kullan (Google
                        Cloud gerekmez).
                      </p>
                      {health && !health.gmail_oauth_configured ? (
                        <p
                          className="muted"
                          style={{
                            gridColumn: "1 / -1",
                            margin: "0.35rem 0 0",
                            padding: "0.65rem 0.75rem",
                            borderRadius: 8,
                            border: "1px solid rgba(220, 160, 60, 0.55)",
                            background: "rgba(220, 160, 60, 0.12)",
                            fontSize: "0.9rem",
                          }}
                        >
                          <strong>OAuth yok → Google’a gidilmez.</strong> Aşağıdaki buton artık seni HA içinde
                          döndürmez; önce{" "}
                          <strong>
                            Eklentiler → EkstreHub → Yapılandırma → gmail_oauth_client_id + gmail_oauth_client_secret
                          </strong>{" "}
                          (Google Cloud Console) doldur, kaydet, add-on’u yeniden başlat.
                        </p>
                      ) : null}
                      <button
                        type="button"
                        className="btn btnGoogle"
                        disabled={health === null}
                        style={{ gridColumn: "1 / -1", justifySelf: "start" }}
                        onClick={() => {
                          if (!health?.gmail_oauth_configured) {
                            setErrorMessage(
                              "Google girişi için add-on Yapılandırması’nda gmail_oauth_client_id ve gmail_oauth_client_secret gerekli. " +
                                "Home Assistant → Eklentiler → EkstreHub → Yapılandırma. Google Cloud Console’da OAuth istemcisi oluştur; " +
                                "Yönlendirme URI için bu add-on’un «redirect URI» bilgisini (API: /api/oauth/gmail/redirect-uri) kullan."
                            );
                            pushLog("info", "auth", "Gmail OAuth: add-on’da Client ID/Secret yok.");
                            return;
                          }
                          openOAuthInNewTabOrNavigate(gmailOAuthUrl);
                        }}
                      >
                        {health === null
                          ? "Yükleniyor…"
                          : health.gmail_oauth_configured
                            ? "Gmail’e bağlan (Google’da aç)"
                            : "Önce OAuth’u add-on’da ayarla (Google’a şu an gidilmez)"}
                      </button>
                      <button
                        type="button"
                        className="btn"
                        style={{ fontSize: "0.85rem" }}
                        onClick={() => setGmailImapManual((v) => !v)}
                      >
                        {gmailImapManual ? "▼ Manuel IMAP’i gizle" : "▶ OAuth çalışmıyorsa: uygulama şifresi ile elle ekle"}
                      </button>
                    </>
                  )}

                  {(formProvider !== "gmail" || gmailImapManual) && (
                    <>
                      {formProvider !== "gmail" && (
                        <select
                          className="filterSelect"
                          value={resolvedMailAuthMode}
                          onChange={(e) => setFormAuthMode(e.target.value as "password" | "oauth_gmail")}
                        >
                          <option value="password">Şifre / Uygulama şifresi</option>
                          <option value="oauth_gmail">OAuth refresh token (gelişmiş)</option>
                        </select>
                      )}
                      {formProvider === "gmail" && gmailImapManual && health?.gmail_oauth_configured && (
                        <select
                          className="filterSelect"
                          value={formAuthMode}
                          onChange={(e) => setFormAuthMode(e.target.value as "password" | "oauth_gmail")}
                        >
                          <option value="password">Uygulama şifresi (IMAP)</option>
                          <option value="oauth_gmail">OAuth refresh token</option>
                        </select>
                      )}
                      {formProvider === "gmail" && gmailImapManual && (
                        <p className="muted" style={{ gridColumn: "1 / -1", fontSize: "0.88rem" }}>
                          <strong>Normal Gmail şifren çalışmaz.</strong> Google Hesabı → Güvenlik → 2 adımlı doğrulama →{" "}
                          <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">
                            Uygulama şifreleri
                          </a>{" "}
                          ile 16 karakterlik şifre oluştur; aşağıdaki alana onu yapıştır.{" "}
                          <a href="https://mail.google.com/mail/u/0/#settings/fwdandpop" target="_blank" rel="noopener noreferrer">
                            IMAP erişimi
                          </a>{" "}
                          açık olmalı.
                        </p>
                      )}
                      {formProvider === "custom" && (
                        <input className="formInput" placeholder="IMAP host (örn: imap.catal.net)" value={formImapHost} onChange={(e) => setFormImapHost(e.target.value)} />
                      )}
                      <input
                        className="formInput"
                        placeholder={formProvider === "gmail" ? "Gmail adresin (tam e-posta)" : "E-posta adresi"}
                        value={formImapUser}
                        onChange={(e) => setFormImapUser(e.target.value)}
                      />
                      {resolvedMailAuthMode === "oauth_gmail" ? (
                        <textarea
                          className="formInput"
                          placeholder="OAuth refresh token"
                          value={formRefreshToken}
                          onChange={(e) => setFormRefreshToken(e.target.value)}
                          style={{ minHeight: 72, resize: "vertical" }}
                        />
                      ) : (
                        <input
                          className="formInput"
                          type="password"
                          placeholder={
                            formProvider === "gmail"
                              ? "Google uygulama şifresi (16 karakter)"
                              : "Şifre / Uygulama şifresi"
                          }
                          value={formImapPassword}
                          onChange={(e) => setFormImapPassword(e.target.value)}
                        />
                      )}
                      <input className="formInput" placeholder="Mailbox (varsayılan: INBOX)" value={formMailbox} onChange={(e) => setFormMailbox(e.target.value)} />
                      <button
                        className="btn btnPrimary"
                        onClick={handleCreateMailAccount}
                        disabled={
                          isCreatingAccount ||
                          !formLabel.trim() ||
                          !formImapUser.trim() ||
                          (formProvider === "custom" && !formImapHost.trim()) ||
                          (resolvedMailAuthMode === "password" && !formImapPassword.trim()) ||
                          (resolvedMailAuthMode === "oauth_gmail" && !formRefreshToken.trim())
                        }
                      >
                        {isCreatingAccount ? "Oluşturuluyor..." : "Hesap Ekle"}
                      </button>
                    </>
                  )}
                </div>
              </section>
            </>
          )}

          {/* ─── AYARLAR ─── */}
          {activeTab === "settings" && (
            <>
              <div className="subTabs">
                <button
                  className={`subTab${settingsSubTab === "auto-sync" ? " subTabActive" : ""}`}
                  onClick={() => setSettingsSubTab("auto-sync")}
                >
                  ⏱ Otomatik Sync
                </button>
                <button
                  className={`subTab${settingsSubTab === "ai-parser" ? " subTabActive" : ""}`}
                  onClick={() => setSettingsSubTab("ai-parser")}
                >
                  AI Parser
                </button>
                <button
                  className={`subTab${settingsSubTab === "parser" ? " subTabActive" : ""}`}
                  onClick={() => setSettingsSubTab("parser")}
                >
                  Parser Onay
                </button>
                <button
                  className={`subTab${settingsSubTab === "logs" ? " subTabActive" : ""}`}
                  onClick={() => setSettingsSubTab("logs")}
                >
                  Sistem Logları
                </button>
                <button
                  className={`subTab${settingsSubTab === "system" ? " subTabActive" : ""}`}
                  onClick={() => setSettingsSubTab("system")}
                >
                  Sistem
                </button>
              </div>

              {settingsSubTab === "auto-sync" && (
                <section className="section">
                  <p className="muted" style={{ marginBottom: 20 }}>
                    Sistem, belirlediğin aralıkta mailleri otomatik olarak kontrol eder ve yeni
                    ekstreler varsa parse eder.
                  </p>

                  {/* Enable / disable toggle */}
                  <div className="autoSyncRow">
                    <div>
                      <div className="autoSyncLabel">Otomatik Sync</div>
                      <div className="autoSyncSub">
                        {autoSync?.enabled
                          ? `Her ${autoSync.interval_minutes} dakikada bir kontrol ediyor`
                          : "Devre dışı — sadece manuel sync"}
                      </div>
                    </div>
                    <label className="toggleSwitch">
                      <input
                        type="checkbox"
                        checked={autoSync?.enabled ?? false}
                        onChange={async (e) => {
                          setIsSavingAutoSync(true);
                          try {
                            const updated = await setAutoSync({ enabled: e.target.checked });
                            setAutoSyncState(updated);
                          } catch {
                            /* ignore */
                          } finally {
                            setIsSavingAutoSync(false);
                          }
                        }}
                        disabled={isSavingAutoSync}
                      />
                      <span className="toggleSlider" />
                    </label>
                  </div>

                  {/* Interval selector */}
                  <div className="autoSyncRow" style={{ marginTop: 16 }}>
                    <div className="autoSyncLabel">Kontrol aralığı</div>
                    <select
                      className="filterSelect"
                      value={autoSync?.interval_minutes ?? 60}
                      disabled={isSavingAutoSync}
                      onChange={async (e) => {
                        setIsSavingAutoSync(true);
                        try {
                          const updated = await setAutoSync({ interval_minutes: Number(e.target.value) });
                          setAutoSyncState(updated);
                        } catch {
                          /* ignore */
                        } finally {
                          setIsSavingAutoSync(false);
                        }
                      }}
                    >
                      <option value={5}>5 dakika</option>
                      <option value={15}>15 dakika</option>
                      <option value={30}>30 dakika</option>
                      <option value={60}>1 saat</option>
                      <option value={120}>2 saat</option>
                      <option value={240}>4 saat</option>
                      <option value={480}>8 saat</option>
                    </select>
                  </div>

                  {/* Status info */}
                  <div className="autoSyncStatus">
                    <div className="autoSyncStatusRow">
                      <span className="autoSyncStatusLabel">Son otomatik sync</span>
                      <span className="autoSyncStatusValue">
                        {autoSync?.last_auto_sync_at
                          ? new Date(autoSync.last_auto_sync_at).toLocaleString("tr-TR")
                          : "—"}
                      </span>
                    </div>
                    <div className="autoSyncStatusRow">
                      <span className="autoSyncStatusLabel">Sonraki sync</span>
                      <span className="autoSyncStatusValue">
                        {autoSync?.enabled && autoSync?.next_sync_at
                          ? new Date(autoSync.next_sync_at).toLocaleString("tr-TR")
                          : "—"}
                      </span>
                    </div>
                  </div>

                  {isSavingAutoSync && <p className="muted" style={{ marginTop: 10 }}>Kaydediliyor...</p>}
                </section>
              )}

              {settingsSubTab === "ai-parser" && (
                <section className="section">
                  <p className="muted" style={{ marginBottom: 20 }}>
                    Ekstreler PDF metninden <strong>AI (LLM)</strong> ile çözülür. API URL ve model kayıtlı olmalı.
                    Yerel Ollama CPU&apos;da yavaş olabilir; ChatGPT API önerilir.
                  </p>

                  {llmForm && (
                    <div className="llmSettingsPanel">
                      {/* Enable/Disable toggle */}
                      <div className="autoSyncRow">
                        <div className="autoSyncLabel">
                          AI Parser
                          <div className="autoSyncSub">Kapalıysa LLM çağrılmaz (yeni ekstreler boş kalır)</div>
                        </div>
                        <label className="toggle">
                          <input
                            type="checkbox"
                            checked={llmForm.enabled}
                            onChange={(e) => setLlmForm((f) => f && { ...f, enabled: e.target.checked })}
                          />
                          <span className="slider" />
                        </label>
                      </div>

                      {/* Provider selection */}
                      <div className="llmRow">
                        <label className="llmLabel">Sağlayıcı</label>
                        <div className="llmProviderBtns">
                          {(["openai", "ollama", "custom"] as const).map((p) => (
                            <button
                              key={p}
                              className={`llmProviderBtn${llmForm.provider === p ? " active" : ""}`}
                              onClick={() => {
                                const defaults = llmSettings?.provider_defaults[p];
                                setLlmForm((f) => f && {
                                  ...f,
                                  provider: p,
                                  api_url: defaults?.llm_api_url ?? f.api_url,
                                  model: defaults?.llm_model ?? f.model,
                                  timeout: defaults?.llm_timeout_seconds ?? f.timeout,
                                });
                                setLlmTestResult(null);
                              }}
                            >
                              {p === "openai" ? "ChatGPT (OpenAI)" : p === "ollama" ? "Ollama (Yerel)" : "Özel API"}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* API URL */}
                      <div className="llmRow">
                        <label className="llmLabel">API URL</label>
                        <input
                          className="llmInput"
                          value={llmForm.api_url}
                          onChange={(e) => setLlmForm((f) => f && { ...f, api_url: e.target.value })}
                          placeholder="https://api.openai.com/v1"
                        />
                      </div>

                      {/* API Key */}
                      <div className="llmRow">
                        <label className="llmLabel">
                          API Anahtarı
                          {llmSettings?.llm_api_key_set && (
                            <span className="llmKeySet"> ✓ kayıtlı ({llmSettings.llm_api_key_masked})</span>
                          )}
                        </label>
                        <input
                          className="llmInput"
                          type="password"
                          value={llmForm.api_key}
                          onChange={(e) => setLlmForm((f) => f && { ...f, api_key: e.target.value })}
                          placeholder={llmSettings?.llm_api_key_set ? "Değiştirmek için yeni anahtar gir" : "sk-..."}
                        />
                      </div>

                      {/* Model */}
                      <div className="llmRow">
                        <label className="llmLabel">Model</label>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                          <input
                            className="llmInput"
                            value={llmForm.model}
                            onChange={(e) => setLlmForm((f) => f && { ...f, model: e.target.value })}
                            placeholder="gpt-4o-mini"
                            style={{ flex: "1 1 160px" }}
                          />
                          {llmForm.provider === "openai" && (
                            <div className="llmModelPresets">
                              {["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"].map((m) => (
                                <button
                                  key={m}
                                  className={`llmModelBtn${llmForm.model === m ? " active" : ""}`}
                                  onClick={() => setLlmForm((f) => f && { ...f, model: m })}
                                >
                                  {m}
                                </button>
                              ))}
                            </div>
                          )}
                          {llmForm.provider === "ollama" && (
                            <div className="llmModelPresets">
                              {["qwen2.5:7b", "llama3.1:8b", "mistral:7b"].map((m) => (
                                <button
                                  key={m}
                                  className={`llmModelBtn${llmForm.model === m ? " active" : ""}`}
                                  onClick={() => setLlmForm((f) => f && { ...f, model: m })}
                                >
                                  {m}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Timeout */}
                      <div className="llmRow">
                        <label className="llmLabel">Zaman aşımı (sn)</label>
                        <input
                          className="llmInput"
                          type="number"
                          min={5}
                          max={300}
                          value={llmForm.timeout}
                          onChange={(e) => setLlmForm((f) => f && { ...f, timeout: Number(e.target.value) })}
                          style={{ width: 90 }}
                        />
                      </div>

                      {/* Hybrid threshold */}
                      <div className="llmRow">
                        <label className="llmLabel">
                          AI eşiği (işlem sayısı)
                          <span style={{ display: "block", fontSize: "0.78em", opacity: 0.6, fontWeight: 400 }}>
                            Regex bu sayıdan az bulursa AI da çalışır
                          </span>
                        </label>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <input
                            type="range"
                            min={0}
                            max={20}
                            step={1}
                            value={llmForm.min_tx_threshold}
                            onChange={(e) => setLlmForm((f) => f && { ...f, min_tx_threshold: Number(e.target.value) })}
                            style={{ width: 140 }}
                          />
                          <span style={{ minWidth: 32, textAlign: "right", fontWeight: 600 }}>
                            {llmForm.min_tx_threshold === 0 ? "Kapalı" : `< ${llmForm.min_tx_threshold}`}
                          </span>
                        </div>
                      </div>

                      {/* Buttons */}
                      <div className="llmActions">
                        <button
                          className="btn btnPrimary"
                          disabled={isSavingLlm}
                          onClick={async () => {
                            setIsSavingLlm(true);
                            setLlmTestResult(null);
                            try {
                              const patch: Record<string, unknown> = {
                                llm_provider: llmForm.provider,
                                llm_api_url: llmForm.api_url,
                                llm_model: llmForm.model,
                                llm_timeout_seconds: llmForm.timeout,
                                llm_enabled: llmForm.enabled,
                                llm_min_tx_threshold: llmForm.min_tx_threshold,
                              };
                              if (llmForm.api_key) patch.llm_api_key = llmForm.api_key;
                              const updated = await patchLlmSettings(patch);
                              setLlmSettings(updated);
                              setLlmForm((f) => f && { ...f, api_key: "" });
                              setSyncInfo("AI parser ayarları kaydedildi.");
                            } catch (e) {
                              setErrorMessage(String(e));
                            } finally {
                              setIsSavingLlm(false);
                            }
                          }}
                        >
                          {isSavingLlm ? "Kaydediliyor…" : "Kaydet"}
                        </button>
                        <button
                          className="btn"
                          disabled={isTestingLlm || isSavingLlm}
                          onClick={async () => {
                            setIsTestingLlm(true);
                            setLlmTestResult(null);
                            try {
                              // Auto-save settings before testing
                              const patch: Record<string, unknown> = {
                                llm_provider: llmForm.provider,
                                llm_api_url: llmForm.api_url,
                                llm_model: llmForm.model,
                                llm_timeout_seconds: llmForm.timeout,
                                llm_enabled: llmForm.enabled,
                                llm_min_tx_threshold: llmForm.min_tx_threshold,
                              };
                              if (llmForm.api_key) patch.llm_api_key = llmForm.api_key;
                              const updated = await patchLlmSettings(patch);
                              setLlmSettings(updated);
                              setLlmForm((f) => f && { ...f, api_key: "" });
                              const r = await testLlmConnection();
                              setLlmTestResult(r);
                            } catch (err) {
                              setLlmTestResult({ ok: false, detail: err instanceof Error ? err.message : String(err) });
                            } finally {
                              setIsTestingLlm(false);
                            }
                          }}
                        >
                          {isTestingLlm ? "Test ediliyor…" : "Bağlantı Testi"}
                        </button>
                      </div>

                      {/* Test result */}
                      {llmTestResult && (
                        <div className={`llmTestResult ${llmTestResult.ok ? "llmTestOk" : "llmTestFail"}`}>
                          {llmTestResult.ok
                            ? `✓ Bağlantı başarılı — model: ${llmSettings?.llm_model} — yanıt: "${llmTestResult.reply}"`
                            : `✗ Bağlantı başarısız: ${llmTestResult.detail}`}
                        </div>
                      )}

                      {/* Re-parse existing PDFs after enabling LLM */}
                      <div className="llmInfoBox" style={{ marginTop: 16 }}>
                        <strong>AI’yi sonradan açtıysan:</strong> Eski ekstreler otomatik yeniden işlenmez.
                        Mailden PDF tekrar alınır ve güncel LLM ayarlarıyla parse edilir (IMAP gerekir).
                        Her ekstre <strong>ayrı istekte</strong> işlenir (proxy zaman aşımı / «Load failed» önlenir).
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 12 }}>
                          <button
                            type="button"
                            className="btn btnPrimary"
                            disabled={
                              isReparsingStatements
                              || !(llmForm?.api_url?.trim() || llmSettings?.llm_api_url?.trim())
                            }
                            title={
                              !(llmForm?.api_url?.trim() || llmSettings?.llm_api_url?.trim())
                                ? "Önce API URL gir ve Kaydet"
                                : undefined
                            }
                            onClick={async () => {
                              setIsReparsingStatements(true);
                              setReparseSummary(null);
                              try {
                                const patch: Record<string, unknown> = {
                                  llm_provider: llmForm!.provider,
                                  llm_api_url: llmForm!.api_url,
                                  llm_model: llmForm!.model,
                                  llm_timeout_seconds: llmForm!.timeout,
                                  llm_enabled: llmForm!.enabled,
                                  llm_min_tx_threshold: llmForm!.min_tx_threshold,
                                };
                                if (llmForm!.api_key) patch.llm_api_key = llmForm!.api_key;
                                await patchLlmSettings(patch);
                                const list = await getStatements({ limit: 200 });
                                const ids = list.items
                                  .filter((it) =>
                                    it.transaction_count === 0
                                    || (it.parse_notes || []).some((n) => /llm|no_transaction|required/i.test(n)),
                                  )
                                  .map((it) => it.id);
                                if (ids.length === 0) {
                                  setReparseSummary("Yeniden işlenecek boş ekstre bulunamadı.");
                                  await reloadCoreData();
                                  return;
                                }
                                let ok = 0;
                                let fail = 0;
                                for (let i = 0; i < ids.length; i++) {
                                  const id = ids[i];
                                  setReparseSummary(`İşleniyor ${i + 1}/${ids.length} (ekstre #${id})…`);
                                  try {
                                    const r = await reparseStatements("selected", [id]);
                                    const row = r.results?.[0];
                                    if (row?.ok) ok += 1;
                                    else fail += 1;
                                  } catch {
                                    fail += 1;
                                  }
                                }
                                setReparseSummary(`Bitti: ${ok} başarılı, ${fail} sorunlu / ${ids.length} ekstre.`);
                                await reloadCoreData();
                                setSyncInfo("Ekstreler yeniden parse edildi; Özet ve Ekstreler sekmesine bak.");
                              } catch (e) {
                                setErrorMessage(formatReparseFetchError(e));
                              } finally {
                                setIsReparsingStatements(false);
                              }
                            }}
                          >
                            {isReparsingStatements ? "İşleniyor…" : "Boş / hatalı ekstreleri yeniden çöz"}
                          </button>
                          <button
                            type="button"
                            className="btn"
                            disabled={
                              isReparsingStatements
                              || !(llmForm?.api_url?.trim() || llmSettings?.llm_api_url?.trim())
                            }
                            onClick={async () => {
                              if (!window.confirm("Tüm PDF ekstreler yeniden LLM ile işlenecek (max 50, tek tek). Devam?")) return;
                              setIsReparsingStatements(true);
                              setReparseSummary(null);
                              try {
                                const patch: Record<string, unknown> = {
                                  llm_provider: llmForm!.provider,
                                  llm_api_url: llmForm!.api_url,
                                  llm_model: llmForm!.model,
                                  llm_timeout_seconds: llmForm!.timeout,
                                  llm_enabled: llmForm!.enabled,
                                  llm_min_tx_threshold: llmForm!.min_tx_threshold,
                                };
                                if (llmForm!.api_key) patch.llm_api_key = llmForm!.api_key;
                                await patchLlmSettings(patch);
                                const list = await getStatements({ limit: 200 });
                                const ids = list.items.map((it) => it.id).slice(0, 50);
                                if (ids.length === 0) {
                                  setReparseSummary("İşlenecek ekstre yok.");
                                  return;
                                }
                                let ok = 0;
                                let fail = 0;
                                for (let i = 0; i < ids.length; i++) {
                                  const id = ids[i];
                                  setReparseSummary(`İşleniyor ${i + 1}/${ids.length} (ekstre #${id})…`);
                                  try {
                                    const r = await reparseStatements("selected", [id]);
                                    const row = r.results?.[0];
                                    if (row?.ok) ok += 1;
                                    else fail += 1;
                                  } catch {
                                    fail += 1;
                                  }
                                }
                                setReparseSummary(`Bitti: ${ok} başarılı, ${fail} sorunlu / ${ids.length} ekstre.`);
                                await reloadCoreData();
                                setSyncInfo("Tüm seçilen PDF ekstreler yeniden işlendi.");
                              } catch (e) {
                                setErrorMessage(formatReparseFetchError(e));
                              } finally {
                                setIsReparsingStatements(false);
                              }
                            }}
                          >
                            Tüm PDF’leri yeniden çöz (max 50)
                          </button>
                          <button
                            type="button"
                            className="btn"
                            disabled={
                              isReparsingStatements
                              || !(llmForm?.api_url?.trim() || llmSettings?.llm_api_url?.trim())
                            }
                            onClick={async () => {
                              if (!window.confirm("Kredi kartı dışı olabilecek ekstreler yeniden denenecek. Devam?")) return;
                              setIsReparsingStatements(true);
                              setReparseSummary(null);
                              try {
                                const patch: Record<string, unknown> = {
                                  llm_provider: llmForm!.provider,
                                  llm_api_url: llmForm!.api_url,
                                  llm_model: llmForm!.model,
                                  llm_timeout_seconds: llmForm!.timeout,
                                  llm_enabled: llmForm!.enabled,
                                  llm_min_tx_threshold: llmForm!.min_tx_threshold,
                                };
                                if (llmForm!.api_key) patch.llm_api_key = llmForm!.api_key;
                                await patchLlmSettings(patch);
                                const list = await getStatements({ limit: 200 });
                                const ids = list.items
                                  .filter((it) => isLikelyNonCardStatement(it))
                                  .map((it) => it.id)
                                  .slice(0, 50);
                                if (ids.length === 0) {
                                  setReparseSummary("Şüpheli kredi kartı dışı kayıt bulunamadı.");
                                  return;
                                }
                                let cleaned = 0;
                                let ok = 0;
                                let fail = 0;
                                for (let i = 0; i < ids.length; i++) {
                                  const id = ids[i];
                                  setReparseSummary(`İşleniyor ${i + 1}/${ids.length} (ekstre #${id})…`);
                                  try {
                                    const r = await reparseStatements("selected", [id]);
                                    const row = r.results?.[0];
                                    if (row?.error === "non_credit_card_document") cleaned += 1;
                                    else if (row?.ok) ok += 1;
                                    else fail += 1;
                                  } catch {
                                    fail += 1;
                                  }
                                }
                                setReparseSummary(
                                  `Bitti: ${cleaned} ekstre dışı temizlendi, ${ok} yeniden parse, ${fail} sorunlu / ${ids.length} ekstre.`
                                );
                                await reloadCoreData();
                                setSyncInfo("Şüpheli kredi kartı dışı kayıtlar yeniden değerlendirildi.");
                              } catch (e) {
                                setErrorMessage(formatReparseFetchError(e));
                              } finally {
                                setIsReparsingStatements(false);
                              }
                            }}
                          >
                            Kredi kartı dışı olabilecekleri temizle (max 50)
                          </button>
                        </div>
                        {reparseSummary && (
                          <p className="muted" style={{ marginTop: 10, fontSize: "0.88rem" }}>{reparseSummary}</p>
                        )}
                      </div>

                      {/* Info box for OpenAI */}
                      {llmForm.provider === "openai" && (
                        <div className="llmInfoBox">
                          <strong>ChatGPT API kullanımı:</strong> platform.openai.com adresinden API anahtarı oluşturun.
                          <code>gpt-4o-mini</code> modeli ucuz ve hızlıdır (~$0.002/ekstre). API anahtarı sunucuda
                          şifreli saklanır, tarayıcıya gönderilmez.
                        </div>
                      )}
                    </div>
                  )}
                </section>
              )}

              {settingsSubTab === "parser" && (
                <section className="section">
                  <p className="muted" style={{ marginBottom: 14 }}>
                    Ekstre formatı değiştiğinde parser güncelleme istekleri buraya düşer.
                  </p>
                  <div className="filterBar">
                    <select className="filterSelect" value={parserStatusFilter} onChange={(e) => setParserStatusFilter(e.target.value as "pending" | "approved" | "rejected")}>
                      <option value="pending">Bekleyen</option>
                      <option value="approved">Onaylanan</option>
                      <option value="rejected">Reddedilen</option>
                    </select>
                    <button className="btn" onClick={() => loadParserChanges(parserStatusFilter)} disabled={isLoadingParser}>
                      {isLoadingParser ? "Yükleniyor..." : "Yenile"}
                    </button>
                  </div>
                  {parserChanges.length === 0 ? (
                    <div className="emptyState">
                      <p className="emptyIcon">✓</p>
                      <p className="emptyTitle">Bekleyen değişiklik yok</p>
                    </div>
                  ) : (
                    <div className="runList">
                      {parserChanges.map((change) => (
                        <div className="runItem runItemCol" key={change.id}>
                          <div className="runLeft">
                            <span className="runId">#{change.id}</span>
                            <span className="badge badgeMuted">{change.status}</span>
                            <span className="muted">{change.bank_name || "Bilinmiyor"}</span>
                          </div>
                          <p className="muted" style={{ fontSize: "0.82rem" }}>{change.reason || "—"}</p>
                          <div className="rowActions">
                            <button className="btn" onClick={() => handleParserDecision(change.id, "approve")} disabled={activeParserActionId === change.id}>Onayla</button>
                            <button className="btn" onClick={() => handleParserDecision(change.id, "reject")} disabled={activeParserActionId === change.id}>Reddet</button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </section>
              )}

              {settingsSubTab === "logs" && (
                <section className="section">
                  <p className="muted" style={{ marginBottom: 12, fontSize: "0.88rem" }}>
                    Bu oturumda tarayıcıda toplanan olaylar. <strong>Loglar</strong> sekmesindeki sunucu aktivitesi ayrıdır.
                    Panoya kopyala = TSV (tab ile ayrılmış); Excel’e yapıştırılabilir.
                  </p>
                  <div className="filterBar" style={{ marginBottom: 10 }}>
                    <select className="filterSelect" value={logLevelFilter} onChange={(e) => setLogLevelFilter(e.target.value as "all" | UiLogLevel)}>
                      <option value="all">Tüm seviyeler</option>
                      <option value="info">info</option>
                      <option value="error">error</option>
                    </select>
                    <select className="filterSelect" value={logCategoryFilter} onChange={(e) => setLogCategoryFilter(e.target.value as "all" | UiLogCategory)}>
                      <option value="all">Tüm kategoriler</option>
                      <option value="system">system</option>
                      <option value="auth">auth</option>
                      <option value="mail">mail</option>
                      <option value="parser">parser</option>
                      <option value="db">db</option>
                    </select>
                    <input className="searchInput" placeholder="Ara..." value={logSearch} onChange={(e) => setLogSearch(e.target.value)} />
                  </div>
                  <div className="logActions">
                    <button type="button" className="btn" onClick={() => setUiLogs([])}>Temizle</button>
                    <button
                      type="button"
                      className="btn btnPrimary"
                      onClick={async () => {
                        const text = buildClientLogsPlainText(visibleLogs);
                        try {
                          await copyTextRobust(text);
                          pushLog("info", "system", "İstemci logları panoya kopyalandı (TSV)");
                        } catch {
                          pushLog("error", "system", "Kopyalama başarısız");
                        }
                      }}
                    >
                      Panoya kopyala (TSV)
                    </button>
                    <button
                      type="button"
                      className="btn"
                      onClick={() => {
                        const text = buildClientLogsPlainText(visibleLogs);
                        downloadTextFile(`ekstrehub-client-logs-${Date.now()}.txt`, text);
                      }}
                    >
                      .txt indir
                    </button>
                  </div>
                  <div className="clientLogTableWrap">
                    {visibleLogs.length === 0 ? (
                      <p className="muted" style={{ padding: "12px 14px" }}>Log kaydı yok.</p>
                    ) : (
                      <table className="clientLogTable">
                        <thead>
                          <tr>
                            <th>Zaman</th>
                            <th>Seviye</th>
                            <th>Kategori</th>
                            <th>İstek</th>
                            <th>Mesaj</th>
                          </tr>
                        </thead>
                        <tbody>
                          {visibleLogs.map((entry) => (
                            <tr key={entry.id} className={entry.level === "error" ? "logRowErr" : ""}>
                              <td className="logTdMono">{entry.at.replace("T", " ").replace("Z", "")}</td>
                              <td><span className={`logLevel logLevel-${entry.level}`}>{entry.level}</span></td>
                              <td>{entry.category}</td>
                              <td className="logTdMono">{entry.requestId ?? "—"}</td>
                              <td className="logTdBreak clientLogMsg">{entry.message}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </section>
              )}

              {settingsSubTab === "system" && (
                <section className="section">
                  <div className="dangerZone">
                    <h3 className="dangerZoneTitle">Veriyi sıfırla</h3>
                    <p className="muted" style={{ marginBottom: 12 }}>
                      Tüm <strong>ekstre kayıtları</strong>, <strong>işlenmiş mail kayıtları</strong>,{" "}
                      <strong>sync geçmişi</strong>, <strong>öğrenilmiş parser kuralları</strong> ve{" "}
                      <strong>denetim logları</strong> veritabanından silinir.
                    </p>
                    <p className="muted" style={{ marginBottom: 16 }}>
                      <strong>Korunur:</strong> mail hesapları (Gmail/IMAP), AI Parser ayarları, otomatik sync ayarı.
                    </p>
                    <button
                      type="button"
                      className="btn dangerOutlineBtn"
                      onClick={() => {
                        setSystemResetInput("");
                        setSystemResetOpen(true);
                      }}
                    >
                      Sıfırlamayı başlat…
                    </button>
                  </div>

                  <div className="testZone" style={{ marginTop: 22 }}>
                    <h3 className="testZoneTitle">Aynı mailleri yeniden indirmek</h3>
                    <p className="muted" style={{ marginBottom: 12 }}>
                      Sadece <strong>ekstreleri silmek</strong> yetmez: veritabanında{" "}
                      <strong>işlenmiş mail kaydı</strong> (<code className="inlineCode">Message-ID</code>) kalır.
                      Sync aynı mesajları <strong>tekrar</strong> sayar, PDF tekrar eklenmez. Kutudaki ekstreleri
                      baştan çekmek için aşağıdaki önbelleği temizleyin; ardından{" "}
                      <strong>Mail ile senkronize et</strong> çalıştırın.
                    </p>
                    <p className="muted" style={{ marginBottom: 14 }}>
                      <strong>Korunur:</strong> öğrenilmiş parser kuralları, denetim logları, mail hesapları, AI ayarları.
                      Tam veri silmek için yukarıdaki <strong>SIFIRLA</strong> kullanın.
                    </p>
                    <button
                      type="button"
                      className="btn testZoneBtn"
                      onClick={() => {
                        setClearEmailInput("");
                        setClearEmailOpen(true);
                      }}
                    >
                      Posta önbelleğini temizle (onaylı)…
                    </button>
                  </div>

                  <div className="testZone" style={{ marginTop: 22 }}>
                    <h3 className="testZoneTitle">Test: öğrenilmiş kuralları sil</h3>
                    <p className="muted" style={{ marginBottom: 12 }}>
                      Veritabanındaki <strong>tüm banka regex kuralları</strong> silinir; ekstre ve mail kayıtları{" "}
                      <strong>kalır</strong>. Sonraki işlemde önce LLM (veya yeni öğrenme) kullanılır.
                    </p>
                    <p className="muted" style={{ marginBottom: 14 }}>
                      Yeniden parse için: <strong>AI Parser</strong> → «Boş / hatalı ekstreleri yeniden çöz» veya{" "}
                      <strong>Ekstreler</strong> → «↻ Yeniden çöz».
                    </p>
                    <button
                      type="button"
                      className="btn testZoneBtn"
                      onClick={() => {
                        setClearLearnedInput("");
                        setClearLearnedOpen(true);
                      }}
                    >
                      Kuralları sil (onaylı)…
                    </button>
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── System reset confirm (type SIFIRLA) ── */}
      {systemResetOpen && (
        <div
          className="modalOverlay"
          onClick={() => !isResettingSystem && setSystemResetOpen(false)}
        >
          <div className="confirmDialog" onClick={(e) => e.stopPropagation()}>
            <div className="confirmDialogIcon">⚠</div>
            <div className="confirmDialogTitle">Emin misin?</div>
            <div className="confirmDialogBody" style={{ textAlign: "left" }}>
              Bu işlem <strong>geri alınamaz</strong>. Aşağıya tam olarak{" "}
              <code className="inlineCode">{RESET_INGESTION_CONFIRM_PHRASE}</code> yaz, sonra onayla.
              <label className="systemResetLabel" htmlFor="system-reset-confirm">
                Onay metni
              </label>
              <input
                id="system-reset-confirm"
                className="systemResetInput"
                type="text"
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
                placeholder={RESET_INGESTION_CONFIRM_PHRASE}
                value={systemResetInput}
                onChange={(e) => setSystemResetInput(e.target.value)}
                disabled={isResettingSystem}
              />
            </div>
            <div className="confirmDialogActions">
              <button
                type="button"
                className="confirmBtnCancel"
                disabled={isResettingSystem}
                onClick={() => setSystemResetOpen(false)}
              >
                İptal
              </button>
              <button
                type="button"
                className="confirmBtnDelete"
                disabled={
                  isResettingSystem
                  || systemResetInput !== RESET_INGESTION_CONFIRM_PHRASE
                }
                onClick={() => void executeSystemReset()}
              >
                {isResettingSystem ? "Sıfırlanıyor…" : "Evet, sıfırla"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Clear email ingestion cache (type POSTA) ── */}
      {clearEmailOpen && (
        <div
          className="modalOverlay"
          onClick={() => !isClearingEmail && setClearEmailOpen(false)}
        >
          <div className="confirmDialog" onClick={(e) => e.stopPropagation()}>
            <div className="confirmDialogIcon">📧</div>
            <div className="confirmDialogTitle">Posta işleme önbelleğini sil?</div>
            <div className="confirmDialogBody" style={{ textAlign: "left" }}>
              Tüm <strong>ekstre kayıtları</strong>, <strong>işlenmiş mail kayıtları</strong> ve{" "}
              <strong>sync geçmişi</strong> silinir; aynı IMAP mesajları bir sonraki sync’te yeniden işlenir.
              Onay için tam olarak{" "}
              <code className="inlineCode">{CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE}</code> yaz.
              <label className="systemResetLabel" htmlFor="clear-email-confirm">
                Onay metni
              </label>
              <input
                id="clear-email-confirm"
                className="systemResetInput"
                type="text"
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
                placeholder={CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE}
                value={clearEmailInput}
                onChange={(e) => setClearEmailInput(e.target.value)}
                disabled={isClearingEmail}
              />
            </div>
            <div className="confirmDialogActions">
              <button
                type="button"
                className="confirmBtnCancel"
                disabled={isClearingEmail}
                onClick={() => setClearEmailOpen(false)}
              >
                İptal
              </button>
              <button
                type="button"
                className="confirmBtnDelete"
                disabled={
                  isClearingEmail
                  || clearEmailInput !== CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE
                }
                onClick={() => void executeClearEmailIngestionCache()}
              >
                {isClearingEmail ? "Temizleniyor…" : "Evet, önbelleği temizle"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Clear learned rules confirm (type KURALLAR) ── */}
      {clearLearnedOpen && (
        <div
          className="modalOverlay"
          onClick={() => !isClearingLearned && setClearLearnedOpen(false)}
        >
          <div className="confirmDialog" onClick={(e) => e.stopPropagation()}>
            <div className="confirmDialogIcon">📋</div>
            <div className="confirmDialogTitle">Öğrenilmiş kuralları sil?</div>
            <div className="confirmDialogBody" style={{ textAlign: "left" }}>
              Onay için tam olarak{" "}
              <code className="inlineCode">{CLEAR_LEARNED_RULES_CONFIRM_PHRASE}</code> yaz.
              <label className="systemResetLabel" htmlFor="clear-learned-confirm">
                Onay metni
              </label>
              <input
                id="clear-learned-confirm"
                className="systemResetInput"
                type="text"
                autoComplete="off"
                autoCorrect="off"
                spellCheck={false}
                placeholder={CLEAR_LEARNED_RULES_CONFIRM_PHRASE}
                value={clearLearnedInput}
                onChange={(e) => setClearLearnedInput(e.target.value)}
                disabled={isClearingLearned}
              />
            </div>
            <div className="confirmDialogActions">
              <button
                type="button"
                className="confirmBtnCancel"
                disabled={isClearingLearned}
                onClick={() => setClearLearnedOpen(false)}
              >
                İptal
              </button>
              <button
                type="button"
                className="confirmBtnDelete"
                disabled={
                  isClearingLearned
                  || clearLearnedInput !== CLEAR_LEARNED_RULES_CONFIRM_PHRASE
                }
                onClick={() => void executeClearLearnedRules()}
              >
                {isClearingLearned ? "Siliniyor…" : "Evet, kuralları sil"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete confirm dialog ── */}
      {deleteConfirm && (
        <div className="modalOverlay" onClick={() => setDeleteConfirm(null)}>
          <div className="confirmDialog" onClick={(e) => e.stopPropagation()}>
            <div className="confirmDialogIcon">🗑</div>
            <div className="confirmDialogTitle">Silmek istediğine emin misin?</div>
            <div className="confirmDialogBody">
              <strong>{deleteConfirm.label}</strong> silinecek.
              <br />
              <span className="confirmDialogNote">Bu işlem geri alınamaz. Ekstre tekrar sync edilebilir.</span>
            </div>
            <div className="confirmDialogActions">
              <button
                className="confirmBtnCancel"
                onClick={() => setDeleteConfirm(null)}
              >
                İptal
              </button>
              <button
                className="confirmBtnDelete"
                disabled={isDeletingStmts}
                onClick={executeDeleteStatements}
              >
                {isDeletingStmts ? "Siliniyor…" : "Evet, Sil"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Mobile bottom nav ── */}
      <nav className="bottomNav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`bottomNavItem${activeTab === item.id ? " navActive" : ""}`}
            onClick={() => setActiveTab(item.id)}
          >
            <span className="bottomNavIcon">{item.icon}</span>
            <span className="bottomNavLabel">{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
