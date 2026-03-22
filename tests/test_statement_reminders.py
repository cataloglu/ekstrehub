"""Extract special notices from Turkish credit card statement PDF text."""
from __future__ import annotations

from app.ingestion.statement_reminders import extract_statement_reminders

_ISBANK_SAMPLE = """
MESAJINIZ VAR
Bir Takvim Yılı İçinde 2 Defa Son Ödeme Tarihi İtibariyle Dönem
Borcunuzun Asgari Tutarından Az Ödeme Yaptınız.3 Defa Dönem
Borcunuzun Asgari Tutarından Az Ödeme Yapmanız Halinde, Yasa
Gereği Dönem Borcunuzun Tamamı Ödeninceye Kadar, Söz Konusu
Kartınız İle Nakit Çekilemeyecek Ve Sahip Olduğunuz Diğer Kartlar
İçin De Limit Artışı Yapılamayacaktır.
2023 yılında kazandığınız Pazarama Puanlarınızın kullanım süresi
31.12.2025 tarihinde sona ermektedir. Henüz kullanmadığınız 13.28
TL Pazarama Puan'ınızı 31 Aralık 2025 tarihine kadar kullanmanızı
önemle hatırlatırız.
2023 yılında kazanılan MaxiMillerin kullanım süresi 31.12.2025
tarihinde sona ermektedir. Henüz kullanmadığınız 992.96 TL
MaxiMil'inizi 31 Aralık 2025 tarihine kadar kullanmanızı önemle
hatırlatırız.
Sayfa 2 / 3
Belge Numarası : 143 - 187752804
KREDİ KARTI HESAP ÖZETİ
Sözleşme değişikliğidir. Kredi Kartı müşterilerimize sunulan
uygulama ve hizmetlerde meydana gelen değişiklikler kapsamında
Kredi Kartı Sözleşmesi'nin M.8 maddesine ve Sözleşme Öncesi
Bilgilendirme Formu D. maddesine aşağıda yer alan ifade eklenmiştir.
Üstü Kalsın hizmetimizin Minimum Yuvarlama Tutarı, Kredi Kartı
Sözleşmemizde yer alan V. ÜSTÜ KALSIN HİZMETİ İŞLEMLERİ
maddeleri kapsamında 1.000 TL olarak güncellenmiştir.
"""


def test_extract_finds_pazarama_maximil_and_legal() -> None:
    reminders = extract_statement_reminders(_ISBANK_SAMPLE)
    kinds = {r["kind"] for r in reminders}
    titles = {r["title"] for r in reminders}
    assert "expiry" in kinds
    assert "legal_warning" in kinds
    assert any("Pazarama" in t for t in titles)
    assert any("MaxiMil" in t for t in titles)
    paz = next(r for r in reminders if "Pazarama" in r["title"])
    assert paz.get("expires_on") == "2025-12-31"


def test_parse_statement_includes_reminders() -> None:
    from app.ingestion.statement_parser import ParsedStatement, _attach_statement_reminders

    ps = ParsedStatement()
    ps.parse_notes = ["test"]
    _attach_statement_reminders(ps, _ISBANK_SAMPLE)
    assert len(ps.statement_reminders) >= 2
