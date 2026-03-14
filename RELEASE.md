# EkstreHub — Versiyon Çıkarma Rehberi

Yeni sürüm çıkarmak için aşağıdaki adımları izle.

## 1. Versiyonu Güncelle

```bash
# ekstrehub/config.yaml
version: "1.0.2"   # Yeni versiyon
```

## 2. CHANGELOG Güncelle

**CHANGELOG.md** (repo root) ve **ekstrehub/CHANGELOG.md** dosyalarına yeni sürüm notlarını ekle:

```markdown
## [1.0.2] – YYYY-MM-DD

### Düzeltmeler / Özellikler
- ...
```

## 3. Commit ve Push

```bash
git add ekstrehub/config.yaml CHANGELOG.md ekstrehub/CHANGELOG.md
git commit -m "Release v1.0.2"
git push origin master
```

## 4. GitHub Release Oluştur

1. **Releases** → **Create a new release**
2. **Choose a tag**: `v1.0.2` (yeni tag oluştur)
3. **Target**: `master` (veya ilgili commit)
4. **Release title**: `v1.0.2`
5. **Description**: CHANGELOG'dan ilgili bölümü kopyala
6. **Publish release** tıkla

## 5. Build

- **Push** sonrası: GitHub Actions otomatik build alır (config.yaml versiyonu ile)
- **Release publish** sonrası: Tag versiyonu ile build alır (`v1.0.2` → `1.0.2`)

## Önemli

- `config.yaml` versiyonu ile GitHub tag **aynı** olmalı (örn. `1.0.2` ↔ `v1.0.2`)
- HA add-on mağazası, depodaki `config.yaml` ve `CHANGELOG.md` dosyalarını kullanır
- Docker image tag'leri: `ghcr.io/cataloglu/ekstrehub/{arch}:1.0.2`
