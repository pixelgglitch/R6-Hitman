# R6 Hitman (WebSockets)

A simple Flask + Socket.IO party game:
- Host creates a lobby
- Players join with a code
- Host starts a round to generate 6 case files (target operator + 3 random requirements)
- Players race to claim kills; points awarded by claim order

## Setup

### 1) Install dependencies
```bash
pip install flask flask-socketio eventlet
```

### 2) Run
```bash
python app.py
```

Open: http://127.0.0.1:5000

## Notes
- This is an MVP / starter. Claims are honor-system.
- Easy upgrades: timers, per-player case files, proof upload, persistent lobbies, etc.
