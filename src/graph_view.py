"""Generate interactive graph.html from knowledge index edges."""

import json
from pathlib import Path


GRAPH_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Knowledge OS — Dependency Graph</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0d1117; color: #c9d1d9; font-family: -apple-system, system-ui, sans-serif; overflow: hidden; }
svg { width: 100vw; height: 100vh; }
.controls { position: fixed; top: 16px; left: 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; z-index: 10; }
.controls h3 { font-size: 14px; margin-bottom: 8px; color: #58a6ff; }
.controls label { font-size: 12px; display: block; margin: 4px 0; }
.controls input[type=range] { width: 140px; }
.tooltip { position: fixed; background: #1c2128; border: 1px solid #30363d; border-radius: 6px; padding: 8px 12px; font-size: 12px; pointer-events: none; display: none; z-index: 20; max-width: 400px; }
.tooltip .name { color: #58a6ff; font-weight: 600; }
.tooltip .path { color: #8b949e; font-size: 11px; word-break: break-all; }
.tooltip .stats { color: #c9d1d9; margin-top: 4px; }
.legend { position: fixed; bottom: 16px; left: 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; font-size: 11px; z-index: 10; }
.legend div { margin: 2px 0; }
.legend span { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.hub-badge { position: fixed; top: 16px; right: 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; z-index: 10; max-height: 50vh; overflow-y: auto; }
.hub-badge h3 { font-size: 14px; margin-bottom: 8px; color: #f0883e; }
.hub-badge .hub { font-size: 12px; margin: 3px 0; }
.hub-badge .hub .count { color: #f0883e; font-weight: 600; }
line { stroke-opacity: 0.3; }
line:hover { stroke-opacity: 0.8; }
</style>
</head>
<body>
<div class="controls">
  <h3>Knowledge OS Graph</h3>
  <label>Nodes: <span id="node-count">0</span></label>
  <label>Edges: <span id="edge-count">0</span></label>
  <label>Repulsion <input type="range" id="repulsion" min="50" max="500" value="200"></label>
</div>
<div class="tooltip" id="tooltip"><div class="name"></div><div class="path"></div><div class="stats"></div></div>
<div class="legend">
  <div><span style="background:#58a6ff"></span>depends_on</div>
  <div><span style="background:#3fb950"></span>uses</div>
  <div><span style="background:#d2a8ff"></span>example_of</div>
  <div><span style="background:#8b949e"></span>other</div>
</div>
<div class="hub-badge" id="hubs"><h3>Hub Nodes</h3></div>
<svg id="graph"></svg>
<script>
const DATA = __GRAPH_DATA__;

const EDGE_COLORS = {depends_on:"#58a6ff", uses:"#3fb950", example_of:"#d2a8ff", extends:"#f0883e"};
const svg = document.getElementById("graph");
const ns = "http://www.w3.org/2000/svg";
const W = window.innerWidth, H = window.innerHeight;
svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

document.getElementById("node-count").textContent = DATA.nodes.length;
document.getElementById("edge-count").textContent = DATA.edges.length;

const inbound = {};
DATA.edges.forEach(e => { inbound[e.target] = (inbound[e.target]||0) + 1; });
const outbound = {};
DATA.edges.forEach(e => { outbound[e.source] = (outbound[e.source]||0) + 1; });

// Hub badge
const hubs = Object.entries(inbound).sort((a,b)=>b[1]-a[1]).slice(0,10);
const hubDiv = document.getElementById("hubs");
hubs.forEach(([id,count]) => {
  const n = DATA.nodes.find(n=>n.id===id);
  const name = n ? n.name : id.replace("concept_","");
  const d = document.createElement("div");
  d.className = "hub";
  d.innerHTML = `<span class="count">${count}←</span> ${name}`;
  hubDiv.appendChild(d);
});

// Simulation
const nodes = DATA.nodes.map((n,i) => ({
  ...n, x: W/2 + (Math.random()-0.5)*400, y: H/2 + (Math.random()-0.5)*400, vx:0, vy:0,
  r: Math.min(4 + (inbound[n.id]||0)*2, 20)
}));
const nodeMap = {};
nodes.forEach(n => nodeMap[n.id] = n);
const edges = DATA.edges.filter(e => nodeMap[e.source] && nodeMap[e.target]);

// Draw
const lineEls = edges.map(e => {
  const l = document.createElementNS(ns,"line");
  l.setAttribute("stroke", EDGE_COLORS[e.predicate]||"#8b949e");
  l.setAttribute("stroke-width","1");
  svg.appendChild(l);
  return l;
});
const circleEls = nodes.map(n => {
  const c = document.createElementNS(ns,"circle");
  c.setAttribute("r", n.r);
  const isHub = (inbound[n.id]||0) >= 3;
  c.setAttribute("fill", isHub ? "#f0883e" : "#58a6ff");
  c.setAttribute("opacity", isHub ? "0.9" : "0.7");
  c.setAttribute("cursor","pointer");
  c.addEventListener("mouseover", ev => showTooltip(ev, n));
  c.addEventListener("mouseout", hideTooltip);
  svg.appendChild(c);
  return c;
});

const tooltip = document.getElementById("tooltip");
function showTooltip(ev, n) {
  tooltip.style.display = "block";
  tooltip.style.left = ev.clientX + 12 + "px";
  tooltip.style.top = ev.clientY + 12 + "px";
  tooltip.querySelector(".name").textContent = n.name;
  tooltip.querySelector(".path").textContent = n.file_path || n.id;
  tooltip.querySelector(".stats").textContent = `${inbound[n.id]||0} inbound · ${outbound[n.id]||0} outbound`;
}
function hideTooltip() { tooltip.style.display = "none"; }

// Force simulation
let repulsion = 200;
document.getElementById("repulsion").addEventListener("input", e => repulsion = +e.target.value);

function tick() {
  nodes.forEach(n => { n.vx *= 0.9; n.vy *= 0.9; });
  // Repulsion
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i+1; j < nodes.length; j++) {
      let dx = nodes[j].x - nodes[i].x, dy = nodes[j].y - nodes[i].y;
      let d2 = dx*dx + dy*dy + 1;
      let f = repulsion / d2;
      nodes[i].vx -= dx*f; nodes[i].vy -= dy*f;
      nodes[j].vx += dx*f; nodes[j].vy += dy*f;
    }
  }
  // Attraction along edges
  edges.forEach(e => {
    const s = nodeMap[e.source], t = nodeMap[e.target];
    let dx = t.x - s.x, dy = t.y - s.y;
    let d = Math.sqrt(dx*dx + dy*dy) + 1;
    let f = (d - 80) * 0.005;
    s.vx += dx/d*f; s.vy += dy/d*f;
    t.vx -= dx/d*f; t.vy -= dy/d*f;
  });
  // Center gravity
  nodes.forEach(n => {
    n.vx += (W/2 - n.x) * 0.001;
    n.vy += (H/2 - n.y) * 0.001;
    n.x += n.vx; n.y += n.vy;
    n.x = Math.max(n.r, Math.min(W-n.r, n.x));
    n.y = Math.max(n.r, Math.min(H-n.r, n.y));
  });
  // Update DOM
  edges.forEach((e,i) => {
    const s = nodeMap[e.source], t = nodeMap[e.target];
    lineEls[i].setAttribute("x1",s.x); lineEls[i].setAttribute("y1",s.y);
    lineEls[i].setAttribute("x2",t.x); lineEls[i].setAttribute("y2",t.y);
  });
  nodes.forEach((n,i) => {
    circleEls[i].setAttribute("cx",n.x); circleEls[i].setAttribute("cy",n.y);
  });
  requestAnimationFrame(tick);
}
tick();

// Drag
let dragNode = null;
svg.addEventListener("mousedown", ev => {
  const x = ev.clientX, y = ev.clientY;
  dragNode = nodes.find(n => Math.hypot(n.x-x, n.y-y) < n.r+5);
});
svg.addEventListener("mousemove", ev => {
  if (dragNode) { dragNode.x = ev.clientX; dragNode.y = ev.clientY; dragNode.vx=0; dragNode.vy=0; }
});
svg.addEventListener("mouseup", () => dragNode = null);
</script>
</body>
</html>"""


def generate_graph_html(graph_data: dict, output_path: str | Path) -> Path:
    output = Path(output_path)
    html = GRAPH_HTML_TEMPLATE.replace("__GRAPH_DATA__", json.dumps(graph_data))
    output.write_text(html)
    return output
