// Newspaper typesetter: flows Hakkan's README copy into justified serif columns as SVG.
const fs = require('fs');
const path = require('path');

const OUT = String.raw`C:\Users\Hakkan\Github-Profile\HakkanShah\assets\news`;
const FONT = "Georgia,'Times New Roman','Liberation Serif',serif";

const THEMES = {
  light: { paper: '#F7F4EC', ink: '#14110C', dim: '#6B6355', accent: '#A8322D', grain: 0.05 },
  dark:  { paper: '#12100B', ink: '#EDE7DA', dim: '#9A917F', accent: '#C9564B', grain: 0.06 },
};

const W = 1200, M = 40, CW = W - 2 * M;

const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// ---- crude Georgia metrics, good enough to wrap without overflow -------------
const NARROW = new Set("iljtfIr.,;:'!|()[]-".split(''));
const WIDE = new Set('mwMW@'.split(''));
function charW(c) {
  if (c === ' ') return 0.26;
  if (NARROW.has(c)) return 0.32;
  if (WIDE.has(c)) return 0.85;
  if (c >= 'A' && c <= 'Z') return 0.68;
  if (c >= '0' && c <= '9') return 0.55;
  return 0.5;
}
const measure = (s, size) => [...s].reduce((a, c) => a + charW(c), 0) * size;
// bold runs wider than the metric above, and letter-spacing adds a fixed per-char cost
const measureBold = (s, size, ls = 0) => measure(s, size) * 1.14 + ls * s.length;

// Wrap where the available width can differ per line (used for drop caps).
function wrap(text, size, widthAt) {
  const words = text.split(/\s+/).filter(Boolean);
  const lines = [];
  let cur = '', i = 0;
  for (const word of words) {
    const trial = cur ? cur + ' ' + word : word;
    // 3% safety margin: the metric table under-measures slightly on real Georgia
    if (measure(trial, size) > widthAt(i) * 0.97 && cur) {
      lines.push(cur); cur = word; i++;
    } else cur = trial;
  }
  if (cur) lines.push(cur);
  return lines;
}

// A block of lines rendered at x,y. Justifies every line except paragraph ends.
function lineBlock(lines, x, y, colW, size, lh, fill, opts = {}) {
  const { justify = true, indentFirst = 0, xAt = null } = opts;
  return lines.map((ln, i) => {
    if (ln === '') return '';
    const lx = xAt ? xAt(i) : x + (i === 0 ? indentFirst : 0);
    const lw = xAt ? colW - (xAt(i) - x) : colW - (i === 0 ? indentFirst : 0);
    const natural = measure(ln, size);
    // Over-long lines are compressed to the measure (never overflow); merely-full
    // lines are stretched to it (justification). Both pin the line to exactly lw.
    const overflow = natural > lw;
    const stretch = justify && !ln.__last && natural > lw * 0.86;
    const tl = (overflow || stretch) ? ` textLength="${lw.toFixed(1)}" lengthAdjust="spacing"` : '';
    return `<text x="${lx.toFixed(1)}" y="${(y + i * lh).toFixed(1)}" font-size="${size}" fill="${fill}"${tl}>${esc(ln)}</text>`;
  }).join('\n    ');
}

// Mark the final line of each paragraph so it is not stretched to full measure.
function paraLines(paragraphs, size, widthAt) {
  const out = [];
  paragraphs.forEach((p, pi) => {
    const ls = wrap(p, size, widthAt);
    ls.forEach((l, li) => {
      const s = new String(l);
      if (li === ls.length - 1) s.__last = true;
      out.push(s);
    });
    if (pi < paragraphs.length - 1) out.push('');
  });
  return out;
}

function balance(lines, nCols) {
  const per = Math.ceil(lines.length / nCols);
  const cols = [];
  for (let c = 0; c < nCols; c++) cols.push(lines.slice(c * per, (c + 1) * per));
  return cols;
}

// ---- page furniture ---------------------------------------------------------
function header(t, num, title, y) {
  const s = `
    <text x="${M}" y="${y + 14}" font-size="10" letter-spacing="3" fill="${t.accent}">SECTION ${num}</text>
    <text x="${M}" y="${y + 60}" font-size="38" font-weight="700" letter-spacing="1" fill="${t.ink}">${esc(title)}</text>
    <g stroke="${t.ink}" fill="none">
      <path d="M${M} ${y + 78}h${CW}" stroke-width="2.5"/>
      <path d="M${M} ${y + 84}h${CW}" stroke-width="0.75"/>
    </g>`;
  return { svg: s, y: y + 84 };
}

function colRules(t, xs, y, h) {
  return xs.map(x => `<path d="M${x} ${y}v${h}" stroke="${t.dim}" stroke-width="0.5" fill="none" opacity="0.6"/>`).join('\n    ');
}

function page(t, height, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${height}" viewBox="0 0 ${W} ${height}" role="img" aria-label="__ALT__">
  <defs>
    <filter id="g" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" stitchTiles="stitch"/>
      <feColorMatrix type="saturate" values="0"/>
    </filter>
  </defs>
  <rect width="${W}" height="${height}" fill="${t.paper}"/>
  <rect width="${W}" height="${height}" filter="url(#g)" opacity="${t.grain}"/>
  <g font-family="${FONT}">
    ${body}
  </g>
</svg>
`;
}

const write = (name, alt, svg) =>
  fs.writeFileSync(path.join(OUT, name), svg.replace('__ALT__', esc(alt)));

// =============================================================================
// SECTION 01 — ABOUT ME  (3 columns, drop cap)
// =============================================================================
function about(t) {
  const size = 15, lh = 22, nCols = 3, gap = 34;
  const colW = (CW - gap * (nCols - 1)) / nCols;
  const paras = [
    "I'm a Full Stack AI Engineer passionate about building production-grade AI products that combine modern web technologies with LLMs, automation, and intelligent user experiences.",
    "Currently working remotely at Persist Ventures, where I build and maintain AI-powered products used in production.",
  ];
  const dropLines = 3, dropW = 46;
  // the drop cap *is* the first letter, so remove it from the flowed copy
  const capChar = paras[0][0];
  paras[0] = paras[0].slice(1);
  const widthAt = i => (i < dropLines ? colW - dropW : colW);
  const lines = paraLines(paras, size, widthAt);
  const cols = balance(lines, nCols);

  const h = header(t, '01', 'ABOUT ME', 24);
  let y = h.y + 30;
  let s = h.svg;
  s += `\n    <text x="${M}" y="${y}" font-size="13" font-style="italic" fill="${t.dim}">By Hakkan Parbej Shah &#183; Persist Ventures &#183; Remote</text>`;
  y += 34;

  const bodyTop = y;
  const colH = Math.max(...cols.map(c => c.length)) * lh + 8;

  cols.forEach((cl, ci) => {
    const x = M + ci * (colW + gap);
    // first column carries the drop cap
    const xAt = ci === 0 ? (i => (i < dropLines ? x + dropW : x)) : null;
    s += '\n    ' + lineBlock(cl, x, bodyTop, colW, size, lh, t.ink, { xAt });
  });
  s += '\n    ' + `<text x="${M}" y="${bodyTop + 40}" font-size="62" font-weight="700" fill="${t.accent}">${esc(capChar)}</text>`;
  const xs = [];
  for (let c = 1; c < nCols; c++) xs.push(M + c * (colW + gap) - gap / 2);
  s += '\n    ' + colRules(t, xs, bodyTop - 16, colH);

  return { svg: s, height: bodyTop + colH + 28 };
}

// =============================================================================
// SECTION 01b — CURRENTLY WORKING ON  (2 columns of briefs)
// =============================================================================
function working(t) {
  const size = 14, lh = 20, gap = 40, nCols = 2;
  const colW = (CW - gap) / 2;
  const items = [
    ['OHM School', 'AI-powered personalized learning platform featuring adaptive learning, AI tutor (Ollie), mastery tracking, assessments, and intelligent recommendations.'],
    ['Aura Desktop', 'AI desktop assistant with voice interaction, desktop automation, browser automation, and multi-provider LLM support.'],
    ['Building scalable products', 'using Next.js, React, TypeScript, Node.js, Supabase, Firebase, and AI APIs.'],
    ['Exploring', 'AI Agents, MCP, RAG, LLM Workflows, Desktop Automation & System Design.'],
    ['Practicing', 'Data Structures & Algorithms to strengthen problem-solving skills.'],
  ];

  let y = 20;
  let s = `
    <text x="${M}" y="${y + 14}" font-size="10" letter-spacing="3" fill="${t.accent}">CURRENTLY WORKING ON</text>
    <g stroke="${t.ink}" fill="none">
      <path d="M${M} ${y + 26}h${CW}" stroke-width="1.5"/>
    </g>`;
  y += 52;

  // lay items into two columns, tracking each column's cursor
  const cursor = [y, y];
  const half = Math.ceil(items.length / nCols);
  items.forEach((it, idx) => {
    const ci = idx < half ? 0 : 1;
    const x = M + ci * (colW + gap);
    let cy = cursor[ci];
    const lead = it[0].toUpperCase();
    const leadW = measureBold(lead, size, 0.6) + 12;
    const lines = paraLines([it[1]], size, i => (i === 0 ? colW - leadW - 16 : colW - 16));
    s += `\n    <rect x="${x}" y="${cy - 10}" width="7" height="7" fill="${t.accent}"/>`;
    s += `\n    <text x="${x + 16}" y="${cy}" font-size="${size}" font-weight="700" letter-spacing="0.6" fill="${t.ink}">${esc(lead)}</text>`;
    const xAt = i => (i === 0 ? x + 16 + leadW : x + 16);
    // base x is indented by 16, so the usable measure shrinks by the same amount
    s += '\n    ' + lineBlock(lines, x + 16, cy, colW - 16, size, lh, t.ink, { xAt });
    cy += lines.length * lh + 20;
    cursor[ci] = cy;
  });

  const bottom = Math.max(...cursor);
  s += `\n    <path d="M${M + colW + gap / 2} ${y - 24}v${bottom - y}" stroke="${t.dim}" stroke-width="0.5" fill="none" opacity="0.6"/>`;
  return { svg: s, height: bottom + 10 };
}

// =============================================================================
// SECTION 02 — FEATURED PROJECTS  (listing with column heads)
// =============================================================================
function projects(t) {
  const size = 15, lh = 21;
  const rows = [
    ['OHM School', 'AI-powered Personalized Learning Platform for adaptive education', 'ohmschool.org'],
    ['Portfolio', 'Interactive terminal-style developer portfolio', 'hakkan.is-a.dev'],
    ['CommitHabit', 'Automation tool for GitHub contribution streak', 'commithabit.vercel.app'],
  ];
  const c1 = M, c2 = M + 300;

  const h = header(t, '02', 'FEATURED PROJECTS', 24);
  let y = h.y + 32;
  let s = h.svg;
  s += `
    <text x="${c1}" y="${y}" font-size="10" letter-spacing="3" fill="${t.dim}">PROJECT</text>
    <text x="${c2}" y="${y}" font-size="10" letter-spacing="3" fill="${t.dim}">DESCRIPTION</text>
    <path d="M${M} ${y + 10}h${CW}" stroke="${t.ink}" stroke-width="0.75" fill="none"/>`;
  y += 38;

  rows.forEach(([name, desc, url]) => {
    const lines = paraLines([desc], size, () => CW - 300 - 10);
    s += `\n    <text x="${c1}" y="${y}" font-size="17" font-weight="700" fill="${t.ink}">${esc(name)}</text>`;
    s += `\n    <text x="${c1}" y="${y + 20}" font-size="11" font-style="italic" fill="${t.accent}">${esc(url)}</text>`;
    s += '\n    ' + lineBlock(lines, c2, y, CW - 300, size, lh, t.ink, { justify: false });
    const rowH = Math.max(lines.length * lh, 44) + 16;
    y += rowH;
    s += `\n    <path d="M${M} ${y - 14}h${CW}" stroke="${t.dim}" stroke-width="0.5" fill="none" opacity="0.7"/>`;
  });

  return { svg: s, height: y + 6 };
}

// =============================================================================
// SECTION 03 — TECH STACK  (3 columns of agate listings)
// =============================================================================
function stack(t) {
  const size = 14, lh = 20, gap = 34, nCols = 3;
  const colW = (CW - gap * 2) / 3;
  const groups = [
    ['Languages', 'Java · TypeScript · JavaScript · Python · C'],
    ['Frontend', 'Next.js · React · Tailwind CSS · HTML · CSS · Shadcn UI'],
    ['Backend', 'Node.js · Express · REST API'],
    ['Database', 'MongoDB · PostgreSQL · MySQL · Redis · Firebase · Supabase'],
    ['AI & LLMs', 'OpenAI · Google Gemini · Anthropic Claude · Groq · NVIDIA NIM'],
    ['Cloud & DevOps', 'Git · GitHub · Docker · Vercel · Netlify · Render'],
  ];

  const h = header(t, '03', 'TECH STACK', 24);
  const top = h.y + 34;
  let s = h.svg;
  const cursor = [top, top, top];

  groups.forEach((g, i) => {
    const ci = i % nCols;
    const x = M + ci * (colW + gap);
    let cy = cursor[ci];
    s += `\n    <text x="${x}" y="${cy}" font-size="11" letter-spacing="2.5" font-weight="700" fill="${t.accent}">${esc(g[0].toUpperCase())}</text>`;
    s += `\n    <path d="M${x} ${cy + 8}h${colW}" stroke="${t.dim}" stroke-width="0.5" fill="none"/>`;
    const lines = paraLines([g[1]], size, () => colW);
    s += '\n    ' + lineBlock(lines, x, cy + 30, colW, size, lh, t.ink, { justify: false });
    cursor[ci] = cy + 30 + lines.length * lh + 26;
  });

  const bottom = Math.max(...cursor);
  const xs = [];
  for (let c = 1; c < nCols; c++) xs.push(M + c * (colW + gap) - gap / 2);
  s += '\n    ' + colRules(t, xs, top - 24, bottom - top);
  return { svg: s, height: bottom + 6 };
}

// =============================================================================
// SECTION 05 — WHAT I ENJOY BUILDING  (classifieds, 3 columns)
// =============================================================================
function building(t) {
  const size = 15, lh = 26, gap = 34, nCols = 3;
  const colW = (CW - gap * 2) / 3;
  const items = [
    'AI Agents & Autonomous Workflows', 'Desktop Applications (Electron)', 'Full Stack Web Applications',
    'AI-powered Education Platforms', 'Developer Productivity Tools', 'Voice Interfaces',
    'RAG & Knowledge Systems', 'Premium UI/UX Experiences', 'Performance Optimization',
  ];
  const h = header(t, '05', 'WHAT I ENJOY BUILDING', 24);
  const top = h.y + 40;
  let s = h.svg;
  const perCol = 3;

  items.forEach((it, i) => {
    const ci = Math.floor(i / perCol);
    const ri = i % perCol;
    const x = M + ci * (colW + gap);
    const y = top + ri * (lh + 12);
    s += `\n    <rect x="${x}" y="${y - 9}" width="7" height="7" fill="${t.accent}"/>`;
    s += `\n    <text x="${x + 16}" y="${y}" font-size="${size}" fill="${t.ink}">${esc(it)}</text>`;
  });

  const bottom = top + perCol * (lh + 12);
  const xs = [];
  for (let c = 1; c < nCols; c++) xs.push(M + c * (colW + gap) - gap / 2);
  s += '\n    ' + colRules(t, xs, top - 26, bottom - top + 12);
  return { svg: s, height: bottom + 14 };
}

// =============================================================================
// SECTION 06 — LET'S CONNECT  (directory)
// =============================================================================
function connect(t) {
  const entries = [
    ['Portfolio', 'hakkan.is-a.dev'],
    ['Persist Portfolio', 'hakkan.persist.org'],
    ['Email', 'hakkanparbej@gmail.com'],
    ['LinkedIn', 'linkedin.com/in/Hakkan'],
    ['GitHub', 'github.com/HakkanShah'],
  ];
  const h = header(t, '06', "LET'S CONNECT", 24);
  let y = h.y + 34;
  let s = h.svg;
  s += `
    <text x="${M}" y="${y}" font-size="10" letter-spacing="3" fill="${t.dim}">CHANNEL</text>
    <text x="${M + 300}" y="${y}" font-size="10" letter-spacing="3" fill="${t.dim}">ADDRESS</text>
    <path d="M${M} ${y + 10}h${CW}" stroke="${t.ink}" stroke-width="0.75" fill="none"/>`;
  y += 34;
  entries.forEach(([k, v]) => {
    s += `\n    <text x="${M}" y="${y}" font-size="15" font-weight="700" fill="${t.ink}">${esc(k)}</text>`;
    s += `\n    <text x="${M + 300}" y="${y}" font-size="15" fill="${t.accent}">${esc(v)}</text>`;
    s += `\n    <path d="M${M} ${y + 12}h${CW}" stroke="${t.dim}" stroke-width="0.5" fill="none" opacity="0.7"/>`;
    y += 34;
  });
  return { svg: s, height: y + 4 };
}

// =============================================================================
// ACTIVITY header only (the streak card itself stays a live image)
// =============================================================================
function activity(t) {
  const h = header(t, '04', 'GITHUB ACTIVITY', 24);
  return { svg: h.svg, height: h.y + 18 };
}

// =============================================================================
// COLOPHON
// =============================================================================
function colophon(t) {
  let s = `
    <g stroke="${t.ink}" fill="none">
      <path d="M${M} 18h${CW}" stroke-width="2.5"/>
      <path d="M${M} 24h${CW}" stroke-width="0.75"/>
    </g>
    <text x="${W / 2}" y="${64}" font-size="20" font-style="italic" fill="${t.ink}" text-anchor="middle">&#8220;Code. Build. Learn. Ship. Repeat.&#8221;</text>
    <text x="${W / 2}" y="${92}" font-size="10" letter-spacing="3" fill="${t.dim}" text-anchor="middle">HAKKAN PARBEJ SHAH &#183; FULL STACK AI ENGINEER &#183; END OF EDITION</text>
    <path d="M${M} 108h${CW}" stroke="${t.ink}" stroke-width="0.75" fill="none"/>`;
  return { svg: s, height: 122 };
}

// ---- emit -------------------------------------------------------------------
const SECTIONS = [
  ['about', about, 'About Me'],
  ['working', working, 'Currently Working On'],
  ['projects', projects, 'Featured Projects'],
  ['stack', stack, 'Tech Stack'],
  ['activity', activity, 'GitHub Activity'],
  ['building', building, 'What I Enjoy Building'],
  ['connect', connect, "Let's Connect"],
  ['colophon', colophon, 'Code. Build. Learn. Ship. Repeat.'],
];

for (const [name, fn, alt] of SECTIONS) {
  for (const [tn, t] of Object.entries(THEMES)) {
    const { svg, height } = fn(t);
    write(`n-${name}-${tn}.svg`, alt, page(t, Math.round(height), svg));
  }
}
console.log('generated:', SECTIONS.map(s => s[0]).join(', '));
