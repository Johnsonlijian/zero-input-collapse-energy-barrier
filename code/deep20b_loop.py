"""Rebuild a6_barrier_deep for SMF20B until the derivable set is exhausted.

addenda53b.build_tasks('a6_barrier_deep') derives tasks from existing
aftershock_a6/aftershock_ms outputs; quarantined a6 results land
asynchronously, so this loops like the queue's _deep_loop: rebuild the
missing list each pass and stop only when nothing is missing.
"""
import multiprocessing as mp
import sys
import time
from pathlib import Path

sys.path.insert(0, r"E:\n0r53\code")
sys.path.insert(0, r"E:\n0r53\code_copy")

import addenda53b as a53b

WORKERS = 8
MODEL = "SMF20B"


def _missing():
    return [t for t in a53b.build_tasks("a6_barrier_deep", MODEL)
            if not a53b._out_path("a6_barrier_deep", MODEL, t[2]).exists()]


def main():
    rnd = 0
    while True:
        rnd += 1
        tasks = _missing()
        if not tasks:
            print(f"[deep20b] round {rnd}: nothing missing — done", flush=True)
            return
        print(f"[deep20b] round {rnd}: {len(tasks)} missing", flush=True)
        t0 = time.time()
        ctx = mp.get_context("spawn")
        with ctx.Pool(WORKERS) as pool:
            for k, (name, st, w) in enumerate(pool.imap_unordered(a53b._worker, tasks), 1):
                if k % 10 == 0 or st != "ok":
                    print(f"[{k}/{len(tasks)} {time.time()-t0:6.0f}s] {name} {st} {w:.0f}s",
                          flush=True)
        time.sleep(30)


if __name__ == "__main__":
    main()
