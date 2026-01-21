const socket = io();

let playerId = null;
let lobbyCode = null;
let isHost = false;

const el = (id) => document.getElementById(id);

function setConnected(ok) {
  el("connStatus").textContent = ok ? "Connected" : "Disconnected";
  el("connStatus").className = ok ? "pill ok" : "pill bad";
}

socket.on("connect", () => setConnected(true));
socket.on("disconnect", () => setConnected(false));

el("createBtn").addEventListener("click", () => {
  const name = el("nameInput").value.trim() || "Host";
  socket.emit("create_lobby", { name });
});

el("joinBtn").addEventListener("click", () => {
  const name = el("nameInput").value.trim() || "Player";
  const code = el("codeInput").value.trim().toUpperCase();
  if (!code) {
    el("joinHint").textContent = "Enter a lobby code to join.";
    return;
  }
  socket.emit("join_lobby", { name, lobby_code: code });
});

el("startRoundBtn").addEventListener("click", () => {
  socket.emit("start_round", { lobby_code: lobbyCode });
});

el("resetScoresBtn").addEventListener("click", () => {
  socket.emit("reset_scores", { lobby_code: lobbyCode });
});

socket.on("error_msg", (p) => {
  alert(p.message || "Error");
});

socket.on("lobby_joined", (p) => {
  playerId = p.player_id;
  lobbyCode = p.lobby_code;
  isHost = !!p.is_host;

  el("joinCard").classList.add("hidden");
  el("lobbyCard").classList.remove("hidden");

  el("lobbyCodeLabel").textContent = lobbyCode;
  el("roleLabel").textContent = isHost ? "You are the host." : "You are a player.";

  el("startRoundBtn").classList.toggle("hidden", !isHost);
  el("resetScoresBtn").classList.toggle("hidden", !isHost);
});

socket.on("state", (state) => {
  if (!state) return;

  // Update host status if host changed
  isHost = (state.host_id === playerId);
  el("roleLabel").textContent = isHost ? "You are the host." : "You are a player.";
  el("startRoundBtn").classList.toggle("hidden", !isHost);
  el("resetScoresBtn").classList.toggle("hidden", !isHost);

  // Round status
  el("roundStatus").textContent = state.round_active
    ? "Round active: claim kills as fast as possible."
    : (state.case_files && state.case_files.length ? "Round finished." : "No round running.");

  renderPlayers(state.players || []);
  renderCases(state.case_files || [], state.players || [], state.points_by_place || []);
  renderOrder(state.claim_order || [], state.case_files || [], state.players || []);
});

function renderPlayers(players) {
  const wrap = el("players");
  wrap.innerHTML = "";
  players.forEach((p, idx) => {
    const div = document.createElement("div");
    div.className = "player";
    div.innerHTML = `
      <div class="playerName">${idx + 1}. ${escapeHtml(p.name)}</div>
      <div class="playerScore">${p.score} pts</div>
    `;
    wrap.appendChild(div);
  });
}

function renderCases(caseFiles, players, pointsByPlace) {
  const wrap = el("caseFiles");
  wrap.innerHTML = "";

  const playerNameById = {};
  players.forEach(p => playerNameById[p.id] = p.name);

  caseFiles.forEach((cf) => {
    const card = document.createElement("div");
    card.className = "case";

    const claimed = cf.claimed_by != null;
    const claimedName = claimed ? (playerNameById[cf.claimed_by] || "Unknown") : null;

    const btnDisabled = claimed;

    card.innerHTML = `
      <div class="caseTop">
        <div class="tag">${escapeHtml(cf.side || "Targets")}</div>
        <div class="target">${(cf.targets || []).map(t => escapeHtml(t)).join(", ")}</div>
      </div>

      <div class="reqs">
        ${cf.requirements.map(r => `<div class="req">• ${escapeHtml(r)}</div>`).join("")}
      </div>

      <div class="caseBottom">
        <div class="claimed">
          ${claimed ? `Claimed by <b>${escapeHtml(claimedName)}</b>` : "Unclaimed — kill any one target"}
        </div>
        <button class="${claimed ? "secondary" : ""}" ${btnDisabled ? "disabled" : ""}>
          ${claimed ? "Claimed" : "Claim Kill"}
        </button>
      </div>
    `;

    const btn = card.querySelector("button");
    btn.addEventListener("click", () => {
      socket.emit("claim_kill", { lobby_code: lobbyCode, case_id: cf.id });
    });

    wrap.appendChild(card);
  });

  if (!caseFiles.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "No case files yet. Host: click Start round.";
    wrap.appendChild(empty);
  }
}

function renderOrder(orderIds, caseFiles, players) {
  const list = el("claimOrder");
  list.innerHTML = "";

  const cfById = {};
  caseFiles.forEach(cf => cfById[cf.id] = cf);

  const playerNameById = {};
  players.forEach(p => playerNameById[p.id] = p.name);

  orderIds.forEach((cid, idx) => {
    const cf = cfById[cid];
    const li = document.createElement("li");
    if (!cf) {
      li.textContent = `#${idx + 1}: (unknown)`;
    } else {
      const who = playerNameById[cf.claimed_by] || "Unknown";
      const label = cf.side ? `${cf.side} file` : "Case file";
      li.textContent = `#${idx + 1}: ${label} — ${who}`;
    }
    list.appendChild(li);
  });

  if (!orderIds.length) {
    const li = document.createElement("li");
    li.className = "muted";
    li.textContent = "No kills claimed yet.";
    list.appendChild(li);
  }
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
