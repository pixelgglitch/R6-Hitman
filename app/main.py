from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass, field
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

OPERATORS = [
    "Ash",
    "Sledge",
    "Thermite",
    "Twitch",
    "Hibana",
    "Buck",
    "Zofia",
    "Iana",
    "Ace",
    "Flores",
    "Zero",
    "Nomad",
    "Kali",
    "Maverick",
    "Nokk",
    "Vigil",
    "Smoke",
    "Mute",
    "Jager",
    "Bandit",
    "Kapkan",
    "Lesion",
    "Valkyrie",
    "Caveira",
]

REQUIREMENTS = [
    "Must be crouched",
    "Must be prone",
    "Must be on rappel",
    "Must be in the objective",
    "Must be outside",
    "Use a silenced weapon",
    "Use a sidearm",
    "Use a shotgun",
    "Use a melee finisher",
    "Use a throwable gadget",
    "Cannot take damage",
    "Cannot reload",
    "Must be alone",
    "Must be above target",
    "Must be below target",
]


@dataclass
class Player:
    player_id: str
    name: str
    score: int = 0


@dataclass
class CaseFile:
    case_id: str
    operator: str
    requirements: List[str]
    kill_order: List[str] = field(default_factory=list)


class GameState:
    def __init__(self) -> None:
        self.players: Dict[str, Player] = {}
        self.case_files: List[CaseFile] = []

    def new_game(self) -> None:
        operators = random.sample(OPERATORS, k=6)
        self.case_files = []
        for operator in operators:
            requirements = random.sample(REQUIREMENTS, k=3)
            self.case_files.append(
                CaseFile(
                    case_id=str(uuid.uuid4()),
                    operator=operator,
                    requirements=requirements,
                )
            )
        for player in self.players.values():
            player.score = 0

    def add_player(self, name: str) -> Player:
        player_id = str(uuid.uuid4())
        player = Player(player_id=player_id, name=name)
        self.players[player_id] = player
        if not self.case_files:
            self.new_game()
        return player

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        for case_file in self.case_files:
            if player_id in case_file.kill_order:
                case_file.kill_order.remove(player_id)

    def record_kill(self, player_id: str, case_id: str) -> None:
        case_file = next((case for case in self.case_files if case.case_id == case_id), None)
        if case_file is None or player_id in case_file.kill_order:
            return

        case_file.kill_order.append(player_id)
        total_players = max(len(self.players), 1)
        order = len(case_file.kill_order)
        player = self.players.get(player_id)
        if player is None:
            return

        if order == 1:
            player.score += 3
        elif order == total_players:
            player.score += 1
        else:
            player.score += 2

    def to_payload(self) -> dict:
        return {
            "players": [
                {
                    "player_id": player.player_id,
                    "name": player.name,
                    "score": player.score,
                }
                for player in self.players.values()
            ],
            "case_files": [
                {
                    "case_id": case.case_id,
                    "operator": case.operator,
                    "requirements": case.requirements,
                    "kill_order": case.kill_order,
                }
                for case in self.case_files
            ],
        }


app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
state = GameState()


@app.get("/")
def index() -> HTMLResponse:
    with open("app/static/index.html", "r", encoding="utf-8") as handle:
        return HTMLResponse(handle.read())


class ConnectionManager:
    def __init__(self) -> None:
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, player_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active[player_id] = websocket

    def disconnect(self, player_id: str) -> None:
        self.active.pop(player_id, None)

    async def broadcast(self, payload: dict) -> None:
        message = json.dumps(payload)
        for websocket in list(self.active.values()):
            await websocket.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    player: Player | None = None
    try:
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "ready"}))
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")
            if action == "join":
                name = payload.get("name", "Player")
                player = state.add_player(name)
                manager.active[player.player_id] = websocket
                await websocket.send_text(
                    json.dumps({"type": "joined", "player_id": player.player_id})
                )
                await manager.broadcast({"type": "state", **state.to_payload()})
            elif action == "kill" and player is not None:
                state.record_kill(player.player_id, payload.get("case_id", ""))
                await manager.broadcast({"type": "state", **state.to_payload()})
            elif action == "new_game":
                state.new_game()
                await manager.broadcast({"type": "state", **state.to_payload()})
    except WebSocketDisconnect:
        if player is not None:
            state.remove_player(player.player_id)
            manager.disconnect(player.player_id)
            await manager.broadcast({"type": "state", **state.to_payload()})
    except json.JSONDecodeError:
        await websocket.send_text(json.dumps({"type": "error", "message": "Bad payload."}))
