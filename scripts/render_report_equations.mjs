"use strict";

import { createRequire } from "module";
const require = createRequire(import.meta.url);
const path = require("path");
const sharp = require("sharp");

const out = process.argv[2];

function svg(width, body) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="120" viewBox="0 0 ${width} 120">
    <rect width="100%" height="100%" fill="white"/>
    <g fill="#111827" font-family="Times New Roman, Times, serif" font-size="35" text-anchor="middle">${body}</g>
  </svg>`;
}

const equations = {
  "notional.png": svg(1050, `<text x="525" y="72">Notional = Price × Contracts</text>`),
  "composite.png": svg(1500, `<text x="750" y="70">Composite = σ(Σ<tspan baseline-shift="sub" font-size="23">i=1</tspan><tspan baseline-shift="super" font-size="23">5</tspan> Q<tspan baseline-shift="sub" font-size="23">i</tspan> log(S<tspan baseline-shift="sub" font-size="23">i</tspan> / (1 − S<tspan baseline-shift="sub" font-size="23">i</tspan>))),   σ(x) = 1 / (1 + e<tspan baseline-shift="super" font-size="23">−x</tspan>)</text>`),
  "poly_signals.png": svg(1550, `<text x="775" y="70">S<tspan baseline-shift="sub" font-size="23">1</tspan> = max(P<tspan baseline-shift="sub" font-size="23">market</tspan>, P<tspan baseline-shift="sub" font-size="23">wallet</tspan>),   S<tspan baseline-shift="sub" font-size="23">3</tspan> = 0.5 + 0.5 tanh(2 ROĪ λ),   S<tspan baseline-shift="sub" font-size="23">4</tspan> = (|I| + P<tspan baseline-shift="sub" font-size="23">share</tspan>) / 2</text>`),
  "kalshi_signals.png": svg(1550, `<text x="775" y="70">K<tspan baseline-shift="sub" font-size="23">1</tspan> = (P<tspan baseline-shift="sub" font-size="23">peer</tspan> + min(Notional / 250, 1)) / 2,   K<tspan baseline-shift="sub" font-size="23">4</tspan> = min(20 × Trade Notional / Contract Notional, 1)</text>`),
};

for (const [name, source] of Object.entries(equations)) {
  await sharp(Buffer.from(source), { density: 300 }).png().toFile(path.join(out, name));
}
