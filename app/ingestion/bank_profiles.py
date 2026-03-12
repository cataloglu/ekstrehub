from dataclasses import dataclass


@dataclass(frozen=True)
class BankProfile:
    bank_name: str
    markers: tuple[str, ...]


BANK_PROFILES: tuple[BankProfile, ...] = (
    BankProfile(bank_name="Akbank", markers=("akbank", "axess")),
    BankProfile(bank_name="Garanti BBVA", markers=("garanti", "garantibbva", "miles&smiles", "miles smiles", "bonus kart")),
    BankProfile(bank_name="Yapi Kredi", markers=("yapikredi", "yapi kredi", "yapı kredi", "world card")),
    BankProfile(bank_name="Is Bankasi", markers=("isbank", "iş bank", "maximum kart", "maximiles", "maxipuan")),
    BankProfile(bank_name="VakifBank", markers=("vakifbank", "vakıfbank")),
    BankProfile(bank_name="Ziraat Bankasi", markers=("ziraat",)),
    BankProfile(bank_name="QNB", markers=("qnb", "qnb finansbank")),
    BankProfile(bank_name="TEB", markers=("teb",)),
    BankProfile(bank_name="DenizBank", markers=("denizbank",)),
    BankProfile(bank_name="Enpara", markers=("enpara",)),
    BankProfile(bank_name="Halkbank", markers=("halkbank", "paraf")),
    BankProfile(bank_name="HSBC", markers=("hsbc",)),
    BankProfile(bank_name="ING Bank", markers=("ing bank", "ing türkiye")),
)
