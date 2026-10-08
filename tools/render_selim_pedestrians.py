"""Prepare two hand-drawn proposals with existing review gates; no approval."""
import hashlib
import json
from pathlib import Path
from prepare_cctv_v2 import ROOT
from propose_manual_boxes import propose


def main():
    base = ROOT/'research/public-selim-forklift-2026-10-08'
    output = base/'pedestrian-proposals-r2'
    if output.exists():
        raise ValueError('Existing proposal preserved')
    decisions = json.loads(Path(__file__).with_name('selim_pedestrian_boxes_2026_10_08.json').read_text())
    source = {Path(row['path']).name: row for row in
              map(json.loads, (base/'candidates.ndjson').read_text().splitlines())}
    if not set(decisions['frames']).issubset(source):
        raise ValueError('Unknown source identity')
    output.mkdir()
    for name, boxes in decisions['frames'].items():
        row = dict(source[name], id=Path(name).stem, platform_name=Path(name).stem,
                   boxes=[], is_original=False, synthetic=False,
                   baseline_relationship='unknown', split='train')
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Image changed')
        manifest = output/(row['id']+'-source.ndjson')
        manifest.write_text(json.dumps(row)+'\n', encoding='utf-8')
        decision = dict(manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                        date=decisions['date'], group=decisions['group'],
                        viewpoint='elevated_security_like', reference_size=[row['width'], row['height']],
                        frames={row['id']:dict(boxes, coverage_complete=True)})
        path = output/(row['id']+'-decisions.json')
        path.write_text(json.dumps(decision, indent=2), encoding='utf-8')
        propose(manifest, path, output/row['id'])
    print(json.dumps(dict(output=str(output), proposed_images=2, approved_images=0)))


if __name__ == '__main__':
    main()
