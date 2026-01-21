import os
import random
import string
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

# -----------------------------
# Config
# -----------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# -----------------------------
# Game data
# -----------------------------
ATTACKERS = [
    "Sledge", "Thatcher", "Ash", "Thermite", "Twitch", "Montagne",
    "Glaz", "Fuze", "Blitz", "IQ", "Buck", "Blackbeard",
    "Capitão", "Hibana", "Jackal", "Ying", "Zofia", "Dokkaebi",
    "Lion", "Finka", "Maverick", "Nomad", "Gridlock", "Nøkk",
    "Amaru", "Kali", "Iana", "Ace", "Zero", "Flores",
    "Osa", "Sens", "Grim", "Brava", "Ram", "Deimos",
]

DEFENDERS = [
    "Smoke", "Mute", "Castle", "Pulse", "Doc", "Rook",
    "Kapkan", "Tachanka", "Jäger", "Bandit", "Frost", "Valkyrie",
    "Caveira", "Echo", "Mira", "Lesion", "Ela", "Vigil",
    "Maestro", "Alibi", "Clash", "Kaid", "Mozzie", "Warden",
    "Goyo", "Wamai", "Oryx", "Melusi", "Aruni", "Thunderbird",
    "Thorn", "Azami", "Solis", "Fenrir", "Tubarao",
]

# Keep these "requirements" generic so they work across platforms/players.
REQUIREMENTS = [
    "Must be crouched",
    "Must be prone",
    "Must be standing (not crouched/prone)",
    "Must be moving (no holding angle)",
    "Must be ADS when finishing shot",
    "Must hipfire (no ADS)",
    "Must be inside objective room",
    "Must be outside objective room",
    "Must be within 5m",
    "Must be beyond 10m",
    "Must be headshot",
    "Must be wallbang",
    "Must be through a soft wall",
    "Must be while peeking (not holding)",
    "Must be while leaning",
    "Must be after a reload",
    "Must be without taking damage",
    "Must not sprint for 10s before kill",
    "Must be on low health (<50) at time of kill",
    "Must be using a shotgun",
    "Must be using a pistol",
    "Must be using an SMG",
    "Must be using an AR",
    "Must be using a DMR",
    "Must be using a sniper",
    "Must be using a melee (knife)",
    "Must be using a suppressor",
    "Must be using iron sights",
    "Must not use gadgets this life",
]

# Scoring: 1st claim = most points, later = fewer.
# With 6 case files, typical: 10, 7, 5, 3, 2, 1
DEFAULT_POINTS_BY_PLACE = [10, 7, 5, 3, 2, 1]


def _rid(n=6) -> str:
    return "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(n))


@dataclass
class CaseFile:
    id: str
    side: str
    targets: List[str]
    requirements: List[str]
    claimed_by: Optional[str] = None  # player_id
    claimed_at: Optional[float] = None


@dataclass
class Player:
    id: str
    name: str
    score: int = 0
    joined_at: float = 0.0


class LobbyState:
    def __init__(self, lobby_code: str):
        self.lobby_code = lobby_code
        self.players: Dict[str, Player] = {}
        self.host_id: Optional[str] = None
        self.round_active: bool = False
        self.case_files: List[CaseFile] = []
        self.claim_order: List[str] = []  # list of case_file ids in order claimed
        self.points_by_place = list(DEFAULT_POINTS_BY_PLACE)

    def to_public(self):
        # Public-safe state for clients
        return {
            "lobby_code": self.lobby_code,
            "host_id": self.host_id,
            "round_active": self.round_active,
            "players": [asdict(p) for p in sorted(self.players.values(), key=lambda x: (-x.score, x.joined_at))],
            "case_files": [asdict(cf) for cf in self.case_files],
            "claim_order": self.claim_order,
            "points_by_place": self.points_by_place,
        }

    def new_round(self):
        self.round_active = True
        self.claim_order = []

        self.case_files = []
        sides = ["Attackers"] * 3 + ["Defenders"] * 3
        random.shuffle(sides)
        for side in sides:
            pool = ATTACKERS if side == "Attackers" else DEFENDERS
            targets = random.sample(pool, k=6) if len(pool) >= 6 else [random.choice(pool) for _ in range(6)]
            reqs = random.sample(REQUIREMENTS, k=3) if len(REQUIREMENTS) >= 3 else random.choices(REQUIREMENTS, k=3)
            self.case_files.append(
                CaseFile(
                    id=_rid(8),
                    side=side,
                    targets=targets,
                    requirements=reqs,
                )
            )

    def end_round_if_done(self):
        if self.round_active and all(cf.claimed_by is not None for cf in self.case_files):
            self.round_active = False


LOBBIES: Dict[str, LobbyState] = {}


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def index():
    return render_template("index.html")


# -----------------------------
# Socket events
# -----------------------------
@socketio.on("create_lobby")
def create_lobby(payload):
    name = (payload.get("name") or "").strip() or "Host"
    lobby_code = _rid(5)

    lobby = LobbyState(lobby_code)
    LOBBIES[lobby_code] = lobby

    player_id = request.sid
    lobby.players[player_id] = Player(id=player_id, name=name, score=0, joined_at=time.time())
    lobby.host_id = player_id

    join_room(lobby_code)

    emit("lobby_joined", {"player_id": player_id, "lobby_code": lobby_code, "is_host": True})
    socketio.emit("state", lobby.to_public(), room=lobby_code)


@socketio.on("join_lobby")
def join_lobby_evt(payload):
    name = (payload.get("name") or "").strip() or "Player"
    lobby_code = (payload.get("lobby_code") or "").strip().upper()

    lobby = LOBBIES.get(lobby_code)
    if not lobby:
        emit("error_msg", {"message": "Lobby not found. Check the code."})
        return

    player_id = request.sid
    lobby.players[player_id] = Player(id=player_id, name=name, score=0, joined_at=time.time())

    join_room(lobby_code)

    emit("lobby_joined", {"player_id": player_id, "lobby_code": lobby_code, "is_host": (player_id == lobby.host_id)})
    socketio.emit("state", lobby.to_public(), room=lobby_code)


@socketio.on("start_round")
def start_round(payload):
    lobby_code = (payload.get("lobby_code") or "").strip().upper()
    lobby = LOBBIES.get(lobby_code)
    if not lobby:
        emit("error_msg", {"message": "Lobby not found."})
        return

    if request.sid != lobby.host_id:
        emit("error_msg", {"message": "Only the host can start the round."})
        return

    # Optional: allow host to customize points
    points = payload.get("points_by_place")
    if isinstance(points, list) and all(isinstance(x, int) for x in points) and len(points) >= 6:
        lobby.points_by_place = points[:6]
    else:
        lobby.points_by_place = list(DEFAULT_POINTS_BY_PLACE)

    lobby.new_round()
    socketio.emit("state", lobby.to_public(), room=lobby_code)


@socketio.on("claim_kill")
def claim_kill(payload):
    lobby_code = (payload.get("lobby_code") or "").strip().upper()
    case_id = (payload.get("case_id") or "").strip()

    lobby = LOBBIES.get(lobby_code)
    if not lobby:
        emit("error_msg", {"message": "Lobby not found."})
        return

    if not lobby.round_active:
        emit("error_msg", {"message": "Round not active."})
        return

    player_id = request.sid
    if player_id not in lobby.players:
        emit("error_msg", {"message": "You are not in this lobby."})
        return

    case = next((c for c in lobby.case_files if c.id == case_id), None)
    if not case:
        emit("error_msg", {"message": "Case file not found."})
        return

    if case.claimed_by is not None:
        emit("error_msg", {"message": "That target has already been claimed."})
        return

    # Claim it
    case.claimed_by = player_id
    case.claimed_at = time.time()

    lobby.claim_order.append(case.id)
    place_index = len(lobby.claim_order) - 1
    points_awarded = lobby.points_by_place[place_index] if place_index < len(lobby.points_by_place) else 1

    lobby.players[player_id].score += points_awarded

    lobby.end_round_if_done()
    socketio.emit("state", lobby.to_public(), room=lobby_code)


@socketio.on("reset_scores")
def reset_scores(payload):
    lobby_code = (payload.get("lobby_code") or "").strip().upper()
    lobby = LOBBIES.get(lobby_code)
    if not lobby:
        emit("error_msg", {"message": "Lobby not found."})
        return

    if request.sid != lobby.host_id:
        emit("error_msg", {"message": "Only the host can reset scores."})
        return

    for p in lobby.players.values():
        p.score = 0

    lobby.round_active = False
    lobby.case_files = []
    lobby.claim_order = []
    socketio.emit("state", lobby.to_public(), room=lobby_code)


@socketio.on("disconnect")
def on_disconnect():
    # Remove player from lobby; if host leaves, assign new host if possible
    sid = request.sid
    for lobby_code, lobby in list(LOBBIES.items()):
        if sid in lobby.players:
            del lobby.players[sid]

            if lobby.host_id == sid:
                # pick a new host if anyone remains
                remaining = list(lobby.players.keys())
                lobby.host_id = remaining[0] if remaining else None

            # If no one left, delete lobby
            if not lobby.players:
                del LOBBIES[lobby_code]
                return

            socketio.emit("state", lobby.to_public(), room=lobby_code)
            return


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
