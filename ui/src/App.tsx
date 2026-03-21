import { useEffect, useMemo, useState } from "react";

import {
  approveParserChange,
  createMailAccount,
  deleteMailAccount,
  apiUrlPath,
  getAutoSync,
  getParserChanges,
  getHealth,
  getIngestionRuns,
  getMailAccounts,
  getStatements,
  getLlmSettings,
  patchLlmSettings,
  testLlmConnection,
  patchMailAccount,
  rejectParserChange,
  setAutoSync,
  triggerMailSync,
  getActivityLog,
  deleteStatement,
  deleteStatementsBulk,
  type AutoSyncSettings,
  type LlmSettings,
  type HealthResponse,
  type IngestionRunItem,
  type IngestionRunStatus,
  type MailAccount,
  type ParserChangeItem,
  type StatementItem,
  type ActivityLogResponse,
  type ActivityEvent,
} from "./lib/api";

type LoadState = "idle" | "loading" | "success" | "error";
type AppTab = "dashboard" | "statements" | "search" | "mail" | "settings" | "logs";
type SettingsSubTab = "parser" | "logs" | "auto-sync" | "ai-parser";
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
  { id: "search", icon: "⌕", label: "Ara" },
  { id: "logs", icon: "◎", label: "Loglar" },
  { id: "mail", icon: "✉", label: "Mail & Sync" },
  { id: "settings", icon: "◈", label: "Ayarlar" },
];

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
  const [formImapUser, setFormImapUser] = useState("");
  const [formImapPassword, setFormImapPassword] = useState("");
  const [formRefreshToken, setFormRefreshToken] = useState("");
  const [formMailbox, setFormMailbox] = useState("INBOX");
  const [formImapHost, setFormImapHost] = useState("");
  /** Gmail'de Mail.app gibi önce OAuth; bunu açınca IMAP + uygulama şifresi formu görünür. */
  const [gmailImapManual, setGmailImapManual] = useState(false);
  const [statements, setStatements] = useState<StatementItem[]>([]);
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
  const [globalSearch, setGlobalSearch] = useState("");
  const [feeMode, setFeeMode] = useState(false);
  const [activityLog, setActivityLog] = useState<ActivityLogResponse | null>(null);
  const [activityFilter, setActivityFilter] = useState<"all" | "mail_sync" | "document_parse">("all");
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);
  const [activityRefreshTick, setActivityRefreshTick] = useState(0);
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

  async function copyLogsToClipboard(lines: string) {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(lines);
      return;
    }
    const el = document.createElement("textarea");
    el.value = lines;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
  }

  async function reloadCoreData() {
    const requestId = nextRequestId("reload");
    setLoadState("loading");
    pushLog("info", "system", "Yenileniyor...", requestId);
    try {
      const [data, runs, accounts, stmts] = await Promise.all([
        getHealth({ requestId }),
        getIngestionRuns(10, undefined, runStatusFilter, { requestId }),
        getMailAccounts({ requestId }),
        getStatements({ requestId }),
      ]);
      setHealth(data);
      setLatestRuns(runs.items);
      setNextCursor(runs.next_cursor);
      setMailAccounts(accounts.items);
      setSelectedMailAccountId(accounts.items[0]?.id ?? null);
      setStatements(stmts.items);
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
      } catch {
        // silently ignore
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
    // ── Sigorta / Emeklilik ──────────────────────────────────────────────────
    "sigorta",         // Türkiye Sigorta, Sompo Sigorta, Ray Sigorta…
    "ferdi kaza",
    "hayat sigorta",
    "emeklilik",       // MetLife Emeklilik, Anadolu Hayat Emeklilik, Garanti BBVA Emeklilik…
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
  function isFee(description: string): boolean {
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
      keywords: ["sigorta", "emeklilik", "metlife", "viennalife", "anadolu hayat", "sompo", "ray sigorta", "turkiye sigorta", "türkiye sigorta", "allianz", "axa", "groupama", "ergo", "ferdi kaza"] },
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

  function fmtTry(n: number | null) {
    if (n == null) return "—";
    return n.toLocaleString("tr-TR", { minimumFractionDigits: 2 }) + " TL";
  }

  const tabTitle: Record<AppTab, string> = {
    dashboard: "Özet",
    statements: "Ekstreler",
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
                      <p className="kpiValue kpiSmall">{upcomingPayments[0].due_date}</p>
                      <p className="kpiSub">{upcomingPayments[0].bank_name} · {daysUntil(upcomingPayments[0].due_date!)} gün kaldı</p>
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
              </div>

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
                    className="bulkDeleteBtn"
                    disabled={isDeletingStmts}
                    onClick={() => confirmDeleteStatements(
                      Array.from(selectedStmtIds),
                      `${selectedStmtIds.size} ekstre`
                    )}
                  >
                    🗑 Seçilenleri Sil
                  </button>
                  <button
                    className="bulkCancelBtn"
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
                          <button
                            className="stmtDeleteBtn"
                            title="Bu ekstreyi sil"
                            disabled={isDeletingStmts}
                            onClick={(e) => {
                              e.stopPropagation();
                              const label = `${stmt.bank_name ?? "Ekstre"} ${stmt.period_start ?? ""}–${stmt.period_end ?? ""}`;
                              confirmDeleteStatements([stmt.id], label);
                            }}
                          >
                            🗑
                          </button>
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
                              {stmt.parse_notes.includes("no_transactions_found") && (
                                <span className="parseNoteBadge parseNoteError" title="İşlem bulunamadı — PDF formatı tanınamıyor olabilir">
                                  ! İşlem yok
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
                      className={`logsFilterChip${activityFilter === f ? " active" : ""}`}
                      onClick={() => setActivityFilter(f)}
                    >
                      {f === "all" ? "Tümü" : f === "mail_sync" ? "✉ Mail Sync" : "📄 Parse"}
                    </button>
                  ))}
                </div>
                <button
                  className="logsRefreshBtn"
                  onClick={() => setActivityRefreshTick((t) => t + 1)}
                  disabled={isLoadingActivity}
                  title="Yenile"
                >
                  <span style={{ display: "inline-block", transition: "transform 0.4s", transform: isLoadingActivity ? "rotate(360deg)" : "none" }}>↺</span>
                  {isLoadingActivity ? " Yükleniyor…" : " Yenile"}
                </button>
              </div>

              {/* Activity timeline */}
              <div className="logsTimeline">
                {!activityLog && isLoadingActivity && (
                  <div className="logsEmpty">Yükleniyor…</div>
                )}
                {activityLog && (() => {
                  const filtered: ActivityEvent[] = activityLog.activities.filter(
                    (a) => activityFilter === "all" || a.type === activityFilter
                  );
                  if (filtered.length === 0) {
                    return <div className="logsEmpty">Kayıt bulunamadı.</div>;
                  }

                  function relTime(ts: string | null): string {
                    if (!ts) return "";
                    const diff = Math.round((Date.now() - new Date(ts).getTime()) / 1000);
                    if (diff < 60) return "az önce";
                    if (diff < 3600) return `${Math.floor(diff / 60)} dk önce`;
                    if (diff < 86400) return `${Math.floor(diff / 3600)} saat önce`;
                    return `${Math.floor(diff / 86400)} gün önce`;
                  }

                  function fmtDate(ts: string | null): string {
                    if (!ts) return "";
                    const d = new Date(ts);
                    return d.toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
                  }

                  return filtered.map((ev) => {
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
                              <span className="logsItemTime" title={ev.timestamp ?? ""}>{fmtDate(ev.timestamp)} · {relTime(ev.timestamp)}</span>
                            </div>
                            <div className="logsItemDetail">
                              <span className="logsChip logsChipNeutral">Taranan: {ev.scanned}</span>
                              <span className="logsChip logsChipGreen">Kaydedilen: {ev.saved}</span>
                              {ev.processed > 0 && <span className="logsChip logsChipNeutral">İşlenen: {ev.processed}</span>}
                              {ev.duplicates > 0 && <span className="logsChip logsChipMuted">Tekrar: {ev.duplicates}</span>}
                              {ev.failed > 0 && <span className="logsChip logsChipRed">Hata: {ev.failed}</span>}
                            </div>
                          </div>
                        </div>
                      );
                    } else {
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
                              <span className="logsItemTime" title={ev.timestamp ?? ""}>{fmtDate(ev.timestamp)} · {relTime(ev.timestamp)}</span>
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
                    }
                  });
                })()}
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
                      <div className="mailAccountSettingsRow">
                        <span className="mailAccountSettingsLabel">Maksimum mail tarama</span>
                        <span className="mailboxCode">{acct.fetch_limit} mail</span>
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
                        iPhone / Mac <strong>Mail</strong> veya Outlook’taki gibi: Google’ın kendi sayfasında oturum açarsın; EkstreHub ana şifreni tutmaz, sadece Google izin verir.
                      </p>
                      <a
                        className="btn btnGoogle"
                        href={`${apiUrlPath("api/oauth/gmail/start")}?label=${encodeURIComponent(formLabel || "Gmail Hesabı")}`}
                      >
                        Gmail’e bağlan (tarayıcıda aç)
                      </a>
                      {!health?.gmail_oauth_configured && (
                        <p className="muted" style={{ gridColumn: "1 / -1", fontSize: "0.88rem" }}>
                          Add-on’da henüz Google girişi ayarlı değilse yukarıdaki bağlantı seni geri yönlendirir — o zaman yönetici OAuth kurmalı veya aşağıdaki manuel yolu kullan.
                        </p>
                      )}
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
                          Google’da <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer">uygulama şifresi</a> ve <a href="https://mail.google.com/mail/u/0/#settings/fwdandpop" target="_blank" rel="noopener noreferrer">IMAP açık</a> olmalı.
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
                    Regex parser tanıyamadığı ekstreyi buraya gönderir. ChatGPT API önerilir — yerel
                    Ollama CPU'da çok yavaş olabilir.
                  </p>

                  {llmForm && (
                    <div className="llmSettingsPanel">
                      {/* Enable/Disable toggle */}
                      <div className="autoSyncRow">
                        <div className="autoSyncLabel">
                          AI Parser
                          <div className="autoSyncSub">Regex 0 işlem döndürürse AI devreye girer</div>
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
                    <button className="btn" onClick={() => setUiLogs([])}>Temizle</button>
                    <button
                      className="btn"
                      onClick={async () => {
                        const lines = visibleLogs.map((e) => `[${e.level}] ${e.at} ${e.message}`).join("\n");
                        try {
                          await copyLogsToClipboard(lines || "No logs");
                          pushLog("info", "system", "Loglar kopyalandı");
                        } catch {
                          pushLog("error", "system", "Kopyalama başarısız");
                        }
                      }}
                    >
                      Kopyala
                    </button>
                  </div>
                  <div className="logList">
                    {visibleLogs.length === 0 ? (
                      <p className="muted" style={{ padding: "12px 14px" }}>Log kaydı yok.</p>
                    ) : (
                      visibleLogs.map((entry) => (
                        <div key={entry.id} className={`logItem${entry.level === "error" ? " logError" : ""}`}>
                          <p className="logMeta">
                            <span className={`logLevel logLevel-${entry.level}`}>{entry.level.toUpperCase()}</span>
                            <span className="logCat">{entry.category}</span>
                            <span className="logTime">{entry.at.replace("T", " ").replace("Z", "")}</span>
                          </p>
                          <p className="logMsg">{entry.message}</p>
                        </div>
                      ))
                    )}
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </div>

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
