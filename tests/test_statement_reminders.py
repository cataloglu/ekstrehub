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
    assert paz.get("loyalty_program") == "Pazarama"
    assert paz.get("remaining_value_try") == 13.28
    maxi = next(r for r in reminders if "MaxiMil" in r["title"])
    assert maxi.get("remaining_value_try") == 992.96


def test_parse_statement_includes_reminders() -> None:
    from app.ingestion.statement_parser import ParsedStatement, _attach_statement_reminders

    ps = ParsedStatement()
    ps.parse_notes = ["test"]
    _attach_statement_reminders(ps, _ISBANK_SAMPLE)
    assert len(ps.statement_reminders) >= 2


def test_header_dates_are_not_misread_as_points_expiry() -> None:
    text = """
    HESAP BİLGİLERİ
    Hesap Kesim Tarihi :2 Mart 2026
    Son Ödeme Tarihi :12 Mart 2026
    Dönem Borcu :403.487,40 TL
    Ödenmesi Gereken Asgari Tutar/Oran
    """
    reminders = extract_statement_reminders(text)
    assert reminders == []


def test_points_expiry_prefers_year_end_deadline() -> None:
    text = """
    2023 yılında kazanılan MaxiMillerin kullanım süresi 31.12.2025 tarihinde sona ermektedir.
    Henüz kullanmadığınız MaxiMil'inizi 31 Aralık 2025 tarihine kadar kullanmanızı önemle hatırlatırız.
    """
    reminders = extract_statement_reminders(text)
    assert len(reminders) == 1
    assert reminders[0]["kind"] == "expiry"
    assert reminders[0]["expires_on"] == "2025-12-31"


def test_extract_loyalty_remaining_from_mojibake_text() -> None:
    text = (
        "2023 y�l�nda kazand���n�z Pazarama Puanlar�n�z�n kullan�m s�resi 31.12.2025 tarihinde sona ermektedir. "
        "Hen�z kullanmad���n�z 13.28 TL Pazarama Puan'�n�z� 31 Aral�k 2025 tarihine kadar kullanman�z� �nemle hat�rlat�r�z."
    )
    reminders = extract_statement_reminders(text)
    assert len(reminders) == 1
    assert reminders[0]["remaining_value_try"] == 13.28
    assert reminders[0]["loyalty_program"] == "Pazarama"


def test_extract_bank_specific_loyalty_programs() -> None:
    samples = [
        ("Bonus programınız kapsamında kullanılabilir 45,60 TL değerinde Bonus bakiyeniz bulunmaktadır.", "Bonus", 45.60),
        ("Worldpuan bakiyeniz 128,75 TL olup kampanyalarda geçerlidir.", "Worldpuan", 128.75),
        ("Kalan 32,10 TL Chip-Para tutarınızı ay sonuna kadar kullanabilirsiniz.", "Chip-Para", 32.10),
        ("Paraf Para bakiyeniz 21.40 TL olarak hesaplanmıştır.", "ParafPara", 21.40),
    ]
    for text, expected_program, expected_amount in samples:
        reminders = extract_statement_reminders(text)
        assert len(reminders) == 1
        assert reminders[0].get("loyalty_program") == expected_program
        assert reminders[0].get("remaining_value_try") == expected_amount


def test_extract_non_tl_miles_balance() -> None:
    text = "Toplam MaxiMil bakiyeniz 12.450 olup kampanya koşullarında kullanılabilir."
    reminders = extract_statement_reminders(text)
    assert len(reminders) == 1
    assert reminders[0].get("loyalty_program") == "MaxiMil"
    assert reminders[0].get("remaining_value_try") == 12450.0
