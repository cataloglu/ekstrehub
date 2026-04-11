"""Extract bank statement notices / reminders from raw PDF text (Turkish).

These are marketing, legal, and expiry notices — not transaction lines.
Heuristics + date extraction; no LLM required.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

# Paragraphs matching any of these (case-insensitive) are candidate reminders
_TRIGGER = re.compile(
    r"(pazarama|maximil|maxipuan|bonusflaş|bonus|worldpuan|world\s*puan|chip-?\s*para|paraf\s*para|"
    r"cardfinans|bankkart\s*lira|puanlarınız|puanınız|kullanım\s+süresi|"
    r"sona\s+erm|hatırlat|hatirlat|mesajınız\s+var|mesajiniz\s+var|"
    r"\basgari\b|nakit\s+çekilemeyecek|nakit\s+cekilemeyecek|dönem\s+borcunuzun|donem\s+borcunuzun|"
    r"sözleşme\s+değişikliği|sozlesme\s+degisikligi|üstü\s+kalsın|ustu\s+kalsin|"
    r"yuvarlama\s+tutarı|yuvarlama\s+tutari)",
    re.IGNORECASE,
)

_DATE_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")

_TR_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "agustos": 8,
    "eylül": 9,
    "eylul": 9,
    "ekim": 10,
    "kasım": 11,
    "kasim": 11,
    "aralık": 12,
    "aralik": 12,
}

_DATE_TR_WORD = re.compile(
    r"(\d{1,2})\s+(Ocak|Şubat|Subat|Mart|Nisan|Mayıs|Mayis|Haziran|Temmuz|"
    r"Ağustos|Agustos|Eylül|Eylul|Ekim|Kasım|Kasim|Aralık|Aralik)\s+(\d{4})",
    re.IGNORECASE,
)

_POINTS_CUE = re.compile(
    r"(pazarama|maximil|maxipuan|maximiles|maxi\s*miller|bonusflaş|bonus|worldpuan|world\s*puan|"
    r"chip-?\s*para|paraf\s*para|cardfinans|bankkart\s*lira|puan(?:lar[ıi]n[ıi]z)?|mil(?:ler)?)",
    re.IGNORECASE,
)
_EXPIRY_CUE = re.compile(
    r"(kullan[ıi]m\s+s[üu]resi|sona\s+erm|son\s+kullan(?:ma)?|tarihine\s+kadar|kadar\s+kullan)",
    re.IGNORECASE,
)
_NON_EXPIRY_DATE_CUE = re.compile(
    r"(hesap\s+kesim\s+tarihi|son\s+[öo]deme\s+tarihi|d[öo]nem\s+borcu|asgari|m[üu][sş]teri\s+numaras[ıi]|kart\s+numaras[ıi])",
    re.IGNORECASE,
)
_HEADER_FIELD_CUE = re.compile(
    r"(hesap\s*/\s*kart\s+bilgileri|hesap\s+bilgileri|m[üu][sş]teri\s+numaras[ıi]|kart\s+numaras[ıi]|kart\s+limiti|"
    r"nakit\s+avans\s+limiti|hesap\s+kesim\s+tarihi|ekstre\s+d[öo]nemi|son\s+[öo]deme\s+tarihi|asgari\s+[öo]deme)",
    re.IGNORECASE,
)
_STRONG_NOTICE_CUE = re.compile(
    r"(mesaj[ıi]n[ıi]z\s+var|nakit\s+çekilemeyecek|nakit\s+cekilemeyecek|"
    r"d[öo]nem\s+borcunuzun\s+asgari\s+tutar[ıi]ndan\s+az\s+[öo]deme|"
    r"s[öo]zleşme\s+değişikliği|sozlesme\s+degisikligi|üstü\s+kalsın|ustu\s+kalsin|"
    r"yuvarlama|pazarama|maximil|maxipuan|maximiles)",
    re.IGNORECASE,
)
_LOYALTY_PROGRAM_CUE = re.compile(
    r"(pazarama|maximil(?:es)?|maxipuan|bonusflaş|bonus|worldpuan|world\s*puan|chip-?\s*para|"
    r"paraf\s*para|cardfinans|bankkart\s*lira|\bpuan(?:lar)?\b|\bmil(?:ler)?\b)",
    re.IGNORECASE,
)
_LOYALTY_AMOUNT_CONTEXT_CUE = re.compile(
    r"(kullanmad|kalan|kullan[ıi]labilir|değerinde|degerinde|sona\s+erm|süresi|suresi|geçerli|gecerli|"
    r"bakiye|bakiyeniz|hesaplan|toplam|mevcut|kazan[ıi]lan|biriken|harcan[ıi]labilir)",
    re.IGNORECASE,
)
_LOYALTY_BALANCE_LINE_CONTEXT = re.compile(
    r"(harcan[ıi]labilir|kullan[ıi]labilir|kalan|toplam|mevcut|biriken|bakiye|bakiyeniz|"
    r"sadakat|puan|mil|bonus|world|chip|paraf|maxi)",
    re.IGNORECASE,
)
_LOYALTY_BALANCE_LINE_PATTERNS = (
    re.compile(
        r"(pazarama|maximil(?:es)?|maxipuan|bonusfla[sş]|bonus|world\s*puan|worldpuan|chip-?\s*para|"
        r"paraf\s*para|cardfinans|bankkart\s*lira|\bpuan(?:lar)?\b|\bmil(?:ler)?\b)"
        r"[^\n]{0,35}?"
        r"(?:bakiye|bakiyeniz|kalan|kullan[ıi]labilir|harcan[ıi]labilir|toplam|mevcut|biriken)"
        r"[^\n]{0,20}?"
        r"([\d\.,]+)\s*(?:tl|try|adet)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:bakiye|bakiyeniz|kalan|kullan[ıi]labilir|harcan[ıi]labilir|toplam|mevcut|biriken)"
        r"[^\n]{0,20}?"
        r"([\d\.,]+)\s*(?:tl|try|adet)?\b[^\n]{0,20}?"
        r"(pazarama|maximil(?:es)?|maxipuan|bonusfla[sş]|bonus|world\s*puan|worldpuan|chip-?\s*para|"
        r"paraf\s*para|cardfinans|bankkart\s*lira|\bpuan(?:lar)?\b|\bmil(?:ler)?\b)",
        re.IGNORECASE,
    ),
)
_LOYALTY_REMAINING_PATTERNS = (
    re.compile(
        r"(?:hen[üu]z\s+kullanmad[ıi][ğg]?[ıi]n[ıi]z|kalan)\s+([\d\.,]+)\s*tl\s+"
        r"(pazarama\s+puan(?:[ıi]'?[ıi]n[ıi]z)?|maximil(?:es)?(?:'in)?|maxipuan(?:[ıi]'?[ıi]n[ıi]z)?|"
        r"bonusfla[sş]|bonus|world\s*puan|worldpuan|chip-?\s*para|paraf\s*para|cardfinans|bankkart\s*lira|"
        r"\bpuan(?:lar[ıi]n[ıi]z)?\b|\bmil(?:ler)?\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(pazarama\s+puan(?:[ıi]'?[ıi]n[ıi]z)?|maximil(?:es)?(?:'in)?|maxipuan(?:[ıi]'?[ıi]n[ıi]z)?|"
        r"bonusfla[sş]|bonus|world\s*puan|worldpuan|chip-?\s*para|paraf\s*para|cardfinans|bankkart\s*lira|"
        r"\bpuan(?:lar[ıi]n[ıi]z)?\b|\bmil(?:ler)?\b)"
        r"[^\n]{0,40}?([\d\.,]+)\s*tl",
        re.IGNORECASE,
    ),
    re.compile(
        r"([\d\.,]+)\s*tl[^\n]{0,40}?"
        r"(pazarama\s+puan|maximil(?:es)?|maxipuan|bonusfla[sş]|bonus|world\s*puan|worldpuan|"
        r"chip-?\s*para|paraf\s*para|cardfinans|bankkart\s*lira|\bmil(?:ler)?\b|\bpuan(?:lar)?\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(bonusfla[sş]|bonus|world\s*puan|worldpuan|chip-?\s*para|paraf\s*para|cardfinans|bankkart\s*lira)"
        r"[^\n]{0,70}?([\d\.,]+)\s*tl",
        re.IGNORECASE,
    ),
    re.compile(
        r"([\d\.,]+)\s*tl[^\n]{0,70}?"
        r"(bonusfla[sş]|bonus|world\s*puan|worldpuan|chip-?\s*para|paraf\s*para|cardfinans|bankkart\s*lira)",
        re.IGNORECASE,
    ),
    # Non-TL loyalty balances (e.g. "Toplam MaxiMil bakiyeniz 12.450")
    re.compile(
        r"(?:kalan|kullan[ıi]labilir|toplam|mevcut|biriken)[^\n]{0,50}?"
        r"([\d\.,]+)\s*(?:adet\s*)?"
        r"(maximil(?:es)?|world\s*puan|worldpuan|bonusfla[sş]|bonus|chip-?\s*para|paraf\s*para|"
        r"cardfinans|bankkart\s*lira|\bmil(?:ler)?\b|\bpuan(?:lar)?\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(maximil(?:es)?|world\s*puan|worldpuan|bonusfla[sş]|bonus|chip-?\s*para|paraf\s*para|"
        r"cardfinans|bankkart\s*lira|\bmil(?:ler)?\b|\bpuan(?:lar)?\b)"
        r"[^\n]{0,50}?"
        r"([\d\.,]+)\s*(?:adet)?\b",
        re.IGNORECASE,
    ),
)


def _parse_dates_from_text(text: str) -> list[date]:
    out: list[date] = []
    for m in _DATE_DMY.finditer(text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            out.append(date(y, mo, d))
        except ValueError:
            pass
    for m in _DATE_TR_WORD.finditer(text):
        d = int(m.group(1))
        mon_raw = m.group(2).lower()
        mon = _TR_MONTHS.get(mon_raw)
        y = int(m.group(3))
        if mon:
            try:
                out.append(date(y, mon, d))
            except ValueError:
                pass
    return out


def _parse_dates_with_span(text: str) -> list[tuple[date, int, int]]:
    out: list[tuple[date, int, int]] = []
    for m in _DATE_DMY.finditer(text):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            out.append((date(y, mo, d), m.start(), m.end()))
        except ValueError:
            pass
    for m in _DATE_TR_WORD.finditer(text):
        d = int(m.group(1))
        mon_raw = m.group(2).lower()
        mon = _TR_MONTHS.get(mon_raw)
        y = int(m.group(3))
        if mon:
            try:
                out.append((date(y, mon, d), m.start(), m.end()))
            except ValueError:
                pass
    return out


def _pick_expiry_date(paragraph: str, dates: list[date]) -> date | None:
    """Prefer the date that appears in expiry / deadline context."""
    if not dates:
        return None
    low = paragraph.lower()
    spans = _parse_dates_with_span(paragraph)
    best: tuple[int, date] | None = None
    for dt, st, en in spans:
        left = max(0, st - 56)
        right = min(len(low), en + 56)
        around = low[left:right]
        score = 0
        if _EXPIRY_CUE.search(around):
            score += 6
        if _POINTS_CUE.search(around):
            score += 3
        if _NON_EXPIRY_DATE_CUE.search(around):
            score -= 8
        # Loyalty expiries are often year-end; weak tie-breaker.
        if _POINTS_CUE.search(low) and dt.month == 12 and dt.day >= 28:
            score += 1
        if best is None or score > best[0] or (score == best[0] and dt > best[1]):
            best = (score, dt)
    if best and best[0] > 0:
        return best[1]
    if _EXPIRY_CUE.search(low) and not _NON_EXPIRY_DATE_CUE.search(low):
        return max(dates)
    return None


def _classify_kind(text: str) -> str:
    low = text.lower()
    if any(
        x in low
        for x in (
            "asgari",
            "nakit çekilemeyecek",
            "nakit cekilemeyecek",
            "dönem borcunuzun",
            "donem borcunuzun",
            "limit artışı",
            "limit artisi",
        )
    ):
        return "legal_warning"
    if "sözleşme" in low or "sozlesme" in low or "değişikliği" in low or "degisligi" in low:
        return "contract"
    if "üstü kalsın" in low or "ustu kalsin" in low or "yuvarlama" in low:
        return "service_change"
    has_points = bool(_POINTS_CUE.search(low))
    has_expiry = bool(_EXPIRY_CUE.search(low))
    if has_points and has_expiry:
        return "expiry"
    if has_expiry and not _NON_EXPIRY_DATE_CUE.search(low):
        return "expiry"
    return "info"


def _title_for(text: str, kind: str) -> str:
    low = text.lower()
    if "pazarama" in low:
        return "Pazarama puanı"
    if "maximil" in low or "maxipuan" in low or "maxi miller" in low:
        return "MaxiMil / MaxiPuan"
    if "bonusflaş" in low or "bonusflas" in low or "bonus" in low:
        return "Bonus"
    if "worldpuan" in low or "world puan" in low:
        return "Worldpuan"
    if "chip-para" in low or "chip para" in low:
        return "Chip-Para"
    if "paraf para" in low or "parafpara" in low:
        return "ParafPara"
    if "cardfinans" in low:
        return "CardFinans"
    if "bankkart lira" in low:
        return "Bankkart Lira"
    if kind == "legal_warning":
        return "Ödeme / limit uyarısı"
    if kind == "contract":
        return "Sözleşme bildirimi"
    if kind == "service_change":
        return "Hizmet / ücret güncellemesi"
    if "mesajınız" in low or "mesajiniz" in low:
        return "Banka mesajı"
    line = text.strip().split("\n")[0] if text.strip() else ""
    if len(line) > 90:
        return line[:87] + "…"
    return line or "Hatırlatma"


def _is_noise(p: str) -> bool:
    s = p.strip().lower()
    if len(s) < 12:
        return True
    if re.match(r"^sayfa\s+\d+", s):
        return True
    if s.startswith("belge numarası") or s.startswith("belge numarasi"):
        return True
    if re.match(r"^\d+\s*[-–]\s*\d+$", s):  # doc numbers
        return False
    return False


def _is_statement_header_block(p: str) -> bool:
    """Skip generic account-info blocks accidentally classified as reminders."""
    low = p.lower()
    header_hits = len(_HEADER_FIELD_CUE.findall(low))
    if header_hits < 2:
        return False
    if _POINTS_CUE.search(low) or _EXPIRY_CUE.search(low):
        return False
    if _STRONG_NOTICE_CUE.search(low):
        return False
    return True


def _parse_tr_amount(amount_raw: str | None) -> float | None:
    if not amount_raw:
        return None
    s = amount_raw.strip().replace(" ", "").replace("\u00a0", "")
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # If dot groups look like thousand separators (e.g. 12.450), normalize to integer form.
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
            s = s.replace(".", "")
    try:
        return round(float(s), 2)
    except Exception:
        return None


def _loyalty_program_name(text: str) -> str | None:
    low = text.lower()
    if "pazarama" in low:
        return "Pazarama"
    if "maximil" in low or "maximiles" in low:
        return "MaxiMil"
    if "maxipuan" in low:
        return "MaxiPuan"
    if "bonusflaş" in low or "bonusflas" in low or "bonus" in low:
        return "Bonus"
    if "worldpuan" in low or "world puan" in low:
        return "Worldpuan"
    if "chip-para" in low or "chip para" in low:
        return "Chip-Para"
    if "paraf para" in low or "parafpara" in low:
        return "ParafPara"
    if "cardfinans" in low:
        return "CardFinans"
    if "bankkart lira" in low:
        return "Bankkart Lira"
    if re.search(r"\bmil(?:ler)?\b", low):
        return "Mil"
    if re.search(r"\bpuan(?:lar)?\b", low):
        return "Puan"
    return None


def _extract_loyalty_remaining(text: str) -> tuple[str | None, float | None]:
    if not _LOYALTY_PROGRAM_CUE.search(text):
        return None, None
    low = text.lower()
    if not (
        _EXPIRY_CUE.search(low)
        or _LOYALTY_AMOUNT_CONTEXT_CUE.search(low)
        or "sona erm" in low
        or "kalan" in low
        or "kullanmad" in low
    ):
        # Avoid picking statement debt amounts from generic card-header blocks.
        return _loyalty_program_name(text), None
    program = _loyalty_program_name(text)
    for rx in _LOYALTY_REMAINING_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        groups = m.groups()
        # pattern-1: (amount, program), pattern-2: (program, amount)
        if groups and len(groups) >= 2:
            if _parse_tr_amount(groups[0]) is not None:
                amount = _parse_tr_amount(groups[0])
                program = _loyalty_program_name(groups[1]) or program
            else:
                amount = _parse_tr_amount(groups[1])
                program = _loyalty_program_name(groups[0]) or program
            if amount is not None:
                return program, amount
    return program, None


def _extract_loyalty_balance_lines(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for raw_line in text.split("\n"):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) < 14 or len(line) > 220:
            continue
        if not _LOYALTY_PROGRAM_CUE.search(line):
            continue
        if not _LOYALTY_BALANCE_LINE_CONTEXT.search(line):
            continue
        if _NON_EXPIRY_DATE_CUE.search(line):
            continue
        program = _loyalty_program_name(line)
        amount: float | None = None
        for rx in _LOYALTY_BALANCE_LINE_PATTERNS:
            m = rx.search(line)
            if not m:
                continue
            g1, g2 = m.groups()
            if _parse_tr_amount(g1) is not None:
                amount = _parse_tr_amount(g1)
                program = _loyalty_program_name(g2) or program
            else:
                amount = _parse_tr_amount(g2)
                program = _loyalty_program_name(g1) or program
            if amount is not None:
                break
        if program is None or amount is None or amount <= 0:
            continue
        key = f"{program}|{amount:.2f}|{line.lower()[:80]}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        title = f"{program} bakiyesi"
        out.append(
            {
                "title": title,
                "text": line[:4000],
                "kind": "info",
                "expires_on": None,
                "loyalty_program": program,
                "remaining_value_try": amount,
            }
        )
    return out


def _split_into_notice_blocks(text: str) -> list[str]:
    """Split dense PDF text (mostly single \\n) into separate notices."""
    lines = text.split("\n")
    starters = (
        re.compile(r"^MESAJINIZ\s+VAR\b", re.I),
        re.compile(
            r"^\d{4}\s+yılında\s+kazandığınız|^\d{4}\s+yılında\s+kazanılan|"
            r"^\d{4}\s+yilinda\s+kazandiniz|^\d{4}\s+yilinda\s+kazanilan",
            re.I,
        ),
        re.compile(r"^Sözleşme\s+değişikliği|^Sozlesme\s+degisligi", re.I),
        re.compile(r"^KREDİ\s+KARTI\s+HESAP\s+ÖZETİ|^KREDI\s+KARTI\s+HESAP\s+OZETI", re.I),
        re.compile(r"^Üstü\s+Kalsın|^Ustu\s+Kalsin", re.I),
    )

    blocks: list[list[str]] = []
    current: list[str] = []

    def is_start(s: str) -> bool:
        t = s.strip()
        if not t:
            return False
        for rx in starters:
            if rx.search(t):
                return True
        return False

    for line in lines:
        if is_start(line) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)

    return ["\n".join(b).strip() for b in blocks if "".join(b).strip()]


def _merge_header_paragraphs(paras: list[str]) -> list[str]:
    """Merge 'MESAJINIZ VAR' + body into one block."""
    out: list[str] = []
    i = 0
    while i < len(paras):
        p = paras[i].strip()
        if (
            i + 1 < len(paras)
            and len(p) < 50
            and re.search(r"mesajınız\s+var|mesajiniz\s+var", p, re.I)
            and _TRIGGER.search(paras[i + 1])
        ):
            out.append(p + "\n\n" + paras[i + 1].strip())
            i += 2
            continue
        out.append(p)
        i += 1
    return out


def extract_statement_reminders(text: str) -> list[dict[str, Any]]:
    """Return structured reminders from full PDF text (deduplicated)."""
    if not text or not text.strip():
        return []

    raw = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n\s*\n+", raw)
    paras = [p.strip() for p in parts if p.strip()]
    paras = _merge_header_paragraphs(paras)

    # Dense PDFs: few blank lines → one huge "paragraph" — split on notice line-starts
    expanded: list[str] = []
    for p in paras:
        if len(p) > 500:
            expanded.extend(_split_into_notice_blocks(p))
        else:
            expanded.append(p)

    seen: set[str] = set()
    reminders: list[dict[str, Any]] = []

    for para in expanded:
        if _is_noise(para) and len(para) < 80:
            continue
        if _is_statement_header_block(para):
            continue
        if not _TRIGGER.search(para):
            continue
        if len(para) < 30:
            continue

        norm = re.sub(r"\s+", " ", para).strip().lower()
        digest = hashlib.sha256(norm.encode("utf-8", errors="ignore")).hexdigest()[:16]
        if digest in seen:
            continue
        seen.add(digest)

        kind = _classify_kind(para)
        dates = _parse_dates_from_text(para)
        exp = _pick_expiry_date(para, dates) if kind == "expiry" or dates else None
        if kind != "expiry" and dates:
            # Still attach primary deadline if any date looks like a deadline
            low = para.lower()
            if "tarihine kadar" in low or "tarihinde sona" in low:
                exp = _pick_expiry_date(para, dates)

        title = _title_for(para, kind)
        loyalty_program, remaining_value_try = _extract_loyalty_remaining(f"{title}\n{para}")
        item: dict[str, Any] = {
            "title": title,
            "text": para[:4000],
            "kind": kind,
            "expires_on": exp.isoformat() if exp else None,
            "loyalty_program": loyalty_program,
            "remaining_value_try": remaining_value_try,
        }
        reminders.append(item)

    # Fallback path: directly capture explicit spendable loyalty balance lines.
    for item in _extract_loyalty_balance_lines(raw):
        norm = re.sub(r"\s+", " ", str(item.get("text", ""))).strip().lower()
        digest = hashlib.sha256(norm.encode("utf-8", errors="ignore")).hexdigest()[:16]
        if digest in seen:
            continue
        seen.add(digest)
        reminders.append(item)

    return reminders
