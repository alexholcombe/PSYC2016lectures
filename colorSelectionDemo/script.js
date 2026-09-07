// Global configuration – updated by sliders
const config = {
  // number of dots per colour (same for red and blue) applied to both halves
  numDots: 900,
  // colour intensities (global for each colour)
  redLevel: 200,
  blueLevel: 240,
  // opacity of dots (0 = transparent, 1 = opaque)
  alpha: .5,
  // other parameters
  refreshRate: 0, // Hz – static by default
  radius: 9,
  columnWidth: 30, // px
};

// Canvas references
const leftCanvas = document.getElementById('leftCanvas');
const rightCanvas = document.getElementById('rightCanvas');
let leftCtx, rightCtx;

function resizeCanvases() {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const colW = config.columnWidth;
  const sideW = (vw - colW) / 2;
  // Left canvas
  leftCanvas.width = sideW;
  leftCanvas.height = vh;
  leftCanvas.style.left = '0px';
  // Right canvas
  rightCanvas.width = sideW;
  rightCanvas.height = vh;
  rightCanvas.style.right = '0px';
  // Centre column positioning
  const centre = document.querySelector('.center-column');
  centre.style.width = colW + 'px';
  centre.style.left = `calc(50% - ${colW / 2}px)`;
  // contexts
  leftCtx = leftCanvas.getContext('2d');
  rightCtx = rightCanvas.getContext('2d');
}

function randomPoint(w, h) {
  return { x: Math.random() * w, y: Math.random() * h };
}

function drawField(ctx, count, colour) {
  ctx.globalAlpha = config.alpha;
  ctx.fillStyle = colour;
  for (let i = 0; i < count; i++) {
    const p = randomPoint(ctx.canvas.width, ctx.canvas.height);
    ctx.beginPath();
    ctx.arc(p.x, p.y, config.radius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = .5;
}

function drawDots() {
  leftCtx.clearRect(0, 0, leftCanvas.width, leftCanvas.height);
  rightCtx.clearRect(0, 0, rightCanvas.width, rightCanvas.height);

  // Left side – red then blue, using unified numDots
  drawField(leftCtx, config.numDots, `rgb(${config.redLevel},0,0)`);
  drawField(leftCtx, config.numDots, `rgb(0,0,${config.blueLevel})`);

  // Right side – same counts
  drawField(rightCtx, config.numDots, `rgb(${config.redLevel},0,0)`);
  drawField(rightCtx, config.numDots, `rgb(0,0,${config.blueLevel})`);
}

let refreshTimer = null;
function startRefreshLoop() {
  if (refreshTimer) clearInterval(refreshTimer);
  if (config.refreshRate > 0) {
    const ms = 1000 / config.refreshRate;
    refreshTimer = setInterval(drawDots, ms);
  } else {
    drawDots(); // static
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
    } else if (key === 'columnWidth') {
      resizeCanvases();
      drawDots();
    } else {
      drawDots();
    }
  });
}

function bindControls() {
  bindSlider('numDots', 'numDots');
  bindSlider('alpha', 'alpha');
  bindSlider('redLevel', 'redLevel');
  bindSlider('blueLevel', 'blueLevel');
  bindSlider('refreshRate', 'refreshRate');
  bindSlider('radius', 'radius');
  bindSlider('columnWidth', 'columnWidth');

  // Reset button – does NOT touch columnWidth or refreshRate (as per user request)
  document.getElementById('resetBtn').addEventListener('click', () => {
    const defaults = {
      numDots: 900,
      alpha: .5,
      redLevel: 220,
      blueLevel: 255,
      radius: 9,
    };
    Object.assign(config, defaults);
    // Update UI elements
    ['numDots', 'alpha', 'redLevel', 'blueLevel', 'radius'].forEach(id => {
      const el = document.getElementById(id);
      el.value = config[id];
      document.getElementById(id + 'Val').textContent = config[id];
    });
    // Redraw (refresh timer continues unchanged)
    drawDots();
  });
}

window.addEventListener('resize', () => {
  resizeCanvases();
  drawDots();
});

// Initialise
resizeCanvases();
bindControls();
startRefreshLoop();
