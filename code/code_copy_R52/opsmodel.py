"""Tcl-free reconstruction of the archetype models from a recorded command log.

``tclbridge.export_log`` evaluates a published Tcl model once and records every
state-changing OpenSees call in order (including the static gravity analysis
and the Rayleigh damping regions).  ``replay`` re-issues the same calls through
OpenSeesPy, so the resulting domain is identical to the bridge-built one while
needing neither Tcl nor the original script at analysis time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import openseespy.opensees as ops

G_IN_S2 = 386.1  # value used by the published scripts (in/s^2)
LOG_DIR = Path(__file__).resolve().parent.parent / "models" / "command_logs"


@dataclass
class ModelInfo:
    name: str
    n_story: int
    mf_floor_nodes: list[int]
    egf_floor_nodes: list[int]
    h1: float
    htyp: float
    periods: list[float]
    seismic_weight_kip: float | None
    seismic_mass: float | None
    drift_limit: float
    zeta: float
    rayleigh: dict = field(default_factory=dict)

    @property
    def story_heights(self) -> list[float]:
        return [self.h1] + [self.htyp] * (self.n_story - 1)


_CACHE: dict[str, tuple[ModelInfo, list]] = {}


def load_log(name: str, log_dir: Path | None = None) -> tuple[ModelInfo, list]:
    if name not in _CACHE:
        path = Path(log_dir or LOG_DIR) / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _CACHE[name] = (ModelInfo(**data["info"]), data["commands"])
    return _CACHE[name]


def replay(name: str, log_dir: Path | None = None) -> ModelInfo:
    info, cmds = load_log(name, log_dir)
    ops.wipe()
    for cmd, args in cmds:
        out = getattr(ops, cmd)(*args)
        if cmd == "analyze" and out != 0:
            raise RuntimeError(f"replayed static analysis failed for {name}: {args}")
    return info
