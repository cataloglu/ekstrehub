import type { ActivityEvent, ActivityLogResponse, ActivityMailSync } from "./api";

/** Tablo / kart özet satırı: taranan = yeni mail + tekrar mail + hata (IMAP’ten gelen her mesaj). */
export function formatMailSyncSummaryLine(ev: ActivityMailSync): string {
  const dupDocs = ev.duplicate_documents ?? 0;
  const skipAtt = ev.skipped_attachments ?? 0;
  const parts = [
    `taranan ${ev.scanned}`,
    `yeni mail ${ev.processed}`,
    `tekrar mail ${ev.duplicates}`,
    `yeni ekstre ${ev.saved}`,
  ];
  if (dupDocs > 0) {
    parts.push(`tekrar ekstre ${dupDocs}`);
  }
  if (skipAtt > 0) {
    parts.push(`atlanan ek ${skipAtt}`);
  }
  if (ev.failed > 0) {
    parts.push(`hata ${ev.failed}`);
  }
  parts.push(`süre ${ev.duration_seconds ?? "—"}s`);
  return parts.join(" · ");
}

/** Panoya yazma — HA / Ingress’te clipboard API bazen çalışmaz; textarea fallback. */
export async function copyTextRobust(text: string): Promise<void> {
  try {
    if (
      typeof navigator !== "undefined"
      && typeof window !== "undefined"
      && navigator.clipboard?.writeText
      && window.isSecureContext
    ) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch {
    /* fallback */
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "0";
  ta.style.top = "0";
  ta.style.width = "1px";
  ta.style.height = "1px";
  ta.style.opacity = "0";
  ta.style.zIndex = "-1";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    const ok = document.execCommand("copy");
    if (!ok) throw new Error("execCommand copy failed");
  } finally {
    document.body.removeChild(ta);
  }
}

export function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export type ActivityFilter = "all" | "mail_sync" | "document_parse";

function filterActivities(activities: ActivityEvent[], f: ActivityFilter): ActivityEvent[] {
  if (f === "all") return activities;
  return activities.filter((a) => a.type === f);
}

/** TSV benzeri düz metin — Excel / Notepad’e yapıştırmaya uygun. */
export function buildActivityLogPlainText(
  data: ActivityLogResponse | null,
  filter: ActivityFilter,
): string {
  if (!data) return "";
  const lines: string[] = [];
  const now = new Date().toISOString();
  lines.push(`# EkstreHub — sunucu aktivite özeti`);
  lines.push(`# Dışa aktarım: ${now}`);
  lines.push(`# Otomatik sync: ${data.auto_sync.enabled ? "açık" : "kapalı"} · ${data.auto_sync.interval_minutes} dk`);
  lines.push(`# Belgeler: toplam ${data.stats.total_docs} · parse ${data.stats.parsed_docs} · hatalı ${data.stats.failed_docs}`);
  lines.push("");
  lines.push(["zaman_iso", "tur", "durum", "id", "hesap_veya_dosya", "ozet"].join("\t"));

  const acts = filterActivities(data.activities, filter);
  for (const ev of acts) {
    if (ev.type === "mail_sync") {
      const acc = [ev.account_label, ev.imap_user].filter(Boolean).join(" · ") || `hesap_id=${ev.mail_account_id ?? "—"}`;
      const summary = `run=${ev.run_id} · ${formatMailSyncSummaryLine(ev)}`;
      lines.push(
        [
          ev.timestamp ?? "",
          "mail_sync",
          ev.status,
          String(ev.run_id),
          acc.replace(/\t/g, " "),
          summary.replace(/\t/g, " "),
        ].join("\t"),
      );
    } else {
      const notes = (ev.parse_notes || []).join(",");
      const summary = `doc=${ev.doc_id} islem=${ev.transaction_count} boyut_kb=${(ev.file_size_bytes / 1024).toFixed(0)} notlar=${notes}`;
      lines.push(
        [
          ev.timestamp ?? "",
          "document_parse",
          ev.status,
          String(ev.doc_id),
          `${(ev.bank_name ?? "—").replace(/\t/g, " ")} · ${ev.file_name.replace(/\t/g, " ")}`,
          summary.replace(/\t/g, " "),
        ].join("\t"),
      );
    }
  }
  return lines.join("\n");
}

export type UiLogRow = {
  at: string;
  level: string;
  category: string;
  requestId?: string;
  message: string;
};

export function buildClientLogsPlainText(rows: UiLogRow[]): string {
  const lines: string[] = [];
  lines.push(`# EkstreHub — tarayıcı / istemci logları`);
  lines.push(`# Dışa aktarım: ${new Date().toISOString()}`);
  lines.push("");
  lines.push(["zaman_iso", "seviye", "kategori", "istek_id", "mesaj"].join("\t"));
  for (const r of rows) {
    lines.push(
      [
        r.at,
        r.level,
        r.category,
        (r.requestId ?? "").replace(/\t/g, " "),
        r.message.replace(/\r?\n/g, " ").replace(/\t/g, " "),
      ].join("\t"),
    );
  }
  return lines.join("\n");
}
