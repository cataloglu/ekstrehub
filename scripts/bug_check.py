"""General bug check for EkstreHub."""
import sys, re, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

errors = []
warnings = []

def ok(msg): print(f"  [OK]   {msg}")
def warn(msg): warnings.append(msg); print(f"  [WARN] {msg}")
def fail(msg): errors.append(msg); print(f"  [FAIL] {msg}")

# ── 1. Parser imports ──────────────────────────────────────────────────────
print("\n=== 1. PARSER IMPORTS ===")
try:
    from app.ingestion.statement_parser import (
        parse_statement, _parse_yapikredi, _parse_isbank,
        _parse_garanti, _parse_denizbank, _detect_bank_from_text,
        _ISBANK_TX_SLASH, _YK_TX_LINE,
    )
    ok("All parser functions importable")
except Exception as e:
    fail(f"Parser import error: {e}")

# ── 2. Bank detection ──────────────────────────────────────────────────────
print("\n=== 2. BANK DETECTION ===")
cases = [
    ("DenizBank", "DENIZBANK A.S. KREDİ KARTI HESAP ÖZETİ"),
    ("is bankasi", "MAXIMILES BLACK Hesap Özeti"),
    ("yapi kredi", "WORLDPUAN Hesap Kesim Tarihi Kart Numarası"),
    ("garanti", "Garanti BBVA Miles&Smiles Hesap Özeti"),
]
for expected, text in cases:
    detected = _detect_bank_from_text(text)
    if detected and expected.lower() in detected.lower():
        ok(f"Detect '{expected}' -> '{detected}'")
    else:
        warn(f"Detect '{expected}' -> '{detected}' (expected to contain '{expected}')")

# ── 3. YK amount regex ─────────────────────────────────────────────────────
print("\n=== 3. YK AMOUNT REGEX ===")
_YK_AMOUNT_PAT = r"[+\-]?[\d]{1,3}(?:\.[\d]{3})*,[\d]{2}"
amounts = [("480,42", True), ("1.400,00", True), ("300.000,00", True),
           ("+100.356,06", True), ("-82,63", True), ("1.40", False), ("abc", False)]
for amt, should_match in amounts:
    m = bool(re.fullmatch(_YK_AMOUNT_PAT, amt))
    if m == should_match:
        ok(f"Amount '{amt}' -> {'match' if m else 'no match'} (expected)")
    else:
        fail(f"Amount '{amt}' -> {'match' if m else 'no match'} (expected {'match' if should_match else 'no match'})")

# ── 4. IS Bank slash regex ─────────────────────────────────────────────────
print("\n=== 4. IS BANK SLASH REGEX ===")
ib_lines = [
    ("25/11/2025 HACIRESTORANKAYSERITR 7.455,00 37,28", "7.455,00"),
    ("27/11/2025 BLACKRESTORANINDIRIM -745,50", "-745,50"),
    ("06/12/2025 OCTET/OZGORKEYOTOMOTIVDENIZLITR 270.000,00 40,00 27,00", "270.000,00"),
    ("26/11/2025 ETSTUR/4440387ISTANBULTR 14.849,96 4/6taksidi(89.099,75)", "14.849,96"),
]
for line, expected_amt in ib_lines:
    m = _ISBANK_TX_SLASH.match(line)
    if m and m.group(5) == expected_amt:
        ok(f"IS slash: '{line[:50]}' -> amount={m.group(5)}")
    elif m:
        fail(f"IS slash: '{line[:50]}' -> amount={m.group(5)} (expected {expected_amt})")
    else:
        fail(f"IS slash: NO MATCH for '{line[:50]}'")

# ── 5. YK tx regex ────────────────────────────────────────────────────────
print("\n=== 5. YK TX REGEX ===")
yk_lines = [
    ("02 Şubat 2026 KÖŞK DÖNER KAYSERİ TR 1.400,00", "1.400,00"),
    ("17 Şubat 2026 A-101 9910 A101 KAYSERİ DKAYSERİ TR 300.000,00 12.000", "300.000,00"),
    ("19 Şubat 2026 AMAZON PRIME*130CX1OC3 AMZN.COM/BILLWAUS 675,54", "675,54"),
    ("06 Şubat 2026 OPET SOMPET AKARYAKIT KAYSERİ TR 480,42 120", "480,42"),
]
for line, expected_amt in yk_lines:
    m = _YK_TX_LINE.match(line)
    if m and m.group(5) == expected_amt:
        ok(f"YK tx: '{line[:50]}' -> amount={m.group(5)}")
    elif m:
        fail(f"YK tx: '{line[:50]}' -> amount={m.group(5)} (expected {expected_amt})")
    else:
        fail(f"YK tx: NO MATCH for '{line[:50]}'")

# ── 6. app_settings ───────────────────────────────────────────────────────
print("\n=== 6. APP SETTINGS ===")
try:
    import app.app_settings as aps
    cfg = aps.get_llm_config()
    ok(f"get_llm_config: enabled={cfg['llm_enabled']} provider={aps.load().get('llm_provider')}")
    resp = aps.get_api_response()
    ok(f"get_api_response: model={resp['llm_model']} key_set={resp['llm_api_key_set']}")
except Exception as e:
    fail(f"app_settings error: {e}")

# ── 7. DB consistency ─────────────────────────────────────────────────────
print("\n=== 7. DB CONSISTENCY ===")
try:
    import sqlite3, json
    db = sqlite3.connect("dev-local.db")
    docs = db.execute("SELECT id, parsed_json FROM statement_documents").fetchall()
    zero = [d[0] for d in docs if not json.loads(d[1] or "{}").get("transactions")]
    if zero:
        warn(f"{len(zero)} docs with 0 transactions: IDs={zero}")
    else:
        ok(f"All {len(docs)} docs have transactions")
    cards = set()
    for d in docs:
        p = json.loads(d[1] or "{}")
        cn = p.get("card_number")
        if cn:
            cards.add(cn)
    ok(f"Unique card numbers found: {len(cards)}")
    db.close()
except Exception as e:
    fail(f"DB check error: {e}")

# ── Summary ────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Results: {len(errors)} errors, {len(warnings)} warnings")
if errors:
    print("ERRORS:")
    for e in errors:
        print(f"  - {e}")
if warnings:
    print("WARNINGS:")
    for w in warnings:
        print(f"  - {w}")
if not errors and not warnings:
    print("All checks PASSED!")
