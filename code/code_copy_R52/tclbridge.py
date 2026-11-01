"""Execute the published Elkady-Lignos SMF Tcl models inside OpenSeesPy.

The archetype models (Elkady & Lignos 2014, 2015; model package dated 2019)
are distributed as OpenSees Tcl scripts.  No Tcl build of OpenSees is
available on the analysis machine, so the scripts are evaluated by the Tcl
interpreter bundled with Python (tkinter) and every OpenSees command is
forwarded to OpenSeesPy.  The model-definition part of each script (nodes,
elements, materials, masses, gravity analysis and the authors' Rayleigh
damping regions) is executed verbatim; only the following edits are made:

* the analysis flags EQ/PO/ShowAnimation are set to 0 and everything after the
  pushover header (including the final ``wipe all``) is dropped, because the
  dynamic analyses are driven from Python (see ``driver.py``);
* ``Generate_lognrmrand`` is replaced by a deterministic proc returning the
  median value (the published scripts use log-standard deviations of 1e-9,
  i.e. deterministic models, but call a random-number package);
* recorder, display and file-system commands are made no-ops.

Units are those of the published models: kip, inch, second.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tkinter
from pathlib import Path

import openseespy.opensees as ops

from opsmodel import LOG_DIR, ModelInfo

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "elkady_lignos_smf"

_NUM_INT = re.compile(r"^[+-]?\d+$")


def _conv(token: str):
    if _NUM_INT.match(token):
        return int(token)
    try:
        return float(token)
    except ValueError:
        return token


class TclOpenSees:
    """Tcl interpreter whose OpenSees commands are forwarded to OpenSeesPy."""

    FORWARD = [
        "model", "node", "fix", "mass", "equalDOF", "geomTransf", "uniaxialMaterial",
        "element", "load", "timeSeries", "constraints", "numberer", "system", "test",
        "algorithm", "integrator", "analysis", "loadConst", "wipeAnalysis", "region",
        "rayleigh", "setTime", "remove", "rigidLink", "sp",
    ]

    def __init__(self) -> None:
        self.failed_analyses: list = []
        # Every state-changing OpenSees call, in order, so that the model can be
        # rebuilt without Tcl (``replay_commands``).
        self.log: list[list] = []
        self.tcl = tkinter.Tcl()
        for name in self.FORWARD:
            self.tcl.createcommand(name, self._make_forward(name))
        self.tcl.createcommand("pattern", self._pattern)
        self.tcl.createcommand("analyze", self._analyze)
        self.tcl.createcommand("eigen", self._eigen)
        self.tcl.createcommand("nodeDisp", self._node_disp)
        self.tcl.createcommand("getTime", lambda *a: str(ops.getTime()))
        self.tcl.createcommand("wipe", self._wipe)
        for noop in ("recorder", "record", "print", "printModel", "DisplayModel3D", "DisplayPlane"):
            self.tcl.createcommand(noop, lambda *a: "")

    def _call(self, name: str, args: list):
        self.log.append([name, args])
        return getattr(ops, name)(*args)

    def _make_forward(self, name):
        def _fwd(*args):
            out = self._call(name, [_conv(a) for a in args])
            if out is None:
                return ""
            if isinstance(out, (list, tuple)):
                return " ".join(str(v) for v in out)
            return str(out)

        return _fwd

    def _wipe(self, *args):
        self._call("wipe", [])
        return ""

    def _pattern(self, *args):
        # Tcl syntax: pattern Plain tag tsTag {body}
        if args and args[0] == "Plain" and len(args) >= 4:
            ts = _conv(args[2])
            if not isinstance(ts, int):
                # Inline series type (e.g. ``Linear``): OpenSeesPy needs a tag.
                tag = 900_000 + int(args[1])
                self._call("timeSeries", [str(ts), tag])
                ts = tag
            self._call("pattern", ["Plain", int(args[1]), ts])
            self.tcl.eval(args[3])
            return ""
        raise RuntimeError(f"pattern form not supported by bridge: {args[:3]}")

    def _analyze(self, *args):
        ok = self._call("analyze", [_conv(a) for a in args])
        if ok != 0:
            self.failed_analyses.append((args, ok))
        return str(ok)

    def _eigen(self, *args):
        vals = self._call("eigen", [_conv(a) for a in args])
        return " ".join(repr(float(v)) for v in vals)

    def _node_disp(self, *args):
        return str(ops.nodeDisp(*[_conv(a) for a in args]))

    def eval(self, script: str) -> str:
        return self.tcl.eval(script)


_DETERMINISTIC_LOGNORMAL = (
    "proc Generate_lognrmrand {meanX stdlnX} { global xRandom; set xRandom $meanX }"
)


def _preprocess(text: str) -> str:
    # The one-step static analysis that follows the eigen check advances the
    # pseudo-time to 1.0 before the gravity pattern is defined; the gravity
    # analysis (10 x 0.1) then ends at pseudo-time 2.0, i.e. the Linear
    # series applies twice the tabulated gravity loads.  Reset the
    # pseudo-time so that the gravity load factor is exactly 1.0.
    text, n_fix = re.subn(
        r"(integrator\s+LoadControl\s+1\s*;\s*\n\s*analysis\s+Static\s*;\s*\n\s*analyze\s+1\s*;)",
        r"\1\nloadConst -time 0.0;",
        text,
    )
    if n_fix != 1:
        raise RuntimeError("expected exactly one post-eigen static step to patch")
    text = re.sub(r"set\s+EQ\s+1\s*;", "set EQ 0;", text)
    text = re.sub(r"set\s+PO\s+1\s*;", "set PO 0;", text)
    text = re.sub(r"set\s+ShowAnimation\s+1\s*;", "set ShowAnimation 0;", text)
    text = text.replace("source Generate_lognrmrand.tcl;", _DETERMINISTIC_LOGNORMAL + ";")
    for helper in ("DisplayModel3D.tcl", "DisplayPlane.tcl", "DynamicAnalysisCollapseSolverX.tcl"):
        text = text.replace(f"source {helper};", "")
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("file mkdir") or s.startswith("cd "):
            continue
        lines.append(line)
    text = "\n".join(lines)
    # Drop the analysis blocks (pushover, dynamic) and the trailing ``wipe all``.
    cut = text.find("Pushover Analysis")
    if cut < 0:
        raise RuntimeError("pushover header not found; unexpected model layout")
    cut = text.rfind("\n", 0, cut)
    cut = text.rfind("\n", 0, cut)  # remove the comment banner line too
    return text[:cut]


def _extract_dynamic_block(text: str) -> dict:
    """Read the authors' damping and collapse-check settings from the EQ block."""
    eq = text[text.find("if {$EQ==1}"):]
    regions = re.findall(r"^\s*region\s+.*?;\s*$", eq, flags=re.M)
    mf = re.search(r"set\s+MF_FloorNodes\s+\[list\s+([^\]]+)\]", eq)
    egf = re.search(r"set\s+EGF_FloorNodes\s+\[list\s+([^\]]+)\]", eq)
    zeta = re.search(r"set\s+zeta\s+([0-9.]+)\s*;", eq)
    call = re.search(
        r"DynamicAnalysisCollapseSolverX\s+\$GMdt\s+\$dtAnalysis\s+\$totTime\s+\$NStory\s+([0-9.]+)\s+"
        r"\$MF_FloorNodes\s+\$EGF_FloorNodes\s+([0-9.]+)\s+([0-9.]+)",
        eq,
    )
    fv = re.search(r"set\s+FVduration\s+([0-9.]+)", eq)
    coeffs = [re.search(rf"^\s*(set\s+{k}\s+\[expr[^\n]*\])\s*;", eq, flags=re.M) for k in ("a0", "a1", "a1_mod")]
    if not (regions and mf and egf and zeta and call and all(coeffs)):
        raise RuntimeError("could not parse the dynamic-analysis block")
    return {
        "coeff_lines": [c.group(1) for c in coeffs],
        "regions": regions,
        "mf_nodes": [int(v) for v in mf.group(1).split()],
        "egf_nodes": [int(v) for v in egf.group(1).split()],
        "zeta": float(zeta.group(1)),
        "drift_limit": float(call.group(1)),
        "h1": float(call.group(2)),
        "htyp": float(call.group(3)),
        "fv_duration": float(fv.group(1)) if fv else None,
    }


def build_model(name: str, model_dir: Path | None = None, damping: bool = True,
                return_log: bool = False):
    """Build model ``name`` (e.g. 'SMF4B') in the OpenSeesPy domain.

    The domain is left after the gravity analysis (``loadConst -time 0``) with
    the authors' Rayleigh damping regions assigned.
    """
    mdir = Path(model_dir) if model_dir else MODEL_DIR
    raw = (mdir / f"{name}.tcl").read_text(encoding="latin-1")
    dyn = _extract_dynamic_block(raw)
    script = _preprocess(raw)
    bridge = TclOpenSees()
    cwd = os.getcwd()
    os.chdir(mdir)
    try:
        bridge.eval(script)
    finally:
        os.chdir(cwd)
    if bridge.failed_analyses:
        raise RuntimeError(f"static analysis failed while building {name}: {bridge.failed_analyses}")
    n_story = int(bridge.eval("set NStory"))
    periods = []
    for k in range(1, 5):
        try:
            periods.append(float(bridge.eval(f"set T{k}")))
        except tkinter.TclError:
            break
    w = re.search(r'puts "Seismic Weight=\s*([0-9.]+)\s*kip"', raw)
    m = re.search(r'puts "Seismic Mass=\s*([0-9.]+)', raw)
    ray = {}
    if damping:
        bridge.eval(f"set zeta {dyn['zeta']}")
        for line in dyn["coeff_lines"]:  # the authors' a0/a1 expressions, verbatim
            bridge.eval(line)
        for line in dyn["regions"]:
            bridge.eval(line)
        ray = {k: float(bridge.eval(f"set {k}")) for k in ("a0", "a1", "a1_mod", "w1")}
        ray["coeff_lines"] = dyn["coeff_lines"]
    info = ModelInfo(
        name=name,
        n_story=n_story,
        mf_floor_nodes=dyn["mf_nodes"],
        egf_floor_nodes=dyn["egf_nodes"],
        h1=dyn["h1"],
        htyp=dyn["htyp"],
        periods=periods,
        seismic_weight_kip=float(w.group(1)) if w else None,
        seismic_mass=float(m.group(1)) if m else None,
        drift_limit=dyn["drift_limit"],
        zeta=dyn["zeta"],
        rayleigh=ray,
    )
    if return_log:
        return info, bridge.log
    return info


def export_log(name: str, out_dir: Path | None = None) -> Path:
    """Evaluate the Tcl model once and write its OpenSees command log (JSON)."""
    info, log = build_model(name, return_log=True)
    src = (MODEL_DIR / f"{name}.tcl").read_bytes()
    out = Path(out_dir or LOG_DIR)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.json"
    path.write_text(json.dumps({
        "info": info.__dict__,
        "source_tcl": f"{name}.tcl",
        "source_sha256": hashlib.sha256(src).hexdigest(),
        "edits": [
            "pseudo-time reset (loadConst -time 0.0) after the post-eigen one-step static analysis",
            "EQ/PO/ShowAnimation flags set to 0; analysis blocks and trailing 'wipe all' removed",
            "Generate_lognrmrand replaced by its median (published log-std = 1e-9)",
            "recorders, display and file-system commands ignored",
        ],
        "commands": log,
    }), encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys
    import time

    for nm in sys.argv[1:] or ["SMF4B"]:
        t0 = time.time()
        p = export_log(nm)
        print(nm, "->", p, f"{time.time() - t0:.2f}s")
