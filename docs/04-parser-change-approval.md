# Parser Change and Approval Flow

## Objective

Banka ekstre formatinda degisiklik oldugunda sistemin sessizce parser degistirmesi yerine kullanici onayi ile guvenli gecis yapmak.

## Trigger Conditions

Asagidaki durumlardan biri olursa drift suphe kaydi olusur:

- Zorunlu alanlardan biri cikartilamadi
- Toplam borc ve item toplamlarinda belirgin tutarsizlik var
- Due date benzeri kritik alan confidence esik altinda
- Yeni metin paterni mevcut parser ile eslesmiyor

## Candidate Parser Pipeline

1. Sistem aktif parser ile parse eder ve sonuc confidence skoru uretir.
2. Esik altindaysa candidate parser olusturma sureci baslar.
3. Candidate parser son N dokumanla geriye donuk test edilir.
4. Test sonucu bir `validation_score` olarak kaydedilir.
5. `parser_change_requests` kaydi `pending` durumunda acilir.

## User Approval Policy

- Varsayilan: parser degisimi icin kullanici onayi zorunlu
- Kullanici approved verirse candidate parser active olur
- Kullanici rejected verirse mevcut parser ile devam edilir
- Her karar audit log'a yazilir

## Safety Rules

- Onaysiz parser promote edilmez
- Kritik alanlari eksik parse eden parser active olamaz
- Candidate parser rollback icin onceki active versiyon saklanir

## UX Expectations

Kullaniciya sunulacak onay ekraninda:

- "Ne degisti?" ozeti
- Eski/yeni parser basari metrikleri
- Ornek cikti farki (masked)
- Onay / Reddet aksiyonu
