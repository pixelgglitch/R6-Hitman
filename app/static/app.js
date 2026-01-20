const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
const socket = new WebSocket(`${wsProtocol}://${window.location.host}/ws`);

const caseFilesEl = document.getElementById("case-files");
const scoreboardEl = document.getElementById("scoreboard");
const joinBtn = document.getElementById("join");
const joinInput = document.getElementById("player-name");
const newGameBtn = document.getElementById("new-game");
const caseTemplate = document.getElementById("case-template");

let playerId = null;

function render(state) {
  const players = state.players ?? [];
  const caseFiles = state.case_files ?? [];

  caseFilesEl.innerHTML = "";
  caseFiles.forEach((caseFile) => {
    const node = caseTemplate.content.cloneNode(true);
    const title = node.querySelector("h3");
    const status = node.querySelector(".status");
    const requirements = node.querySelector(".requirements");
    const claim = node.querySelector(".claim");
    const killOrder = node.querySelector(".kill-order");

    title.textContent = caseFile.operator;
    status.textContent = `${caseFile.kill_order.length}/${players.length} confirmed`;

    requirements.innerHTML = "";
    caseFile.requirements.forEach((req) => {
      const li = document.createElement("li");
      li.textContent = req;
      requirements.appendChild(li);
    });

    claim.disabled = !playerId || caseFile.kill_order.includes(playerId);
    claim.addEventListener("click", () => {
      socket.send(JSON.stringify({ action: "kill", case_id: caseFile.case_id }));
    });

    if (caseFile.kill_order.length) {
      const orderList = caseFile.kill_order
        .map((id, index) => {
          const player = players.find((p) => p.player_id === id);
          const name = player ? player.name : "Unknown";
          return `${index + 1}. ${name}`;
        })
        .join(" · ");
      killOrder.textContent = `Order: ${orderList}`;
    }

    caseFilesEl.appendChild(node);
  });

  const sortedPlayers = [...players].sort((a, b) => b.score - a.score);
  scoreboardEl.innerHTML = "";
  sortedPlayers.forEach((player) => {
    const row = document.createElement("div");
    row.className = "score-row";
    row.innerHTML = `
      <span>${player.name}</span>
      <strong>${player.score}</strong>
    `;
    scoreboardEl.appendChild(row);
  });
}

joinBtn.addEventListener("click", () => {
  const name = joinInput.value.trim();
  if (!name) {
    joinInput.focus();
    return;
  }
  socket.send(JSON.stringify({ action: "join", name }));
});

newGameBtn.addEventListener("click", () => {
  socket.send(JSON.stringify({ action: "new_game" }));
});

socket.addEventListener("message", (event) => {
  const payload = JSON.parse(event.data);
  if (payload.type === "joined") {
    playerId = payload.player_id;
    return;
  }
  if (payload.type === "state") {
    render(payload);
  }
});
