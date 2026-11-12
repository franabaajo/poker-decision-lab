// CI smoke test for the in-browser engine (ADR 0025): load the built pokerlab.zip into
// Pyodide (the same WebAssembly Python the website uses, here under Node.js) and run
// real requests through pokerlab.service.dispatch.
//
//   python3 scripts/build_site.py && npm install --no-save pyodide@314.0.2 && node scripts/pyodide_smoke.mjs

import { readFileSync } from "node:fs";
import { loadPyodide } from "pyodide";

const pyodide = await loadPyodide();
await pyodide.loadPackage("numpy");
pyodide.unpackArchive(readFileSync("site/pokerlab.zip"), "zip", { extractDir: "/home/pyodide/lib" });
pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
const service = pyodide.pyimport("pokerlab.service");

const call = (op, args = {}) => JSON.parse(service.dispatch(op, JSON.stringify(args)));
const check = (cond, msg) => {
  if (!cond) {
    console.error(`FAIL: ${msg}`);
    process.exit(1);
  }
  console.log(`ok: ${msg}`);
};

check(call("health").status === "ok", "health");
check(call("cards").length === 52, "52 cards");

const started = performance.now();
const r = call("analyse", {
  hero: ["As", "Qs"],
  board: ["Js", "8d", "4s"],
  range_notation: "77+, ATs+, KTs+, QJs, AJo+, KQo",
  pot: 100,
  bet: 50,
  stack: 500,
  style: "tight",
});
const ms = performance.now() - started;
check(r.valid && r.method === "exact", "exact analysis on the flop");
// Same golden value as tests/test_fast_vs_reference.py (computed by the reference engine).
check(Math.abs(r.multi_street.ev_call - 69.90425117166784) < 1e-6, `multi-street EV = ${r.multi_street.ev_call}`);
console.log(`analyse took ${ms.toFixed(0)} ms in Pyodide`);

const mc = call("equity", { hero: ["As", "Ah"], range_notation: "KK", samples: 20000, seed: 7 });
check(Math.abs(mc.equity - 0.82) < 0.015, `AA vs KK preflop ≈ 82% (got ${(100 * mc.equity).toFixed(1)}%)`);
