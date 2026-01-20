# R6 Hitman

A lightweight FastAPI + WebSocket game board for tracking Rainbow Six Hitman case files.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open <http://localhost:8000>.
