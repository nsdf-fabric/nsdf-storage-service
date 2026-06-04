(function () {
  const statusBanner = document.getElementById("status-banner");
  const revisionEl = document.getElementById("revision");
  const measurementCount = document.getElementById("measurement-count");
  const nextCount = document.getElementById("next-count");
  const latestPoint = document.getElementById("latest-point");
  const s3Status = document.getElementById("s3-status");
  const plotsEl = document.getElementById("plots");
  const gridWidthInput = document.getElementById("grid-width");
  const gridHeightInput = document.getElementById("grid-height");
  const gridApplyButton = document.getElementById("grid-apply");
  const gridResetButton = document.getElementById("grid-reset");
  const gridMode = document.getElementById("grid-mode");

  let lastState = null;
  let serverDashboardConfig = {};
  let dashboardConfig = {};
  let canvases = {};
  let tooltip = null;

  const plotArea = {
    left: 50,
    right: 14,
    top: 16,
    bottom: 42,
  };
  const gridOverrideKey = "nsdf-storage-dashboard-grid-size";

  function setupGridControls() {
    gridApplyButton.addEventListener("click", () => {
      const width = Math.max(1, Number.parseInt(gridWidthInput.value, 10));
      const height = Math.max(1, Number.parseInt(gridHeightInput.value, 10));
      if (!Number.isFinite(width) || !Number.isFinite(height)) {
        return;
      }
      localStorage.setItem(gridOverrideKey, JSON.stringify([width, height]));
      dashboardConfig = configWithGridSize([width, height]);
      syncGridControls();
      if (lastState) {
        drawAll(lastState, measuredPoints(lastState.measurement), lastState.next_points || flattenNext(lastState.next_x));
      }
    });
    gridResetButton.addEventListener("click", () => {
      localStorage.removeItem(gridOverrideKey);
      dashboardConfig = configFromServerAndStorage(serverDashboardConfig);
      syncGridControls();
      if (lastState) {
        drawAll(lastState, measuredPoints(lastState.measurement), lastState.next_points || flattenNext(lastState.next_x));
      }
    });
  }

  function configFromServerAndStorage(config) {
    const stored = storedGridSize();
    if (stored) {
      return configWithGridSize(stored);
    }
    return normalizeConfig(config || {});
  }

  function configWithGridSize(size) {
    return {
      ...normalizeConfig(serverDashboardConfig),
      grid_size: size,
      grid_bounds: [
        [0, size[0]],
        [0, size[1]],
      ],
      source: "dashboard",
    };
  }

  function normalizeConfig(config) {
    const size = Array.isArray(config.grid_size) && config.grid_size.length === 2 ? config.grid_size : null;
    const bounds =
      Array.isArray(config.grid_bounds) && config.grid_bounds.length === 2
        ? config.grid_bounds
        : size
          ? [
              [0, size[0]],
              [0, size[1]],
            ]
          : null;
    return {
      ...config,
      grid_size: size,
      grid_bounds: bounds,
      source: config.source || (size ? "config" : "inferred"),
    };
  }

  function storedGridSize() {
    try {
      const parsed = JSON.parse(localStorage.getItem(gridOverrideKey) || "null");
      if (Array.isArray(parsed) && parsed.length === 2) {
        const width = Math.max(1, Number.parseInt(parsed[0], 10));
        const height = Math.max(1, Number.parseInt(parsed[1], 10));
        if (Number.isFinite(width) && Number.isFinite(height)) {
          return [width, height];
        }
      }
    } catch (_error) {
      localStorage.removeItem(gridOverrideKey);
    }
    return null;
  }

  function syncGridControls() {
    const size = fixedGridSize();
    gridWidthInput.value = size ? size[0] : "";
    gridHeightInput.value = size ? size[1] : "";
    if (!size) {
      gridMode.textContent = "Inferred grid";
    } else if (dashboardConfig.source === "dashboard") {
      gridMode.textContent = `Dashboard override: ${size[0]} x ${size[1]}`;
    } else {
      gridMode.textContent = `Config grid: ${size[0]} x ${size[1]}`;
    }
  }

  function statusClass(state) {
    const statuses = Object.values(state.s3 || {}).map((entry) => entry.status);
    if (!state.measurement && !state.surrogate && (!state.next_x || state.next_x.length === 0)) {
      return ["banner-empty", "Waiting for data."];
    }
    if (statuses.includes("failed")) {
      return ["banner-failed", "Latest local data visible. S3 upload failed; retry is active."];
    }
    if (statuses.includes("pending")) {
      return ["banner-pending", "Latest local data visible. S3 upload pending."];
    }
    return ["banner-ok", "Latest files persisted to S3."];
  }

  function flattenNext(nextX) {
    const points = [];
    (nextX || []).forEach((workflow) => {
      const workflowId = String(workflow.workflow_id || "");
      (workflow.data || []).forEach((coords, index) => {
        if (Array.isArray(coords) && coords.length >= 2) {
          points.push({
            workflow_id: workflowId,
            labx: Number(coords[0]),
            labz: Number(coords[1]),
            sequence: index + 1,
          });
        }
      });
    });
    return { all: points, latest: points.length ? points[points.length - 1] : null };
  }

  function measuredPoints(measurement) {
    if (!measurement || !Array.isArray(measurement.dataset_x) || !Array.isArray(measurement.dataset_y)) {
      return [];
    }
    return measurement.dataset_x
      .filter((coords) => Array.isArray(coords) && coords.length >= 2)
      .map((coords, index) => ({
        labx: Number(coords[0]),
        labz: Number(coords[1]),
        center_value: Number(measurement.dataset_y[index]),
      }));
  }

  function boundsFor(state, measured, next) {
    const configBounds = dashboardConfig.grid_bounds;
    if (
      Array.isArray(configBounds) &&
      configBounds.length >= 2 &&
      Array.isArray(configBounds[0]) &&
      Array.isArray(configBounds[1])
    ) {
      return {
        xMin: Number(configBounds[0][0]),
        xMax: Number(configBounds[0][1]),
        zMin: Number(configBounds[1][0]),
        zMax: Number(configBounds[1][1]),
      };
    }
    const configured = state.measurement && state.measurement.bounds;
    if (
      Array.isArray(configured) &&
      configured.length >= 2 &&
      Array.isArray(configured[0]) &&
      Array.isArray(configured[1])
    ) {
      return {
        xMin: Number(configured[0][0]),
        xMax: Number(configured[0][1]),
        zMin: Number(configured[1][0]),
        zMax: Number(configured[1][1]),
      };
    }
    const xs = measured.map((p) => p.labx).concat((next.all || []).map((p) => p.labx));
    const zs = measured.map((p) => p.labz).concat((next.all || []).map((p) => p.labz));
    const xMin = xs.length ? Math.min(...xs) : 0;
    const xMax = xs.length ? Math.max(...xs) : 1;
    const zMin = zs.length ? Math.min(...zs) : 0;
    const zMax = zs.length ? Math.max(...zs) : 1;
    return {
      xMin,
      xMax: xMax === xMin ? xMin + 1 : xMax,
      zMin,
      zMax: zMax === zMin ? zMin + 1 : zMax,
    };
  }

  function gridPayload(state) {
    const measurement = state.measurement;
    if (!measurement || !Array.isArray(measurement.dataset_x) || measurement.dataset_x.length === 0) {
      return null;
    }
    const fixedGrid = fixedGridSize();
    const xs = [...new Set(measurement.dataset_x.map((row) => Number(row[0])))].sort((a, b) => a - b);
    const zs = [...new Set(measurement.dataset_x.map((row) => Number(row[1])))].sort((a, b) => a - b);
    const nx = fixedGrid ? fixedGrid[0] : Math.max(1, xs.length);
    const ny = fixedGrid ? fixedGrid[1] : Math.max(1, zs.length);
    const mask = Array.from({ length: ny }, () => Array(nx).fill(0));
    const estimate = Array.from({ length: ny }, () => Array(nx).fill(0));
    const variance = Array.from({ length: ny }, () => Array(nx).fill(0));
    const bounds = boundsFor(state, measuredPoints(measurement), state.next_points || flattenNext(state.next_x));
    const xIndex = new Map(xs.map((value, index) => [value, index]));
    const zIndex = new Map(zs.map((value, index) => [value, index]));
    const gridIndex = (coords) => {
      if (!fixedGrid) {
        return {
          xi: xIndex.get(Number(coords[0])) || 0,
          zi: zIndex.get(Number(coords[1])) || 0,
        };
      }
      return {
        xi: clampIndex(scaleToIndex(Number(coords[0]), bounds.xMin, bounds.xMax, nx), nx),
        zi: clampIndex(scaleToIndex(Number(coords[1]), bounds.zMin, bounds.zMax, ny), ny),
      };
    };
    measurement.dataset_x.forEach((coords, index) => {
      const { xi, zi } = gridIndex(coords);
      mask[zi][xi] = 1;
      estimate[zi][xi] = Number(measurement.dataset_y[index] || 0);
    });

    const surrogate = state.surrogate || {};
    if (Array.isArray(surrogate.surrogate) && surrogate.surrogate.length === measurement.dataset_x.length) {
      measurement.dataset_x.forEach((coords, index) => {
        const { xi, zi } = gridIndex(coords);
        estimate[zi][xi] = Number(surrogate.surrogate[index] || 0);
      });
    }
    if (Array.isArray(surrogate.uncertainty) && surrogate.uncertainty.length === measurement.dataset_x.length) {
      measurement.dataset_x.forEach((coords, index) => {
        const value = Number(surrogate.uncertainty[index] || 0);
        const { xi, zi } = gridIndex(coords);
        variance[zi][xi] = value * value;
      });
    }
    return { nx, ny, mask, estimate, variance };
  }

  function fixedGridSize() {
    const size = dashboardConfig.grid_size;
    if (!Array.isArray(size) || size.length !== 2) {
      return null;
    }
    const width = Math.max(1, Number.parseInt(size[0], 10));
    const height = Math.max(1, Number.parseInt(size[1], 10));
    return Number.isFinite(width) && Number.isFinite(height) ? [width, height] : null;
  }

  function scaleToIndex(value, min, max, count) {
    if (max === min) {
      return Math.floor(count / 2);
    }
    return Math.round(((value - min) / (max - min)) * (count - 1));
  }

  function clampIndex(value, count) {
    return Math.max(0, Math.min(count - 1, value));
  }

  function ensurePlots() {
    if (Object.keys(canvases).length) {
      return;
    }
    plotsEl.innerHTML = `
      <div class="plot-grid">
        ${plotPanel("mask", "Measurement locations")}
        ${plotPanel("estimate", "Estimate")}
        ${plotPanel("variance", "Variance")}
      </div>
      <div class="plot-tooltip" id="plot-tooltip"></div>
    `;
    canvases = {
      mask: document.getElementById("plot-mask"),
      estimate: document.getElementById("plot-estimate"),
      variance: document.getElementById("plot-variance"),
    };
    tooltip = document.getElementById("plot-tooltip");
    Object.values(canvases).forEach((canvas) => {
      canvas.addEventListener("mousemove", showTooltip);
      canvas.addEventListener("mouseleave", hideTooltip);
    });
  }

  function plotPanel(id, title) {
    return `<div class="plot-panel"><h2>${title}</h2><canvas id="plot-${id}" width="640" height="640"></canvas></div>`;
  }

  function updateState(state) {
    if (state.dashboard_config) {
      serverDashboardConfig = state.dashboard_config;
      dashboardConfig = configFromServerAndStorage(serverDashboardConfig);
      syncGridControls();
    }
    lastState = state;
    const measured = measuredPoints(state.measurement);
    const next = state.next_points || flattenNext(state.next_x);
    const [klass, text] = statusClass(state);
    statusBanner.className = `banner ${klass}`;
    statusBanner.textContent = text;
    revisionEl.textContent = `revision ${state.revision || 0}`;
    measurementCount.textContent = measured.length;
    nextCount.textContent = (next.all || []).length;
    latestPoint.textContent = next.latest ? `${next.latest.labx}, ${next.latest.labz}` : "none";
    s3Status.textContent = JSON.stringify(state.s3 || {}, null, 2);

    ensurePlots();
    drawAll(state, measured, next);
  }

  function drawAll(state, measured, next) {
    const grids = gridPayload(state);
    const bounds = boundsFor(state, measured, next);
    drawPlot(canvases.mask, grids ? grids.mask : [[0]], measured, next, bounds, "mask");
    drawPlot(canvases.estimate, grids ? grids.estimate : [[0]], measured, next, bounds, "estimate");
    drawPlot(canvases.variance, grids ? grids.variance : [[0]], measured, next, bounds, "variance");
  }

  function drawPlot(canvas, grid, measured, next, bounds, mode) {
    const ctx = canvas.getContext("2d");
    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "#f8fafc";
    ctx.fillRect(0, 0, width, height);

    const rows = grid.length || 1;
    const cols = grid[0] ? grid[0].length : 1;
    const values = grid.flat().filter((v) => Number.isFinite(Number(v)));
    const min = values.length ? Math.min(...values) : 0;
    const max = values.length ? Math.max(...values) : 1;
    const area = drawableArea(canvas);
    const gridW = area.width / cols;
    const gridH = area.height / rows;
    for (let r = 0; r < rows; r += 1) {
      for (let c = 0; c < cols; c += 1) {
        ctx.fillStyle = colorFor(Number(grid[r][c] || 0), min, max, mode);
        ctx.fillRect(
          area.left + c * gridW,
          area.top + area.height - (r + 1) * gridH,
          Math.ceil(gridW),
          Math.ceil(gridH)
        );
      }
    }

    measured.forEach((point) => drawMarker(ctx, canvas, bounds, point, "measured"));
    (next.all || []).forEach((point) => drawMarker(ctx, canvas, bounds, point, "next"));
    if (next.latest) {
      drawMarker(ctx, canvas, bounds, next.latest, "latest");
    }
    drawAxes(ctx, canvas, bounds);
  }

  function colorFor(value, min, max, mode) {
    if (mode === "mask") {
      return value > 0 ? "#fde724" : "#2d1b4e";
    }
    const t = max === min ? 0.5 : Math.max(0, Math.min(1, (value - min) / (max - min)));
    const r = Math.round(48 + t * 205);
    const g = Math.round(74 + t * 150);
    const b = Math.round(126 - t * 88);
    return `rgb(${r}, ${g}, ${b})`;
  }

  function project(canvas, bounds, point) {
    const area = drawableArea(canvas);
    const x = area.left + ((point.labx - bounds.xMin) / (bounds.xMax - bounds.xMin)) * area.width;
    const y = area.top + area.height - ((point.labz - bounds.zMin) / (bounds.zMax - bounds.zMin)) * area.height;
    return { x, y };
  }

  function drawableArea(canvas) {
    return {
      left: plotArea.left,
      top: plotArea.top,
      width: canvas.width - plotArea.left - plotArea.right,
      height: canvas.height - plotArea.top - plotArea.bottom,
    };
  }

  function drawMarker(ctx, canvas, bounds, point, kind) {
    const p = project(canvas, bounds, point);
    ctx.save();
    if (kind === "measured") {
      ctx.fillStyle = "#ffffff";
      ctx.strokeStyle = "#1d2430";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else if (kind === "latest") {
      ctx.fillStyle = "#d62828";
      ctx.strokeStyle = "#7d1d1d";
      ctx.lineWidth = 3;
      drawStar(ctx, p.x, p.y, 14);
    } else {
      ctx.fillStyle = "#ffb000";
      ctx.strokeStyle = "#553400";
      ctx.lineWidth = 2;
      drawTriangle(ctx, p.x, p.y, 11);
    }
    ctx.restore();
  }

  function drawTriangle(ctx, x, y, size) {
    ctx.beginPath();
    ctx.moveTo(x, y - size);
    ctx.lineTo(x + size, y + size);
    ctx.lineTo(x - size, y + size);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  function drawStar(ctx, x, y, radius) {
    ctx.beginPath();
    for (let i = 0; i < 10; i += 1) {
      const r = i % 2 === 0 ? radius : radius * 0.45;
      const a = -Math.PI / 2 + (i * Math.PI) / 5;
      ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  function drawAxes(ctx, canvas, bounds) {
    const area = drawableArea(canvas);
    ctx.strokeStyle = "rgba(29, 36, 48, 0.45)";
    ctx.lineWidth = 1;
    ctx.strokeRect(area.left + 0.5, area.top + 0.5, area.width, area.height);
    ctx.fillStyle = "#344153";
    ctx.font = "18px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    tickValues(bounds.xMin, bounds.xMax).forEach((value) => {
      const x = area.left + ((value - bounds.xMin) / (bounds.xMax - bounds.xMin)) * area.width;
      ctx.beginPath();
      ctx.moveTo(x, area.top + area.height);
      ctx.lineTo(x, area.top + area.height + 7);
      ctx.stroke();
      ctx.fillText(formatTick(value), x, area.top + area.height + 10);
    });
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    tickValues(bounds.zMin, bounds.zMax).forEach((value) => {
      const y = area.top + area.height - ((value - bounds.zMin) / (bounds.zMax - bounds.zMin)) * area.height;
      ctx.beginPath();
      ctx.moveTo(area.left - 7, y);
      ctx.lineTo(area.left, y);
      ctx.stroke();
      ctx.fillText(formatTick(value), area.left - 10, y);
    });
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    ctx.fillText("labx", area.left + area.width / 2, canvas.height - 2);
    ctx.save();
    ctx.translate(12, area.top + area.height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("labz", 0, 0);
    ctx.restore();
  }

  function tickValues(min, max) {
    if (max === min) {
      return [Math.round(min)];
    }
    const count = 5;
    const step = Math.max(1, Math.round((max - min) / (count - 1)));
    const ticks = [];
    for (let value = Math.round(min); value <= Math.round(max); value += step) {
      ticks.push(value);
    }
    const roundedMax = Math.round(max);
    if (ticks[ticks.length - 1] !== roundedMax) {
      ticks.push(roundedMax);
    }
    return ticks;
  }

  function formatTick(value) {
    return String(Math.round(value));
  }

  function showTooltip(event) {
    if (!lastState || !tooltip) {
      return;
    }
    const canvas = event.currentTarget;
    const rect = canvas.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * canvas.width;
    const y = ((event.clientY - rect.top) / rect.height) * canvas.height;
    const measured = measuredPoints(lastState.measurement);
    const next = lastState.next_points || flattenNext(lastState.next_x);
    const bounds = boundsFor(lastState, measured, next);
    const candidates = measured
      .map((point) => ({ kind: "measured", point }))
      .concat((next.all || []).map((point) => ({ kind: "suggested", point })));
    const closest = candidates
      .map((entry) => ({ ...entry, screen: project(canvas, bounds, entry.point) }))
      .map((entry) => ({ ...entry, distance: Math.hypot(entry.screen.x - x, entry.screen.y - y) }))
      .sort((a, b) => a.distance - b.distance)[0];
    if (!closest || closest.distance > 24) {
      hideTooltip();
      return;
    }
    tooltip.innerHTML = tooltipText(closest.kind, closest.point);
    tooltip.style.left = `${event.clientX + 12}px`;
    tooltip.style.top = `${event.clientY + 12}px`;
    tooltip.style.display = "block";
  }

  function hideTooltip() {
    if (tooltip) {
      tooltip.style.display = "none";
    }
  }

  function tooltipText(kind, point) {
    if (kind === "measured") {
      return `measured<br>labx: ${point.labx}<br>labz: ${point.labz}<br>value: ${point.center_value}`;
    }
    return `suggested<br>labx: ${point.labx}<br>labz: ${point.labz}<br>workflow: ${point.workflow_id}<br>sequence: ${point.sequence}`;
  }

  async function start() {
    setupGridControls();
    const response = await fetch("/api/state");
    updateState(await response.json());
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/state`);
    ws.onmessage = (message) => {
      const event = JSON.parse(message.data);
      updateState(event.state || event);
    };
    ws.onclose = () => {
      statusBanner.className = "banner banner-failed";
      statusBanner.textContent = "WebSocket disconnected. Refresh to reconnect.";
    };
  }

  start().catch((error) => {
    statusBanner.className = "banner banner-failed";
    statusBanner.textContent = `Dashboard failed to start: ${error}`;
  });
})();
