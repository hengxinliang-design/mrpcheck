# MRP Check / MPS LN Import

This repository contains the service-oriented replacement prototype for the original Excel VBA macro used to import master production schedule data into ERP-LN/Baan.

## Current Scope

- Excel import parser for the original `主计划导入` workbook layout.
- Local validation and mock LN adapter.
- FastAPI service skeleton for batch upload, validation, import, job status, and row status.
- SQLite-backed local storage for the first service prototype.
- Test coverage for Excel IO, importer orchestration, validation, mock adapter, and service flow.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r mps_ln_import/requirements-dev.txt
python -m pytest mps_ln_import/tests -q
```

Run the API:

```bash
uvicorn mps_ln_import.service.api:app --host 127.0.0.1 --port 8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

See [mps_ln_import/README.md](mps_ln_import/README.md) and [mps_ln_import/SERVICE_REDESIGN.md](mps_ln_import/SERVICE_REDESIGN.md) for details.

