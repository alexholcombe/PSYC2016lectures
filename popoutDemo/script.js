// Line Segment Demo
// Configuration controlled by UI sliders
const config = {
  refreshRate: 0, // Hz – static by default
  lineLength: 50, // length of line segment (pixels)
  numLines: 200,
  entropy: 0, // 0 = perfect grid, 1 = full random
  lineWidth: 1, // stroke width in pixels
  mode: 'orientation', // dropdown mode
};

const canvas = document.getElementById('mainCanvas');
let ctx = null;

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  ctx = canvas.getContext('2d');
}

// Utility: random point that keeps the whole line inside the canvas
function randomPoint(length) {
  // 45° line extends length along both axes; vertical line extends only vertically.
  const margin = length; // simple margin to avoid clipping
  const x = Math.random() * (canvas.width - 2 * margin) + margin;
  const y = Math.random() * (canvas.height - 2 * margin) + margin;
  return { x, y };
}

function drawLines() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  const half = config.lineLength / Math.SQRT2; // component for 45°
  const oddballIndex = Math.floor(Math.random() * config.numLines);
  const cols = Math.ceil(Math.sqrt(config.numLines));
  const rows = Math.ceil(config.numLines / cols);
  const cellW = canvas.width / cols;
  const cellH = canvas.height / rows;
  for (let i = 0; i < config.numLines; i++) {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const baseX = col * cellW + cellW / 2;
    const baseY = row * cellH + cellH / 2;
    const jitterX = (Math.random() - 0.5) * cellW * config.entropy;
    const jitterY = (Math.random() - 0.5) * cellH * config.entropy;
    const x = baseX + jitterX;
    const y = baseY + jitterY;
    ctx.beginPath();
    if (config.mode === 'conjunction') {
      // Random orientation for each line
      if (i === oddballIndex) {
        // oddball: opposite diagonal, red
        ctx.moveTo(x - half, y + half);
        ctx.lineTo(x + half, y - half);
        ctx.strokeStyle = 'red';
      } else {
        const opposite = Math.random() < 0.5; // true = opposite diagonal (blue), false = regular diagonal (red)
        if (opposite) {
          // opposite diagonal, blue
          ctx.moveTo(x - half, y + half);
          ctx.lineTo(x + half, y - half);
          ctx.strokeStyle = 'blue';
        } else {
          // regular diagonal, red
          ctx.moveTo(x - half, y - half);
          ctx.lineTo(x + half, y + half);
          ctx.strokeStyle = 'red';
        }
      }
    } else {
      // default orientation mode
      if (i === oddballIndex) {
        // opposite 45° line (bottom‑left to top‑right)
        ctx.moveTo(x - half, y + half);
        ctx.lineTo(x + half, y - half);
      } else {
        // 45° line (top‑left to bottom‑right)
        ctx.moveTo(x - half, y - half);
        ctx.lineTo(x + half, y + half);
      }
      ctx.strokeStyle = '#000';
    }
    ctx.lineWidth = config.lineWidth;
    ctx.stroke();
  }
}

let refreshTimer = null;
function startRefreshLoop() {
  if (refreshTimer) clearInterval(refreshTimer);
  if (config.refreshRate > 0) {
    const ms = 1000 / config.refreshRate;
    refreshTimer = setInterval(drawLines, ms);
  } else {
    drawLines(); // static draw
  }
}

function bindSlider(id, key) {
  const el = document.getElementById(id);
  const valEl = document.getElementById(id + 'Val');
  el.addEventListener('input', () => {
    config[key] = Number(el.value);
    valEl.textContent = el.value;
    if (key === 'refreshRate') {
      startRefreshLoop();
    } else {
      drawLines();
    }
  });
}

function bindControls() {
  bindSlider('refreshRate', 'refreshRate');
  bindSlider('lineLength', 'lineLength');
  bindSlider('numLines', 'numLines');
  bindSlider('entropy', 'entropy');
  bindSlider('lineWidth', 'lineWidth');
  // Orientation dropdown currently does nothing but is kept for future extensions
  document.getElementById('orientationSelect').addEventListener('change', () => {
    config.mode = document.getElementById('orientationSelect').value;
    drawLines();
  });

  document.getElementById('resetBtn').addEventListener('click', () => {
    const defaults = {
      refreshRate: 0,
      lineLength: 50,
      numLines: 200,
      entropy: 0,
      lineWidth: 1,
    };
    Object.assign(config, defaults);
    // Update UI components
    ['refreshRate', 'lineLength', 'numLines', 'entropy', 'lineWidth'].forEach(id => {
      const el = document.getElementById(id);
      el.value = config[id];
      document.getElementById(id + 'Val').textContent = config[id];
    });
    startRefreshLoop();
  });
}

window.addEventListener('resize', () => {
  resizeCanvas();
  drawLines();
});

// Initialise
resizeCanvas();
bindControls();
startRefreshLoop();
