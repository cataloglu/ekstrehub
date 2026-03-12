# Dev Environment and Dependency Policy

## Why

Global Python ortaminda paket kurulumlari diger araclarla cakisabilir. Bu nedenle proje izole sanal ortam ile calistirilmalidir.

## Python Setup (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Test Commands

```powershell
pytest -q
```

## Node Setup

```powershell
cd ui
npm install
npm test
npm run build
```

## Dependency Rules

- Backend paketleri `requirements.txt` icinde pinlenmis versiyonla tutulur.
- Yeni paket eklerken once local venv'de test edilir.
- Upgrade islemleri toplu degil, kontrollu ve testli yapilir.
