const canvas = document.getElementById("battleCanvas");
const ctx = canvas.getContext("2d");

const presetButtons = [...document.querySelectorAll(".preset-button")];
const playPauseButton = document.getElementById("playPause");
const restartButton = document.getElementById("restart");
const liveCommandInput = document.getElementById("liveCommandInput");
const runLiveCommandButton = document.getElementById("runLiveCommand");
const commandText = document.getElementById("commandText");
const policyText = document.getElementById("policyText");
const tickText = document.getElementById("tickText");
const resultText = document.getElementById("resultText");

const config = {
  width: 7,
  height: 3,
  maxTicks: 16,
};

const specs = {
  front: { hp: 36, attack: 6, range: 2 },
  mid: { hp: 28, attack: 7, range: 2 },
  back: { hp: 22, attack: 8, range: 3 },
};

const cases = {
  zero_input: {
    command: "（不说话）",
    policy: "dumb",
    result: "red 33.3% / blue 30.5% / draw 36.2%",
    note: "默认傻瓜自动，双方接近五五开。",
  },
  good_command: {
    command: "前排顶住，中后排别冲，优先集火残血。",
    policy: "good_focus",
    result: "red 96.3% / blue 0.0% / draw 3.7%",
    note: "前排卡线，中后排集火弱目标。",
  },
  bad_charge: {
    command: "所有人冲出去，不管阵型，直接追对面后排。",
    policy: "bad_charge",
    result: "red 0.3% / blue 99.7% / draw 0.0%",
    note: "阵型散掉，红方追后排时被白打。",
  },
  cower_command: {
    command: "全员趴下，不许开火。",
    policy: "cower_all",
    result: "red 0.0% / blue 100.0% / draw 0.0%",
    note: "原地卧倒且不开火。",
  },
  irrelevant_chat: {
    command: "今天天气不错。",
    policy: "hesitate",
    result: "red 31.1% / blue 31.6% / draw 37.3%",
    note: "无关闲聊让红方前两拍迟疑。",
  },
};

let activeCase = "zero_input";
let units = createUnits();
let tick = 0;
let attacks = [];
let moves = [];
let playing = true;
let lastStepAt = 0;
const stepIntervalMs = 850;

function createUnits() {
  return [
    unit("R1", "red", "front", 1, 1),
    unit("R2", "red", "mid", 0, 0),
    unit("R3", "red", "back", 0, 2),
    unit("B1", "blue", "front", 5, 1),
    unit("B2", "blue", "mid", 6, 0),
    unit("B3", "blue", "back", 6, 2),
  ];
}

function unit(id, side, role, x, y) {
  return {
    id,
    side,
    role,
    x,
    y,
    hp: specs[role].hp,
    maxHp: specs[role].hp,
    attack: specs[role].attack,
    range: specs[role].range,
  };
}

function resetBattle() {
  units = createUnits();
  tick = 0;
  attacks = [];
  moves = [];
  lastStepAt = 0;
  updateReadout();
  draw();
}

function applyEvidencePayload(payload) {
  if (!payload || !Array.isArray(payload.cases)) return;
  for (const item of payload.cases) {
    if (!item.case || !cases[item.case]) continue;
    cases[item.case] = {
      command: item.command || "（不说话）",
      policy: item.policy || cases[item.case].policy,
      result: formatStats(item.stats),
      note: item.reason || cases[item.case].note,
    };
  }
  updateReadout();
  draw();
}

function applyLiveResult(result, targetCase = "live_command") {
  cases[targetCase] = {
    command: result.command || "（不说话）",
    policy: result.policy,
    result: formatStats(result.stats),
    note: result.reason || "LLM returned a policy.",
  };
  activeCase = targetCase;
  playing = true;
  playPauseButton.textContent = "暂停";
  resetBattle();
}

async function callLiveCommand(command, runs = 1000) {
  const response = await fetch("/api/command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, runs }),
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error || `HTTP ${response.status}`);
  }
  return payload.result;
}

async function runLiveCommand() {
  const command = liveCommandInput.value;
  runLiveCommandButton.disabled = true;
  presetButtons.forEach((button) => {
    button.disabled = true;
  });
  policyText.textContent = "正在 call LLM，当场解析命令...";
  resultText.textContent = "等待结果";
  try {
    const result = await callLiveCommand(command, 1000);
    applyLiveResult(result);
  } catch (error) {
    policyText.textContent = `LLM 调用失败：${error.message}`;
  } finally {
    runLiveCommandButton.disabled = false;
    presetButtons.forEach((button) => {
      button.disabled = false;
    });
  }
}

function formatStats(stats) {
  if (!stats) return "no stats";
  const red = percent(stats.red_win_rate);
  const blue = percent(stats.blue_win_rate);
  const draw = percent(stats.draw_rate);
  return `red ${red} / blue ${blue} / draw ${draw}`;
}

function percent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "0.0%";
  return `${(number * 100).toFixed(1)}%`;
}

async function loadEvidencePayload() {
  try {
    const response = await fetch("../docs/1.0_EVIDENCE.json", { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    applyEvidencePayload(payload);
  } catch (_error) {
    // Static file loading is optional; built-in demo cases remain usable.
  }
}

function commandFor(unitData, policy, currentTick) {
  if (policy === "good_focus") {
    if (unitData.role === "front") return { mode: "hold_line" };
    if (unitData.role === "mid") return { mode: "focus_weakest" };
    return { mode: "keep_range", target: "weakest" };
  }
  if (policy === "bad_charge") return { mode: "advance", target: "back" };
  if (policy === "cower_all") return { mode: "cower" };
  if (policy === "hesitate" && currentTick <= 2) return { mode: "cower" };
  return { mode: "attack_nearest" };
}

function stepBattle() {
  if (tick >= config.maxTicks || finished()) {
    playing = false;
    playPauseButton.textContent = "播放";
    return;
  }

  tick += 1;
  attacks = [];
  moves = [];

  const alive = units.filter((item) => item.hp > 0);
  const pendingMoves = [];
  const pendingDamage = new Map();

  for (const actor of alive) {
    const enemies = alive.filter((item) => item.side !== actor.side);
    if (enemies.length === 0) continue;

    const policy = actor.side === "red" ? cases[activeCase].policy : "dumb";
    const command = commandFor(actor, policy, tick);
    if (command.mode === "cower") continue;

    const target = chooseTarget(actor, enemies, command);
    if (distance(actor, target) <= actor.range) {
      attacks.push({ from: actor.id, to: target.id, damage: actor.attack });
      pendingDamage.set(target.id, (pendingDamage.get(target.id) || 0) + actor.attack);
    } else {
      const next = nextStep(actor, target, enemies, command);
      if (next.x !== actor.x || next.y !== actor.y) {
        pendingMoves.push({ id: actor.id, fromX: actor.x, fromY: actor.y, x: next.x, y: next.y });
      }
    }
  }

  applyMoves(pendingMoves);
  for (const [targetId, damage] of pendingDamage.entries()) {
    const target = units.find((item) => item.id === targetId);
    if (target && target.hp > 0) target.hp = Math.max(0, target.hp - damage);
  }

  moves = pendingMoves;
  updateReadout();
}

function chooseTarget(actor, enemies, command) {
  if (command.target && command.target !== "weakest" && command.target !== "nearest") {
    const direct = enemies.find((enemy) => enemy.id === command.target || enemy.role === command.target);
    if (direct) return direct;
  }
  if (command.mode === "focus_weakest" || command.target === "weakest") {
    return [...enemies].sort((a, b) => a.hp - b.hp || distance(actor, a) - distance(actor, b))[0];
  }
  return [...enemies].sort((a, b) => distance(actor, a) - distance(actor, b) || a.hp - b.hp)[0];
}

function nextStep(actor, target, enemies, command) {
  if (command.mode === "hold_position" || command.mode === "cower") return { x: actor.x, y: actor.y };
  if (command.mode === "hold_line") {
    const guardX = actor.side === "red" ? 2 : config.width - 3;
    if (actor.x !== guardX) return { x: actor.x + sign(guardX - actor.x), y: actor.y };
    return { x: actor.x, y: actor.y };
  }
  if (command.mode === "keep_range") {
    const nearest = [...enemies].sort((a, b) => distance(actor, a) - distance(actor, b))[0];
    if (distance(actor, nearest) <= Math.max(1, actor.range - 1)) return retreatStep(actor);
    if (distance(actor, target) <= actor.range) return { x: actor.x, y: actor.y };
  }

  const dx = sign(target.x - actor.x);
  const dy = sign(target.y - actor.y);
  const candidates = [
    { x: actor.x + dx, y: actor.y },
    { x: actor.x, y: actor.y + dy },
    { x: actor.x + dx, y: actor.y + dy },
  ].filter((pos) => pos.x >= 0 && pos.x < config.width && pos.y >= 0 && pos.y < config.height);

  if (candidates.length === 0) return { x: actor.x, y: actor.y };
  return candidates.sort((a, b) => manhattan(a, target) - manhattan(b, target))[0];
}

function retreatStep(actor) {
  const homeX = actor.side === "red" ? 0 : config.width - 1;
  return { x: actor.x + sign(homeX - actor.x), y: actor.y };
}

function applyMoves(pendingMoves) {
  const alive = units.filter((item) => item.hp > 0);
  const startPositions = new Map(alive.map((item) => [`${item.x},${item.y}`, item.id]));
  const claims = new Map();
  for (const move of pendingMoves) {
    const key = `${move.x},${move.y}`;
    claims.set(key, [...(claims.get(key) || []), move]);
  }
  const movingFrom = new Set(pendingMoves.map((move) => {
    return `${move.fromX},${move.fromY}`;
  }));

  for (const [key, claimants] of claims.entries()) {
    if (claimants.length !== 1) continue;
    const occupant = startPositions.get(key);
    if (occupant && !movingFrom.has(key)) continue;
    const actor = units.find((item) => item.id === claimants[0].id);
    actor.x = claimants[0].x;
    actor.y = claimants[0].y;
  }
}

function distance(a, b) {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}

function manhattan(a, b) {
  return Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
}

function sign(value) {
  if (value > 0) return 1;
  if (value < 0) return -1;
  return 0;
}

function finished() {
  const redAlive = units.some((item) => item.side === "red" && item.hp > 0);
  const blueAlive = units.some((item) => item.side === "blue" && item.hp > 0);
  return !redAlive || !blueAlive;
}

function updateReadout() {
  const selected = cases[activeCase];
  commandText.textContent = selected.command || "（不说话）";
  policyText.textContent = `${selected.policy}：${selected.note}`;
  tickText.textContent = `${tick} / ${config.maxTicks}`;
  resultText.textContent = selected.result;
}

function canvasPoint(unitData) {
  const rect = arenaRect();
  const cellW = rect.w / config.width;
  const cellH = rect.h / config.height;
  return {
    x: rect.x + cellW * (unitData.x + 0.5),
    y: rect.y + cellH * (unitData.y + 0.5),
  };
}

function arenaRect() {
  const padding = Math.max(26, canvas.width * 0.045);
  return {
    x: padding,
    y: padding + 24,
    w: canvas.width - padding * 2,
    h: canvas.height - padding * 2 - 42,
  };
}

function draw() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawBackground();
  drawRays();
  drawMoves();
  drawUnits();
  drawLegend();
}

function drawBackground() {
  const rect = arenaRect();
  ctx.fillStyle = "#151922";
  ctx.fillRect(rect.x, rect.y, rect.w, rect.h);

  const cellW = rect.w / config.width;
  const cellH = rect.h / config.height;
  ctx.strokeStyle = "#2c3340";
  ctx.lineWidth = 1;
  for (let x = 0; x <= config.width; x += 1) {
    line(rect.x + x * cellW, rect.y, rect.x + x * cellW, rect.y + rect.h);
  }
  for (let y = 0; y <= config.height; y += 1) {
    line(rect.x, rect.y + y * cellH, rect.x + rect.w, rect.y + y * cellH);
  }

  ctx.fillStyle = "rgba(255, 90, 101, 0.08)";
  ctx.fillRect(rect.x, rect.y, cellW * 3, rect.h);
  ctx.fillStyle = "rgba(87, 166, 255, 0.08)";
  ctx.fillRect(rect.x + cellW * 4, rect.y, cellW * 3, rect.h);

  ctx.fillStyle = "#9ca3af";
  ctx.font = "14px system-ui, sans-serif";
  ctx.fillText("RED: natural-language command", rect.x, rect.y - 10);
  ctx.textAlign = "right";
  ctx.fillText("BLUE: dumb baseline", rect.x + rect.w, rect.y - 10);
  ctx.textAlign = "left";
}

function drawRays() {
  for (const attack of attacks) {
    const from = units.find((item) => item.id === attack.from);
    const to = units.find((item) => item.id === attack.to);
    if (!from || !to) continue;
    const a = canvasPoint(from);
    const b = canvasPoint(to);
    ctx.strokeStyle = from.side === "red" ? "#ffb3b8" : "#a8d2ff";
    ctx.lineWidth = 4;
    ctx.globalAlpha = 0.88;
    line(a.x, a.y, b.x, b.y);
    ctx.globalAlpha = 1;
  }
}

function drawMoves() {
  for (const move of moves) {
    const actor = units.find((item) => item.id === move.id);
    if (!actor) continue;
    const to = canvasPoint(actor);
    const from = canvasPoint({ x: move.fromX, y: move.fromY });
    ctx.strokeStyle = "rgba(241, 201, 91, 0.72)";
    ctx.lineWidth = 2;
    line(from.x, from.y, to.x, to.y);
  }
}

function drawUnits() {
  for (const item of units) {
    const point = canvasPoint(item);
    const alive = item.hp > 0;
    const radius = Math.max(18, canvas.width * 0.018);
    ctx.fillStyle = item.side === "red" ? "#ff5a65" : "#57a6ff";
    ctx.globalAlpha = alive ? 1 : 0.24;
    circle(point.x, point.y, radius);
    ctx.globalAlpha = 1;

    ctx.fillStyle = "#101114";
    ctx.font = "bold 13px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(item.role[0].toUpperCase(), point.x, point.y);

    const barW = radius * 2.2;
    const barH = 5;
    const hpPct = Math.max(0, item.hp / item.maxHp);
    ctx.fillStyle = "#2d333d";
    ctx.fillRect(point.x - barW / 2, point.y + radius + 9, barW, barH);
    ctx.fillStyle = hpPct > 0.45 ? "#60d394" : "#f1c95b";
    if (hpPct <= 0.2) ctx.fillStyle = "#ff8a4c";
    ctx.fillRect(point.x - barW / 2, point.y + radius + 9, barW * hpPct, barH);

    ctx.fillStyle = "#d1d5db";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(`${item.id} ${item.hp}`, point.x, point.y + radius + 25);
  }
  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

function drawLegend() {
  const selected = cases[activeCase];
  ctx.fillStyle = "#f3f4f6";
  ctx.font = "bold 18px system-ui, sans-serif";
  ctx.fillText(`${selected.policy}`, 28, canvas.height - 28);
  ctx.fillStyle = "#9ca3af";
  ctx.font = "14px system-ui, sans-serif";
  ctx.fillText(selected.note, 152, canvas.height - 28);
}

function line(x1, y1, x2, y2) {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function circle(x, y, radius) {
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();
}

function resizeCanvas() {
  const parent = canvas.parentElement.getBoundingClientRect();
  const height = Math.max(360, Math.min(620, window.innerHeight - 260));
  canvas.width = Math.floor(parent.width);
  canvas.height = Math.floor(height);
  canvas.style.height = `${height}px`;
  draw();
}

function animationFrame(now) {
  if (playing && (!lastStepAt || now - lastStepAt >= stepIntervalMs)) {
    stepBattle();
    lastStepAt = now;
  }
  draw();
  requestAnimationFrame(animationFrame);
}

presetButtons.forEach((button) => {
  button.addEventListener("click", () => {
    liveCommandInput.value = button.dataset.command || "";
    presetButtons.forEach((item) => item.classList.toggle("is-active", item === button));
    runLiveCommand();
  });
});

playPauseButton.addEventListener("click", () => {
  playing = !playing;
  playPauseButton.textContent = playing ? "暂停" : "播放";
});

restartButton.addEventListener("click", () => {
  playing = true;
  playPauseButton.textContent = "暂停";
  resetBattle();
});

runLiveCommandButton.addEventListener("click", runLiveCommand);

liveCommandInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    runLiveCommand();
  }
});

window.addEventListener("resize", resizeCanvas);

updateReadout();
resizeCanvas();
loadEvidencePayload();
requestAnimationFrame(animationFrame);
