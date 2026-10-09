"""Gera worklist de duplicatas p/ revisao lado a lado. So propoe, nunca exclui.

Uso:
  .venv/Scripts/python tools/opencode_dupes.py --manifest <copia.ndjson> --outdir <dir-isolado>
Saida: <outdir>/dupes.json (tiers, scores, clusters, origens).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opencode_pipeline import (  # noqa: E402
    atomic_json, build_dupe_worklist, find_duplicates_scalable, read_manifest,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--hamming-max", type=int, default=5)
    a = ap.parse_args()
    rows = read_manifest(a.manifest)
    out = Path(a.outdir)
    dup = find_duplicates_scalable(rows, cache_path=out / "dupe-hashes.json",
                                   hamming_max=a.hamming_max)
    work = build_dupe_worklist(rows, dup)
    atomic_json(out / "dupes.json", dict(worklist=work, stats=dict(
        buckets=dup["buckets"], comparisons=dup["comparisons"],
        skipped_cross_bucket=dup["skipped_cross_bucket"],
        exact_groups=len(dup["exact"]), near_pairs=len(dup["near"]))))
    print(json.dumps(dict(items=len(work["items"]), clusters=len(work["clusters"]),
                           comparisons=dup["comparisons"],
                           skipped=dup["skipped_cross_bucket"])))


if __name__ == "__main__":
    main()
