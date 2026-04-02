(function () {
  "use strict";

  /* ═══════════════════════════════════════════════════════════════════
     AETHER-ACM  ·  dashboard.js
     Fully wired to your index.html element IDs and your backend API.
     Falls back to realistic demo data if the API is unreachable.
  ═══════════════════════════════════════════════════════════════════ */

  const API = ""; // same origin — FastAPI serves this page

  // ── Shared state ──────────────────────────────────────────────────
  let state = {
    satellites: [],
    debris: [],
    cdms: [],
    selectedSat: null,
    showDebris: true,
    showTerminator: true,
    autoPilot: true,
    burnCount: 0,
    metrics: {
      health: 0,
      total: 0,
      nominal: 0,
      evading: 0,
      recovery: 0,
      eol: 0,
      avgFuel: 0,
      active_cdms: 0,
      pending_burns: 0,
    },
  };

  // ── API helpers ───────────────────────────────────────────────────
  async function fetchSnapshot() {
    const r = await fetch(`${API}/api/visualization/snapshot`);
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  async function fetchMetrics() {
    const r = await fetch(`${API}/api/metrics`);
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  async function loadFromAPI() {
    try {
      const [snap, met] = await Promise.all([fetchSnapshot(), fetchMetrics()]);

      // Map snapshot satellites → state
      state.satellites = (snap.satellites || []).map((s) => ({
        id: s.id,
        lat: s.lat,
        lon: s.lon,
        alt: s.alt ?? 550,
        fuel_pct: s.fuel_pct ?? 80,
        fuel_kg: s.fuel_kg ?? 40,
        status: s.status ?? "NOMINAL",
        risk_level: s.risk_level ?? "GREEN",
      }));

      // Map debris cloud tuples [id, lat, lon, alt] → objects
      state.debris = (snap.debris_cloud || []).map((d) => ({
        id: d[0],
        lat: d[1],
        lon: d[2],
        alt: d[3],
      }));

      // CDMs from snapshot
      state.cdms = (snap.recent_cdms || [])
        .map((c) => ({
          id: c.id,
          satellite_id: c.satellite_id,
          debris_id: c.debris_id,
          miss_dist_km: c.miss_dist_km,
          risk_level: c.risk_level,
          tca: new Date(c.tca),
        }))
        .sort((a, b) => a.miss_dist_km - b.miss_dist_km);

      // Metrics
      state.metrics = {
        health: Math.round(met.health_score ?? snap.health_score ?? 0),
        total: met.total_satellites ?? state.satellites.length,
        nominal: met.nominal ?? 0,
        evading: met.evading ?? 0,
        recovery: met.recovery ?? 0,
        eol: met.eol ?? 0,
        avgFuel: Math.round(met.avg_fuel_pct ?? 0),
        active_cdms: met.active_cdms ?? state.cdms.length,
        pending_burns: met.pending_burns ?? 0,
      };
    } catch (e) {
      // API unreachable — use demo data so dashboard still looks alive
      generateDemoData();
    }
  }

  // ── Demo data fallback ────────────────────────────────────────────
  function generateDemoData() {
    const names = [
      "ATLAS",
      "VANGUARD",
      "ORION",
      "POLARIS",
      "NOVA",
      "CYGNUS",
      "DRAGON",
      "STARLINK",
      "ASTRA",
      "ZEPHYR",
    ];
    const sats = [];
    for (let i = 0; i < 50; i++) {
      const r = Math.random();
      const status = r < 0.07 ? "EVADING" : r < 0.11 ? "RECOVERY" : "NOMINAL";
      sats.push({
        id: `${names[i % names.length]}-${Math.floor(i / names.length) + 1}`,
        lat: +((Math.random() - 0.5) * 150).toFixed(3),
        lon: +((Math.random() - 0.5) * 360).toFixed(3),
        alt: +(540 + Math.random() * 20).toFixed(1),
        fuel_pct: +(20 + Math.random() * 75).toFixed(1),
        fuel_kg: +(10 + Math.random() * 40).toFixed(1),
        status,
        risk_level:
          Math.random() < 0.06
            ? "RED"
            : Math.random() < 0.12
              ? "YELLOW"
              : "GREEN",
      });
    }

    const debris = Array.from({ length: 1800 }, (_, i) => ({
      id: `DEB-${i}`,
      lat: +((Math.random() - 0.5) * 170).toFixed(2),
      lon: +((Math.random() - 0.5) * 360).toFixed(2),
      alt: +(400 + Math.random() * 800).toFixed(0),
    }));

    const cdms = Array.from({ length: 7 }, (_, i) => {
      const sat = sats[Math.floor(Math.random() * sats.length)];
      const dist = +(0.05 + Math.random() * 7).toFixed(2);
      return {
        id: i,
        satellite_id: sat.id,
        debris_id: `DEB-${Math.floor(Math.random() * 2000)}`,
        miss_dist_km: dist,
        risk_level: dist < 0.1 ? "CRITICAL" : dist < 1 ? "RED" : "YELLOW",
        tca: new Date(Date.now() + Math.random() * 5400000),
      };
    }).sort((a, b) => a.miss_dist_km - b.miss_dist_km);

    const ev = sats.filter((s) => s.status === "EVADING").length;
    const rec = sats.filter((s) => s.status === "RECOVERY").length;

    state.satellites = sats;
    state.debris = debris;
    state.cdms = cdms;
    state.metrics = {
      health: 84 + Math.floor(Math.random() * 12),
      total: 50,
      nominal: 50 - ev - rec,
      evading: ev,
      recovery: rec,
      eol: 0,
      avgFuel: Math.floor(sats.reduce((a, b) => a + b.fuel_pct, 0) / 50),
      active_cdms: cdms.length,
      pending_burns: ev * 2,
    };
  }

  // ── Advance simulation ────────────────────────────────────────────
  async function advanceSim() {
    addLog("⏩ Advancing simulation +1 hour...");
    try {
      const r = await fetch(`${API}/api/simulate/step`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ step_seconds: 3600 }),
      });
      const d = await r.json();
      if (d.maneuvers_executed > 0) {
        addLog(`🔥 ${d.maneuvers_executed} burn(s) executed autonomously`);
        state.burnCount += d.maneuvers_executed;
      }
      if (d.collisions_detected > 0) {
        addLog(
          `⚠️ COLLISION ALERT: ${d.collisions_detected} impact(s) detected!`,
        );
      }
    } catch (e) {
      // No backend — just regenerate demo data
      generateDemoData();
    }
    await loadFromAPI();
    renderAll();
    addLog(`✅ Epoch advanced · ${state.cdms.length} active CDMs`);
  }

  // ── Map ───────────────────────────────────────────────────────────
  let map,
    satMarkers = {},
    debrisCtx,
    termSvg;

  function initMap() {
    map = L.map("map", {
      zoomControl: false,
      attributionControl: false,
    }).setView([20, 0], 2);

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 10,
      },
    ).addTo(map);

    const container = document.getElementById("map-container");
    const canvas = document.getElementById("debris-canvas");

    new ResizeObserver(() => {
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      renderDebris();
    }).observe(container);

    debrisCtx = canvas.getContext("2d");
    termSvg = document.getElementById("terminator-svg");

    // Toggle buttons — IDs from your HTML
    document.getElementById("toggle-debris").onclick = function () {
      state.showDebris = !state.showDebris;
      this.classList.toggle("active", state.showDebris);
      renderDebris();
    };
    document.getElementById("toggle-terminator").onclick = function () {
      state.showTerminator = !state.showTerminator;
      this.classList.toggle("active", state.showTerminator);
      renderTerminator();
    };

    map.on("moveend zoomend", () => {
      renderDebris();
      renderTerminator();
    });
  }

  function updateSatMarkers() {
    if (!map) return;
    const ids = new Set(state.satellites.map((s) => s.id));

    // Remove stale
    Object.keys(satMarkers).forEach((id) => {
      if (!ids.has(id)) {
        satMarkers[id].remove();
        delete satMarkers[id];
      }
    });

    state.satellites.forEach((sat) => {
      const cls = [
        "sat-marker",
        sat.status.toLowerCase(),
        state.selectedSat === sat.id ? "selected" : "",
      ]
        .filter(Boolean)
        .join(" ");

      const icon = L.divIcon({
        className: "",
        html: `<div class="${cls}"></div>`,
        iconSize: [12, 12],
        iconAnchor: [6, 6],
      });

      const fuelColor =
        sat.fuel_pct < 20
          ? "var(--red)"
          : sat.fuel_pct < 50
            ? "var(--amber)"
            : "var(--green)";

      const popup = `
        <div style="font-family:monospace;font-size:12px;min-width:160px">
          <b style="color:#00e4ff">${sat.id}</b><br/>
          Status: <span style="color:${sat.status === "NOMINAL" ? "var(--green)" : "var(--amber)"}">${sat.status}</span><br/>
          Alt: ${sat.alt.toFixed(1)} km<br/>
          Fuel: <span style="color:${fuelColor}">${sat.fuel_pct}% (${sat.fuel_kg} kg)</span><br/>
          Risk: ${sat.risk_level}
        </div>`;

      if (satMarkers[sat.id]) {
        satMarkers[sat.id].setLatLng([sat.lat, sat.lon]).setIcon(icon);
      } else {
        satMarkers[sat.id] = L.marker([sat.lat, sat.lon], { icon })
          .addTo(map)
          .bindPopup(popup)
          .on("click", () => selectSat(sat.id));
      }
    });
  }

  // ── Debris canvas ─────────────────────────────────────────────────
  function renderDebris() {
    if (!debrisCtx || !map) return;
    const ctx = debrisCtx;
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    if (!state.showDebris) return;

    const bounds = map.getBounds();
    state.debris.forEach((d) => {
      if (!bounds.contains([d.lat, d.lon])) return;
      const pt = map.latLngToContainerPoint([d.lat, d.lon]);

      // Color by altitude — low=cyan, mid=amber, high=red (matches your theme)
      const t = Math.min(1, Math.max(0, (d.alt - 300) / 900));
      const rv = Math.round(t * 255);
      const gv = Math.round(120 - t * 80);
      const bv = Math.round(255 - t * 200);

      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 1.2, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rv},${gv},${bv},0.65)`;
      ctx.fill();
    });
  }

  // ── Terminator line ───────────────────────────────────────────────
  function renderTerminator() {
    termSvg.innerHTML = "";
    if (!state.showTerminator || !map) return;

    const now = new Date();
    const doy = Math.floor(
      (now - new Date(now.getFullYear(), 0, 0)) / 86400000,
    );
    const decl = -23.45 * Math.cos(((360 / 365) * (doy + 10) * Math.PI) / 180);
    const hour = now.getUTCHours() + now.getUTCMinutes() / 60;
    const sunLon = (hour / 24) * 360 - 180;

    const pts = [];
    for (let lat = -80; lat <= 80; lat += 2) {
      const denom =
        Math.cos((lat * Math.PI) / 180) * Math.tan((decl * Math.PI) / 180);
      const lon =
        sunLon -
        (Math.atan2(Math.sin((decl * Math.PI) / 180), denom) * 180) / Math.PI -
        90;
      const p = map.latLngToContainerPoint([lat, ((lon + 180) % 360) - 180]);
      pts.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`);
    }

    // Night shade
    const mapSz = map.getSize();
    const shade = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "path",
    );
    shade.setAttribute("d", `M 0,0 L ${pts.join(" L ")} L ${mapSz.x},0 Z`);
    shade.setAttribute("fill", "rgba(0,8,30,0.30)");
    termSvg.appendChild(shade);

    // Dashed line
    const poly = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "polyline",
    );
    poly.setAttribute("points", pts.join(" "));
    poly.setAttribute("stroke", "rgba(0,228,255,0.35)");
    poly.setAttribute("stroke-width", "2");
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke-dasharray", "8 6");
    termSvg.appendChild(poly);
  }

  // ── Bullseye ──────────────────────────────────────────────────────
  function renderBullseye() {
  const canvas = document.getElementById('bullseye-canvas');
  if (!canvas) return;

  const ctx  = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H / 2;
  const maxR = Math.min(W, H) / 2 - 10;

  ctx.clearRect(0, 0, W, H);

  // 🔥 AUTO-SELECT MOST DANGEROUS SAT (for demo)
  if (!state.selectedSat && state.cdms.length > 0) {
    const mostDangerous = [...state.cdms].sort(
      (a, b) => a.miss_dist_km - b.miss_dist_km
    )[0];

    state.selectedSat = mostDangerous.satellite_id;

    const label = document.getElementById("bullseye-label");
    if (label) label.textContent = state.selectedSat;
  }

  // Rings
  [1, 0.65, 0.3].forEach((f, i) => {
    ctx.beginPath();
    ctx.arc(cx, cy, maxR * f, 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(0,228,255,${0.14 + i * 0.1})`;
    ctx.lineWidth   = 0.8;
    ctx.setLineDash([4, 4]);
    ctx.stroke();
  });
  ctx.setLineDash([]);

  // Cross-hairs
  ctx.strokeStyle = 'rgba(0,228,255,0.1)';
  ctx.lineWidth   = 0.5;
  ctx.beginPath(); ctx.moveTo(cx, cy - maxR); ctx.lineTo(cx, cy + maxR); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(cx - maxR, cy); ctx.lineTo(cx + maxR, cy); ctx.stroke();

  // Labels
  ctx.font      = '8px JetBrains Mono';
  ctx.fillStyle = 'rgba(148,163,184,0.5)';
  ctx.textAlign = 'center';
  ctx.fillText('1km',  cx, cy - maxR * 0.3 - 3);
  ctx.fillText('5km',  cx, cy - maxR * 0.65 - 3);
  ctx.fillText('>5km', cx, cy - maxR - 3);

  // Center dot
  ctx.beginPath(); ctx.arc(cx, cy, 4, 0, Math.PI * 2);
  ctx.fillStyle = '#00e4ff'; ctx.fill();
  ctx.lineWidth = 6; ctx.strokeStyle = 'rgba(0,228,255,0.2)'; ctx.stroke();

  // 🔥 SMART FILTERING (no empty screen)
  let relevant = [];

  if (state.selectedSat) {
    relevant = state.cdms.filter(c => c.satellite_id === state.selectedSat);
  }

  if (relevant.length === 0) {
    relevant = [...state.cdms]
      .sort((a, b) => a.miss_dist_km - b.miss_dist_km)
      .slice(0, 16);
  }

  if (relevant.length === 0) {
    ctx.font      = '10px Inter';
    ctx.fillStyle = 'rgba(148,163,184,0.3)';
    ctx.textAlign = 'center';
    ctx.fillText('NO ACTIVE CONJUNCTIONS', cx, cy + 40);
    return;
  }

  relevant.forEach((cdm, i) => {
    const dist  = cdm.miss_dist_km;
    const angle = (i / relevant.length) * Math.PI * 2 - Math.PI / 2;

    const r = dist < 1  ? maxR * 0.08 + (dist / 1)  * maxR * 0.22
            : dist < 5  ? maxR * 0.30 + ((dist - 1) / 4) * maxR * 0.35
            :             maxR * 0.70 + Math.min(0.22, (dist - 5) / 20) * maxR;

    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);

    // 🔥 IMPROVED COLOR LOGIC
    let color;
    if (dist < 1) color = '#ff3366';
    else if (dist < 3) color = '#ff4d4d';
    else if (dist < 6) color = '#ffb020';
    else color = '#00fca8';

    // 🔥 STRONG PULSE FOR CRITICAL
    if (dist < 1) {
      const pulse = (Math.sin(Date.now() / 200) + 1) / 2;

      ctx.beginPath();
      ctx.arc(x, y, 6 + pulse * 10, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255,51,102,${0.5 * pulse})`;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    ctx.shadowBlur  = 10;
    ctx.shadowColor = color;

    ctx.beginPath();
    ctx.arc(x, y, 5, 0, Math.PI * 2);
    ctx.fillStyle = color;
    ctx.fill();

    ctx.shadowBlur = 0;
  });
}

  // ── Fuel grid ─────────────────────────────────────────────────────
  function renderFuelGrid() {
    const grid = document.getElementById("fuel-grid");
    if (!grid) return;

    // Update average label — matches your HTML id="fuel-avg"
    const avgEl = document.getElementById("fuel-avg");
    if (avgEl) avgEl.textContent = `AVG ${state.metrics.avgFuel}%`;

    // Diff-patch: rebuild only when count changes
    if (grid.children.length !== state.satellites.length) {
      grid.innerHTML = "";
      state.satellites.forEach((sat) => grid.appendChild(buildFuelCell(sat)));
    } else {
      state.satellites.forEach((sat, i) => {
        const cell = grid.children[i];
        if (cell) applyFuelStyle(cell, sat);
        const tip = cell?.querySelector(".fuel-tip");
        if (tip) tip.textContent = `${sat.id} · ${sat.fuel_pct}%`;
      });
    }
  }

  function buildFuelCell(sat) {
    const cell = document.createElement("div");
    cell.className = "fuel-cell";
    applyFuelStyle(cell, sat);
    const tip = document.createElement("div");
    tip.className = "fuel-tip";
    tip.textContent = `${sat.id} · ${sat.fuel_pct}%`;
    cell.appendChild(tip);
    cell.onclick = () => selectSat(sat.id);
    return cell;
  }

  function applyFuelStyle(cell, sat) {
    const pct = sat.fuel_pct / 100;
    let color;
    if (sat.fuel_pct < 25)
      color = `rgba(255, 51, 102, `; // red
    else if (sat.fuel_pct < 55)
      color = `rgba(255, 176, 32, `; // amber
    else color = `rgba(0, 252, 168, `; // green
    cell.style.background = `${color}${0.2 + pct * 0.8})`;
    cell.style.border = `1px solid ${color}0.4)`;
  }

  // ── CDM Alerts list ───────────────────────────────────────────────
  // Matches your HTML: id="alerts-list", id="stat-alerts"
  function renderAlerts() {
    const container = document.getElementById("alerts-list");
    const statEl = document.getElementById("stat-alerts");
    if (!container) return;

    if (statEl) statEl.textContent = state.cdms.length;
    container.innerHTML = "";

    state.cdms.slice(0, 8).forEach((cdm) => {
      const div = document.createElement("div");
      div.className = "alert-item";

      // Map backend risk levels → your CSS classes
      const riskClass =
        cdm.risk_level === "CRITICAL" || cdm.risk_level === "RED"
          ? "risk-critical"
          : "risk-high";
      const riskLabel =
        cdm.risk_level === "CRITICAL"
          ? "CRITICAL"
          : cdm.risk_level === "RED"
            ? "HIGH"
            : "MEDIUM";

      const mins = Math.max(0, Math.floor((cdm.tca - Date.now()) / 60000));
      const Pc = Math.exp(-(cdm.miss_dist_km ** 2) / (2 * 0.01)).toExponential(
        1,
      );

      div.innerHTML = `
        <div class="risk-tag ${riskClass}">${riskLabel}</div>
        <div class="alert-info">
          <strong style="color:var(--text-primary)">${cdm.satellite_id}</strong><br/>
          <span style="color:var(--text-muted)">${cdm.miss_dist_km} km miss · Pc ${Pc}</span>
        </div>
        <div style="font-size:10px;font-family:monospace;color:var(--cyan)">T-${mins}m</div>`;
      div.onclick = () => selectSat(cdm.satellite_id);
      container.appendChild(div);
    });

    if (state.cdms.length === 0) {
      container.innerHTML = `
        <div style="padding:20px;text-align:center;color:var(--text-muted);font-size:11px;font-family:monospace">
          ✓ NO ACTIVE CONJUNCTIONS
        </div>`;
    }
  }

  // ── Fleet metrics ─────────────────────────────────────────────────
  // Matches: stat-sats, stat-debris, health-value, health-dot,
  //          nominal-count, evading-count, recovery-count
  function renderMetrics() {
    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    set("stat-sats", state.metrics.total);
    set("stat-debris", state.debris.length.toLocaleString());
    set("health-value", state.metrics.health + "%");
    set("nominal-count", state.metrics.nominal);
    set("evading-count", state.metrics.evading);
    set(
      "recovery-count",
      state.metrics.recovery +
        (state.metrics.eol > 0 ? ` (+${state.metrics.eol} EOL)` : ""),
    );

    // Health dot colour
    const dot = document.getElementById("health-dot");
    if (dot) {
      dot.className =
        state.metrics.health < 65
          ? "health-dot critical"
          : state.metrics.health < 80
            ? "health-dot warning"
            : "health-dot";
    }

    // Health badge colour
    const badge = document.getElementById("health-badge");
    if (badge) {
      badge.style.background =
        state.metrics.health < 65
          ? "rgba(255,51,102,0.10)"
          : state.metrics.health < 80
            ? "rgba(255,176,32,0.10)"
            : "rgba(16,216,118,0.10)";
    }
    const hv = document.getElementById("health-value");
    if (hv) {
      hv.style.color =
        state.metrics.health < 65
          ? "var(--red)"
          : state.metrics.health < 80
            ? "var(--amber)"
            : "var(--green)";
    }
  }

  // ── Event log ─────────────────────────────────────────────────────
  function addLog(msg) {
    const logDiv = document.getElementById("event-log");
    if (!logDiv) return;
    const entry = document.createElement("div");
    entry.className = "log-entry";
    const t = new Date().toLocaleTimeString("en-US", { hour12: false });
    entry.textContent = `${t} › ${msg}`;
    logDiv.prepend(entry);
    while (logDiv.children.length > 25) logDiv.removeChild(logDiv.lastChild);
  }

  // ── Select satellite ──────────────────────────────────────────────
  function selectSat(id) {
    state.selectedSat = state.selectedSat === id ? null : id;
    // Matches your HTML: id="bullseye-label"
    const label = document.getElementById("bullseye-label");
    if (label) label.textContent = state.selectedSat || "ALL SATS";
    updateSatMarkers();
    renderBullseye();
    addLog(
      state.selectedSat ? `🎯 Lock acquired: ${id}` : "🌐 Reset to fleet view",
    );
    // Pan map to satellite
    if (state.selectedSat && map) {
      const sat = state.satellites.find((s) => s.id === id);
      if (sat) map.panTo([sat.lat, sat.lon], { animate: true, duration: 0.5 });
    }
  }

  // ── SITREP modal ──────────────────────────────────────────────────
  // Matches: sitrep-btn, modal, sitrep-body, close-modal
  function openSitrep() {
    document.getElementById("modal").style.display = "flex";
    const m = state.metrics;
    const top = state.cdms[0];
    document.getElementById("sitrep-body").innerHTML = `
      <h3 style="color:var(--text-primary);margin-bottom:16px">🚀 FLEET DIAGNOSTICS</h3>
      <p><strong>System Health:</strong>
        <span style="color:${m.health < 65 ? "var(--red)" : m.health < 80 ? "var(--amber)" : "var(--green)"}">${m.health}%</span></p>
      <p><strong>Nominal Units:</strong> ${m.nominal} / ${m.total}</p>
      <p><strong>Evading Maneuvers:</strong> ${m.evading}</p>
      <p><strong>Recovery Status:</strong> ${m.recovery}</p>
      <p><strong>EOL Satellites:</strong> ${m.eol}</p>
      <p><strong>Mean Propellant:</strong> ${m.avgFuel}%</p>
      <p><strong>Pending Burns:</strong> ${m.pending_burns}</p>
      <br/>
      <h3 style="color:var(--text-primary);margin-bottom:16px">⚠️ THREAT ASSESSMENT</h3>
      <p><strong>Critical Conjunctions (&lt;1km):</strong>
        <span style="color:var(--red)">${state.cdms.filter((c) => c.miss_dist_km < 1).length}</span></p>
      <p><strong>High Risk (&lt;4km):</strong>
        <span style="color:var(--amber)">${state.cdms.filter((c) => c.miss_dist_km >= 1 && c.miss_dist_km < 4).length}</span></p>
      ${top ? `<p><strong>Closest Threat:</strong> ${top.satellite_id} — ${top.miss_dist_km} km from ${top.debris_id}</p>` : ""}
      <br/>
      <p style="padding:12px;background:rgba(0,228,255,0.08);border-left:3px solid var(--cyan);border-radius:4px">
        <strong>Recommendation:</strong>
        ${
          state.cdms.filter((c) => c.miss_dist_km < 1).length > 0
            ? `<span style="color:var(--red)">IMMEDIATE ACTION — ${state.cdms.filter((c) => c.miss_dist_km < 1).length} critical conjunction(s). Verify evasion burns.</span>`
            : "All risks within manageable thresholds. Autonomous monitoring active."
        }
      </p>`;
  }

  // ── Master render ─────────────────────────────────────────────────
  function renderAll() {
    updateSatMarkers();
    renderDebris();
    renderTerminator();
    renderBullseye();
    renderFuelGrid();
    renderAlerts();
    renderMetrics();
  }

  // ── Boot sequence ─────────────────────────────────────────────────
  const bootMsgs = [
    "Establishing TLE feed...",
    "Propagating orbits via RK4+J2...",
    "Building KD-Tree spatial index...",
    "Loading ground station network...",
    "Ready for command.",
  ];

  function boot() {
    const fill = document.getElementById("boot-fill");
    const status = document.getElementById("boot-status");
    let step = 0;

    const iv = setInterval(async () => {
      if (step < bootMsgs.length) {
        status.textContent = bootMsgs[step];
        fill.style.width = ((step + 1) / bootMsgs.length) * 100 + "%";
        step++;
      } else {
        clearInterval(iv);

        // Load real data before showing UI
        await loadFromAPI();

        document.getElementById("boot-overlay").classList.add("fade-out");
        setTimeout(() => {
          document.getElementById("app").style.display = "flex";
          document.getElementById("boot-overlay").style.display = "none";
          initMap();
          renderAll();

          // Live polling every 3 seconds
          setInterval(async () => {
            await loadFromAPI();
            renderAll();
          }, 3000);

          // Live CDM countdown tick
          setInterval(() => {
            document.querySelectorAll(".tca-countdown").forEach((el) => {
              const tca = new Date(el.dataset.tca);
              const mins = Math.max(0, Math.floor((tca - Date.now()) / 60000));
              el.textContent = `T-${mins}m`;
            });
          }, 1000);

          // Bullseye animation
          setInterval(renderBullseye, 500);

          // Auto-pilot loop
          setInterval(() => {
            if (state.autoPilot) advanceSim();
          }, 30000);

          addLog("🛰️ AETHER-ACM online — autonomous mode active");
        }, 600);
      }
    }, 480);
  }

  // ── Wire up buttons ───────────────────────────────────────────────
  // IDs exactly as in your index.html
  document.getElementById("advance-btn").onclick = () => advanceSim();
  document.getElementById("sitrep-btn").onclick = () => openSitrep();
  document.getElementById("close-modal").onclick = () => {
    document.getElementById("modal").style.display = "none";
  };
  window.onclick = (e) => {
    if (e.target === document.getElementById("modal"))
      document.getElementById("modal").style.display = "none";
  };

  // Auto-pilot toggle — id="auto-toggle", id="auto-switch"
  document.getElementById("auto-toggle").onclick = function () {
    state.autoPilot = !state.autoPilot;
    this.classList.toggle("active", state.autoPilot);
    document
      .getElementById("auto-switch")
      .classList.toggle("active", state.autoPilot);
    addLog(`🤖 Autopilot ${state.autoPilot ? "ENGAGED" : "DISENGAGED"}`);
  };

  // ── Start ─────────────────────────────────────────────────────────
  boot();
})();
