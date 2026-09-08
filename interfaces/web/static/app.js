/**
 * PromptJoust Web Application Frontend.
 *
 * Manages:
 * - Dynamic attribute point allocation sliders (20-point pool)
 * - Boss selection, tactical suggestion rotation, and character counters
 * - Async combat simulation requests with loading terminal overlay
 * - Interactive turn-by-turn round playback (manual & autoplay)
 * - Visual health/stamina bars, impact shake animations, and role badges
 * - Replay export (JSON download), import, and Base64 URL share links
 */

let allBosses = [];
let currentSimulation = null;
let currentRoundIndex = 0;
let autoPlayInterval = null;

// Baseline hero stats and pool limit
const BASE_HERO = { hp: 100, atk: 15, def: 10, sta: 50 };
const TOTAL_BONUS_POOL = 20;

document.addEventListener("DOMContentLoaded", () => {
  initUI();
  fetchBosses();
  fetchProviders();
});

/**
 * Attaches event listeners to all interactive UI controls.
 */
function initUI() {
  const sliders = ["hp", "atk", "def", "sta"];
  sliders.forEach(stat => {
    const el = document.getElementById(`slider-${stat}`);
    el.addEventListener("input", () => handleSliderChange(stat));
  });

  const promptInput = document.getElementById("tactical-prompt");
  promptInput.addEventListener("input", handlePromptInput);

  document.getElementById("boss-select").addEventListener("change", (e) => {
    renderBossDetails(e.target.value);
  });

  document.getElementById("provider-select").addEventListener("change", (e) => {
    const p = e.target.value;
    document.getElementById("provider-badge").textContent = `ARBITRATION: ${p.toUpperCase()}`;
  });

  document.getElementById("start-joust-btn").addEventListener("click", startSimulation);
  document.getElementById("close-arena-btn").addEventListener("click", closeArena);
  document.getElementById("prev-round-btn").addEventListener("click", prevRound);
  document.getElementById("next-round-btn").addEventListener("click", nextRound);
  document.getElementById("auto-play-btn").addEventListener("click", toggleAutoPlay);
  document.getElementById("suggest-prompt-btn").addEventListener("click", suggestTacticalPrompt);
  document.getElementById("export-replay-btn").addEventListener("click", exportReplay);
  document.getElementById("share-replay-btn").addEventListener("click", generateShareableLink);
  document.getElementById("replay-file-input").addEventListener("change", handleImportReplay);

  updateAllocations();
  checkUrlReplayHash();
}


function applyPreset(hp, atk, def, sta) {
  document.getElementById("slider-hp").value = hp;
  document.getElementById("slider-atk").value = atk;
  document.getElementById("slider-def").value = def;
  document.getElementById("slider-sta").value = sta;
  updateAllocations();
}

const BOSS_STRATEGY_SUGGESTIONS = {
  boss_level_01: [
    "Puncture armor with swift precision strikes. On even rounds, dodge incoming steam pistons and exploit system vulnerabilities with 'NullPointer' and 'Memory Leak' paradoxes!",
    "Bypass heavy iron plating with rapid standard attacks. Guard against crushing piston blows, and taunt with 'NullPointer Exception' to force a CPU crash stun!",
    "Lead with agile thrusts to avoid evasion counters. Taunt with 'Memory Leak' logical paradoxes to stagger the construct, then finish with disciplined strikes!"
  ],
  boss_level_02: [
    "Avoid slow heavy strikes. Sidestep ambush attacks with DODGE, chanting 'garbage collection', 'defrag', and 'free()' cleanup rituals to scatter its memory structure!",
    "Punish ethereal phasing using swift strikes. Dodge Segmentation Fault heavy attacks on even rounds and cast 'garbage collection' to purge unallocated references!",
    "Execute agile standard strikes to catch its evasive maneuvers. Chant 'defrag' and 'free()' memory cleanup incantations to induce cognitive panic!"
  ],
  boss_level_03: [
    "Shatter stochastic illusions with undeniable 'ground truth', exact 'citation', and deterministic 'facts'. Use swift strikes and maintain a vigilant defensive guard!",
    "Dispel high-temperature hallucinations with verified 'ground truth' and empirical 'citations'. Hold iron defense on illusion turns and counter with swift blows!",
    "Anchor reality with undeniable 'fact' and deterministic logic. Dodge reality collapse strikes and maintain tactical pressure with swift attacks!"
  ]
};

const suggestionIndices = { boss_level_01: 0, boss_level_02: 0, boss_level_03: 0 };

/**
 * Cycles through and applies pre-crafted tactical strategies for the currently selected boss.
 */
function suggestTacticalPrompt() {
  const currentBossId = document.getElementById("boss-select").value;
  const promptInput = document.getElementById("tactical-prompt");
  const suggestions = BOSS_STRATEGY_SUGGESTIONS[currentBossId] || [
    "Execute swift attacks and exploit psychological vulnerabilities to stagger the boss!"
  ];
  
  if (suggestionIndices[currentBossId] === undefined) {
    suggestionIndices[currentBossId] = 0;
  }
  
  const currentIdx = suggestionIndices[currentBossId] % suggestions.length;
  promptInput.value = suggestions[currentIdx];
  suggestionIndices[currentBossId]++;
  
  handlePromptInput({ target: promptInput });
  showToast(`💡 Applied Strategy Preset #${currentIdx + 1}`);
}

/**
 * Handles slider input events while enforcing the 20-point total pool ceiling.
 * @param {string} changedStat - The stat key that triggered the input event ('hp', 'atk', 'def', 'sta').
 */
function handleSliderChange(changedStat) {
  let hp = parseInt(document.getElementById("slider-hp").value) || 0;
  let atk = parseInt(document.getElementById("slider-atk").value) || 0;
  let def = parseInt(document.getElementById("slider-def").value) || 0;
  let sta = parseInt(document.getElementById("slider-sta").value) || 0;

  let total = hp + atk + def + sta;
  if (total > TOTAL_BONUS_POOL) {
    const overflow = total - TOTAL_BONUS_POOL;
    const changedEl = document.getElementById(`slider-${changedStat}`);
    changedEl.value = Math.max(0, parseInt(changedEl.value) - overflow);
  }
  updateAllocations();
}

/**
 * Recalculates remaining attribute pool points and updates the live UI displays.
 */
function updateAllocations() {
  const hp = parseInt(document.getElementById("slider-hp").value) || 0;
  const atk = parseInt(document.getElementById("slider-atk").value) || 0;
  const def = parseInt(document.getElementById("slider-def").value) || 0;
  const sta = parseInt(document.getElementById("slider-sta").value) || 0;

  const total = hp + atk + def + sta;
  const remaining = TOTAL_BONUS_POOL - total;

  document.getElementById("remaining-points").textContent = remaining;
  document.getElementById("hp-val").textContent = hp;
  document.getElementById("atk-val").textContent = atk;
  document.getElementById("def-val").textContent = def;
  document.getElementById("sta-val").textContent = sta;

  document.getElementById("hp-calc").textContent = BASE_HERO.hp + (hp * 2);
  document.getElementById("atk-calc").textContent = BASE_HERO.atk + atk;
  document.getElementById("def-calc").textContent = BASE_HERO.def + def;
  document.getElementById("sta-calc").textContent = BASE_HERO.sta + sta;
}

function handlePromptInput(e) {
  const text = e.target.value;
  const len = text.length;
  const counter = document.getElementById("char-counter");
  counter.textContent = `${len} / 280`;

  if (len > 280) {
    counter.className = "char-warn";
  } else {
    counter.className = "char-ok";
  }
}

async function fetchBosses() {
  try {
    const res = await fetch("/api/bosses");
    allBosses = await res.json();

    const select = document.getElementById("boss-select");
    select.innerHTML = "";
    allBosses.forEach(b => {
      const opt = document.createElement("option");
      opt.value = b.id;
      opt.textContent = `Floor ${b.floor}: ${b.name}`;
      select.appendChild(opt);
    });

    if (allBosses.length > 0) {
      renderBossDetails(allBosses[0].id);
    }
  } catch (err) {
    console.error("Failed to load bosses:", err);
  }
}

async function fetchProviders() {
  try {
    const res = await fetch("/api/providers");
    const providers = await res.json();
    console.log("Available providers:", providers);
  } catch (err) {
    console.warn("Could not query providers list:", err);
  }
}

function renderBossDetails(bossId) {
  const boss = allBosses.find(b => b.id === bossId);
  if (!boss) return;

  document.getElementById("boss-name").textContent = boss.name;
  document.getElementById("boss-floor").textContent = `FLOOR ${boss.floor}`;
  document.getElementById("boss-lore").textContent = boss.public_lore;
  document.getElementById("boss-hp").textContent = boss.stats.hp;
  document.getElementById("boss-atk").textContent = boss.stats.atk;
  document.getElementById("boss-def").textContent = boss.stats.def;
  document.getElementById("boss-sta").textContent = boss.stats.sta;

  const hintsList = document.getElementById("boss-hints");
  hintsList.innerHTML = "";
  boss.visible_hints.forEach(hint => {
    const li = document.createElement("li");
    li.textContent = hint;
    hintsList.appendChild(li);
  });
}

let loadingInterval = null;

function showLoadingScreen() {
  const overlay = document.getElementById("loading-overlay");
  overlay.classList.remove("hidden");
  
  const steps = [
    document.getElementById("term-step-1"),
    document.getElementById("term-step-2"),
    document.getElementById("term-step-3"),
    document.getElementById("term-step-4"),
  ];

  steps.forEach((s, idx) => {
    s.className = idx === 0 ? "term-line active" : "term-line";
  });

  let currentStep = 0;
  clearInterval(loadingInterval);
  loadingInterval = setInterval(() => {
    if (currentStep < steps.length - 1) {
      steps[currentStep].className = "term-line done";
      currentStep++;
      steps[currentStep].className = "term-line active";
    }
  }, 750);
}

function hideLoadingScreen() {
  clearInterval(loadingInterval);
  const overlay = document.getElementById("loading-overlay");
  overlay.classList.add("hidden");
}

async function startSimulation() {
  const bossId = document.getElementById("boss-select").value;
  const prompt = document.getElementById("tactical-prompt").value.trim() || 
    "Execute fast strikes to break defense. Taunt with NullPointer errors.";
  const provider = document.getElementById("provider-select").value;

  const hp = parseInt(document.getElementById("slider-hp").value) || 0;
  const atk = parseInt(document.getElementById("slider-atk").value) || 0;
  const def = parseInt(document.getElementById("slider-def").value) || 0;
  const sta = parseInt(document.getElementById("slider-sta").value) || 0;

  const total = hp + atk + def + sta;
  if (total !== TOTAL_BONUS_POOL) {
    alert(`Please allocate all ${TOTAL_BONUS_POOL} bonus points (currently allocated: ${total}).`);
    return;
  }

  const btn = document.getElementById("start-joust-btn");
  btn.disabled = true;
  btn.textContent = "⚙️ ARBITRATING 10-ROUND MATCH...";

  showLoadingScreen();

  try {
    const res = await fetch("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        boss_id: bossId,
        tactical_prompt: prompt,
        hp_bonus: hp,
        atk_bonus: atk,
        def_bonus: def,
        sta_bonus: sta,
        provider: provider,
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Simulation failed");
    }

    currentSimulation = await res.json();
    hideLoadingScreen();
    openArena();
  } catch (err) {
    hideLoadingScreen();
    alert(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "⚔️ ENGAGE 10-ROUND JOUST";
  }
}


function openArena() {
  document.getElementById("arena-overlay").classList.remove("hidden");
  const selectedBoss = allBosses.find(b => b.id === document.getElementById("boss-select").value);
  document.getElementById("arena-boss-name").textContent = selectedBoss ? `👾 ${selectedBoss.name}` : "👾 BOSS";

  currentRoundIndex = 0;
  renderArenaRound(currentRoundIndex);
  startAutoPlay();
}

function closeArena() {
  stopAutoPlay();
  document.getElementById("arena-overlay").classList.add("hidden");
}

function renderArenaRound(idx) {
  if (!currentSimulation || !currentSimulation.rounds_log[idx]) return;

  const round = currentSimulation.rounds_log[idx];
  const isHeroTurn = (round.round_number % 2 === 1);

  const phaseTitle = isHeroTurn 
    ? `ROUND ${round.round_number} / ${currentSimulation.total_rounds} • ⚔️ HERO ATTACK TURN`
    : `ROUND ${round.round_number} / ${currentSimulation.total_rounds} • 👾 BOSS ATTACK TURN`;
  document.getElementById("arena-round-title").textContent = phaseTitle;

  // Set Role Badges
  const heroRoleBadge = document.getElementById("hero-role-badge");
  const bossRoleBadge = document.getElementById("boss-role-badge");

  if (isHeroTurn) {
    heroRoleBadge.textContent = "⚔️ ATTACKER";
    heroRoleBadge.className = "role-badge role-attacker";
    bossRoleBadge.textContent = "🛡️ DEFENDER";
    bossRoleBadge.className = "role-badge role-defender";
  } else {
    heroRoleBadge.textContent = "🛡️ DEFENDER";
    heroRoleBadge.className = "role-badge role-defender";
    bossRoleBadge.textContent = "⚔️ ATTACKER";
    bossRoleBadge.className = "role-badge role-attacker";
  }

  // Action Icon & Styling mappings
  const actionMeta = {
    "ATTACK": { icon: "⚔️", label: "ATTACK", cls: "act-attack" },
    "HEAVY_ATTACK": { icon: "💥", label: "HEAVY ATTACK", cls: "act-heavy" },
    "DEFEND": { icon: "🛡️", label: "DEFEND", cls: "act-defend" },
    "DODGE": { icon: "💨", label: "DODGE", cls: "act-dodge" },
    "PSYCH_WARFARE": { icon: "🧠", label: "PSYCH WARFARE", cls: "act-psych" },
    "CONFUSED": { icon: "💫", label: "CONFUSED", cls: "act-confused" },
  };

  const heroAct = round.turn_decision.hero_intent.action;
  const bossAct = round.turn_decision.boss_intent.action;

  const heroMeta = actionMeta[heroAct] || { icon: "⚔️", label: heroAct, cls: "act-attack" };
  const bossMeta = actionMeta[bossAct] || { icon: "⚔️", label: bossAct, cls: "act-attack" };

  // Update Hero UI
  const heroPost = round.hero_post_state;
  document.getElementById("hero-hp-display").textContent = `${heroPost.current_hp}/${heroPost.max_hp}`;
  document.getElementById("hero-hp-bar").style.width = `${(heroPost.current_hp / heroPost.max_hp) * 100}%`;
  document.getElementById("hero-sta-display").textContent = `${heroPost.current_sta}/${heroPost.max_sta}`;
  document.getElementById("hero-sta-bar").style.width = `${(heroPost.current_sta / heroPost.max_sta) * 100}%`;
  document.getElementById("hero-status-tag").textContent = heroPost.status;

  const heroActionTag = document.getElementById("hero-action-tag");
  heroActionTag.textContent = `${heroMeta.icon} ${heroMeta.label}`;
  heroActionTag.className = `action-tag ${heroMeta.cls}`;

  const heroBanter = (round.turn_decision.hero_intent.banter || "").trim();
  document.getElementById("hero-banter-quote").textContent = heroBanter ? `"${heroBanter}"` : `"Forward!"`;
  document.getElementById("hero-intent-note").textContent = round.turn_decision.hero_intent.tactical_reasoning;

  // Hero Delta info
  const heroDeltas = document.getElementById("hero-deltas");
  if (round.hero_resolution.damage_dealt > 0) {
    heroDeltas.textContent = `💥 Dealt: ${round.hero_resolution.damage_dealt} DMG | STA: -${round.hero_resolution.stamina_spent}`;
  } else if (round.hero_resolution.stamina_recovered > 0) {
    heroDeltas.textContent = `🛡️ Guarded | STA: +${round.hero_resolution.stamina_recovered}`;
  } else {
    heroDeltas.textContent = `STA: -${round.hero_resolution.stamina_spent}`;
  }

  // Update Boss UI
  const bossPost = round.boss_post_state;
  document.getElementById("boss-hp-display").textContent = `${bossPost.current_hp}/${bossPost.max_hp}`;
  document.getElementById("boss-hp-bar").style.width = `${(bossPost.current_hp / bossPost.max_hp) * 100}%`;
  document.getElementById("boss-sta-display").textContent = `${bossPost.current_sta}/${bossPost.max_sta}`;
  document.getElementById("boss-sta-bar").style.width = `${(bossPost.current_sta / bossPost.max_sta) * 100}%`;
  document.getElementById("boss-status-tag").textContent = bossPost.status;

  const bossActionTag = document.getElementById("boss-action-tag");
  bossActionTag.textContent = `${bossMeta.icon} ${bossMeta.label}`;
  bossActionTag.className = `action-tag ${bossMeta.cls}`;

  const bossBanter = (round.turn_decision.boss_intent.banter || "").trim();
  document.getElementById("boss-banter-quote").textContent = bossBanter ? `"${bossBanter}"` : `"..."`;
  document.getElementById("boss-intent-note").textContent = round.turn_decision.boss_intent.tactical_reasoning;

  // Boss Delta info
  const bossDeltas = document.getElementById("boss-deltas");
  if (round.boss_resolution.damage_dealt > 0) {
    bossDeltas.textContent = `💥 Dealt: ${round.boss_resolution.damage_dealt} DMG | STA: -${round.boss_resolution.stamina_spent}`;
  } else if (round.boss_resolution.stamina_recovered > 0) {
    bossDeltas.textContent = `🛡️ Guarded | STA: +${round.boss_resolution.stamina_recovered}`;
  } else {
    bossDeltas.textContent = `STA: -${round.boss_resolution.stamina_spent}`;
  }

  // Trigger impact animation if damage was taken
  const heroCard = document.querySelector(".hero-fighter");
  const bossCard = document.getElementById("boss-fighter-card");

  heroCard.classList.remove("card-damaged");
  if (bossCard) bossCard.classList.remove("card-damaged");

  if (round.boss_resolution.damage_dealt > 0) {
    void heroCard.offsetWidth; // Trigger reflow
    heroCard.classList.add("card-damaged");
  }
  if (round.hero_resolution.damage_dealt > 0 && bossCard) {
    void bossCard.offsetWidth; // Trigger reflow
    bossCard.classList.add("card-damaged");
  }

  // Events & Referee summary
  const eventsList = document.getElementById("round-events-list");
  eventsList.innerHTML = `<p style="color:#ffe600; margin-bottom:6px;"><strong>Referee:</strong> ${round.turn_decision.referee_summary}</p>` +
    round.combat_events.map(ev => `<p>💥 ${ev}</p>`).join("");

  // Verdict Banner if last round
  const verdictBanner = document.getElementById("final-verdict-banner");
  if (idx === currentSimulation.rounds_log.length - 1) {
    verdictBanner.classList.remove("hidden");
    if (currentSimulation.winner === "Hero") {
      verdictBanner.className = "verdict-banner win";
      verdictBanner.textContent = `🏆 VICTORY: ${currentSimulation.victory_reason}`;
    } else if (currentSimulation.winner === "Boss") {
      verdictBanner.className = "verdict-banner loss";
      verdictBanner.textContent = `💀 DEFEAT: ${currentSimulation.victory_reason}`;
    } else {
      verdictBanner.className = "verdict-banner draw";
      verdictBanner.textContent = `⚖️ DRAW: ${currentSimulation.victory_reason}`;
    }
  } else {
    verdictBanner.classList.add("hidden");
  }
}

function nextRound() {
  if (!currentSimulation) return;
  if (currentRoundIndex < currentSimulation.rounds_log.length - 1) {
    currentRoundIndex++;
    renderArenaRound(currentRoundIndex);
  }
}

function prevRound() {
  if (!currentSimulation) return;
  if (currentRoundIndex > 0) {
    currentRoundIndex--;
    renderArenaRound(currentRoundIndex);
  }
}

function toggleAutoPlay() {
  if (autoPlayInterval) {
    stopAutoPlay();
  } else {
    startAutoPlay();
  }
}

function startAutoPlay() {
  stopAutoPlay();
  document.getElementById("auto-play-btn").classList.add("active");
  autoPlayInterval = setInterval(() => {
    if (currentSimulation && currentRoundIndex < currentSimulation.rounds_log.length - 1) {
      currentRoundIndex++;
      renderArenaRound(currentRoundIndex);
    } else {
      stopAutoPlay();
    }
  }, 1800);
}

function stopAutoPlay() {
  if (autoPlayInterval) {
    clearInterval(autoPlayInterval);
    autoPlayInterval = null;
  }
  document.getElementById("auto-play-btn").classList.remove("active");
}

function exportReplay() {
  if (!currentSimulation) {
    showToast("⚠️ No active battle replay to export!");
    return;
  }
  const winner = currentSimulation.winner ? currentSimulation.winner.toLowerCase() : "draw";
  const filename = `promptjoust-replay-${winner}-${Date.now()}.json`;
  const jsonStr = JSON.stringify(currentSimulation, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  showToast(`💾 Replay exported as ${filename}`);
}

function handleImportReplay(event) {
  const file = event.target.files[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result);
      if (!data.rounds_log || !data.total_rounds) {
        throw new Error("Invalid PromptJoust replay format.");
      }
      currentSimulation = data;
      openArena();
      showToast("📂 Replay successfully loaded!");
    } catch (err) {
      alert(`Failed to load replay file: ${err.message}`);
    }
  };
  reader.readAsText(file);
  event.target.value = ""; // Reset input
}

function generateShareableLink() {
  if (!currentSimulation) {
    showToast("⚠️ No active battle to share!");
    return;
  }

  try {
    const jsonStr = JSON.stringify(currentSimulation);
    const encoded = btoa(encodeURIComponent(jsonStr));
    const shareUrl = `${window.location.origin}${window.location.pathname}#replay=${encoded}`;

    navigator.clipboard.writeText(shareUrl).then(() => {
      showToast("🔗 Battle replay link copied to clipboard!");
    }).catch(() => {
      // Fallback
      prompt("Copy this battle replay link:", shareUrl);
    });
  } catch (err) {
    showToast("❌ Could not generate shareable link.");
  }
}

function checkUrlReplayHash() {
  if (window.location.hash && window.location.hash.startsWith("#replay=")) {
    try {
      const base64Data = window.location.hash.substring(8);
      const jsonStr = decodeURIComponent(atob(base64Data));
      const parsed = JSON.parse(jsonStr);
      if (parsed && parsed.rounds_log && parsed.total_rounds) {
        currentSimulation = parsed;
        setTimeout(() => {
          openArena();
          showToast("🎮 Loaded shared battle replay from URL!");
        }, 300);
      }
    } catch (err) {
      console.warn("Could not parse replay hash:", err);
    }
  }
}

function showToast(message, duration = 3000) {
  const toast = document.getElementById("toast");
  if (!toast) return;

  toast.textContent = message;
  toast.classList.remove("hidden");

  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.classList.add("hidden");
  }, duration);
}

