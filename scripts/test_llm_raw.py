"""Show the raw LLM response to debug the parser."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "sqlite:///dev-local.db")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("IMAP_HOST", "imap.gmail.com")
os.environ.setdefault("IMAP_PORT", "993")
os.environ.setdefault("IMAP_USER", "placeholder")
os.environ.setdefault("IMAP_PASSWORD", "placeholder")

from app.ingestion.llm_parser import call_llm

# Use a small sample of the PDF text to test
SAMPLE_TEXT = """HESAP / KART B?LG?LER?
Hesap Kesim Tarihi 24/02/2026
Ekstre D?nemi 24/01/2026-24/02/2026
Son ?deme Tarihi 06/03/2026
D?nem Borcu 847,376.81 TL
Asgari ?deme Tutar? 338,950.72 TL /%40
??lem Tarihi D?nemi?i ??lemler ??lem Tutar?
23/02/2026 Restoran ve Cafe ?ndirimi 2,280.00+ TL
22/02/2026 Restoran ve Cafe ?ndirimi 1,813.60+ TL
10/02/2026 Hesaptan ?deme 127,842.46+ TL
21/02/2026 ACIBADEM HASTANES? KAYSER? TR 0.01 60.00 TL
21/02/2026 ACIBADEM HASTANES? KAYSER? TR 0.87 8,650.00 TL
22/02/2026 MIGROS BAH?EL?EVLER MAH K KAYSER? TR 1,641.79 0.00 TL
19/02/2026 HAYS KYS. KAYSER? PARK A KAYSER? TR 6.40 1,600.98 TL
30/11/2025 SAFAR?-KL?P TEKST? Pe?. Taksit 3.Tk Anapara 4,055.22/6-3 1,351.75 TL
22/02/2026 SAN KUAF?R S?MGE KUAF?R Kayseri TR 800.00 TL
28/01/2026 GEVHER NES?BE VERG? DA?RE Ankara TR 670,021.95 TL
22/02/2026 ACIBADEM KAYSERI HASTAN KAYSERI TR 2,900.00 TL
22/02/2026 KILI? ET KAYSER? TR 9,068.00 TL
24/02/2026 Sat?? Faizi 3,003.87 TL
Toplam 847,376.81 TL"""

print("Sending sample text to LLM...")
print(f"Text length: {len(SAMPLE_TEXT)} chars")
print("-" * 60)

try:
    import urllib.request
    import urllib.error

    payload = {
        "model": "qwen2.5:7b",
        "messages": [
            {"role": "system", "content": """Sen bir Türk banka ekstre ayrıştırıcısısın.
Sana bir PDF'den çıkarılmış banka ekstresi metni verilecek.
Metni okuyup aşağıdaki JSON formatında SADECE JSON döndür, başka hiçbir şey yazma.

{
  "bank_name": "Banka adı",
  "period_start": "YYYY-MM-DD veya null",
  "period_end": "YYYY-MM-DD veya null",
  "due_date": "YYYY-MM-DD veya null",
  "total_due_try": 12345.67,
  "minimum_due_try": 1234.56,
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": "İşlem açıklaması",
      "amount": 123.45,
      "currency": "TRY"
    }
  ]
}

Kurallar:
- Ödemeler ve iadeler için amount negatif olmalı (örn: -1000.0)
- Harcamalar için amount pozitif olmalı
- Tutarları Türk formatından (1.234,56) ondalık sayıya çevir (1234.56)
- ? karakterleri encoding hatası, görmezden gel
- SADECE JSON döndür"""},
            {"role": "user", "content": f"Aşağıdaki banka ekstresi metnini ayrıştır:\n\n---\n{SAMPLE_TEXT}\n---"},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
        "stream": False,
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)
    content = data["choices"][0]["message"]["content"]
    finish = data["choices"][0].get("finish_reason")
    print(f"finish_reason: {finish}")
    print(f"response length: {len(content)} chars")
    print("\nRAW RESPONSE:")
    print(content)

    # Try parsing
    parsed = json.loads(content.strip().lstrip("```json").lstrip("```").rstrip("```").strip())
    print(f"\nParsed OK: {len(parsed.get('transactions', []))} transactions")
except Exception as e:
    print(f"Error: {e}")
