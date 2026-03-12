# Golden Dataset Spec (In Progress)

## Objective

Parser/OCR/LLM kalitesini banka format degisimlerine karsi olcmek.

## Dataset Layout (Planned)

```text
datasets/golden/
  bank-a/
    pdf/
    csv/
    expected/
  bank-b/
    pdf/
    csv/
    expected/
```

## Requirements

- Tum dokumanlar anonimlestirilmis olmali
- Beklenen cikti JSON schema ile versiyonlu tutulmali
- Her release oncesi regression kosulacak

## Minimum Entry Criteria

- Banka basina en az 10 PDF
- Mumkunse banka basina en az 2 CSV
- Aidatli ve aidatsiz donem ornekleri
