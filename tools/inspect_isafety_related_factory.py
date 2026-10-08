"""Decode related-scene candidates; preserve source-bound triage keyframes."""
import hashlib
import json
import cv2
from prepare_cctv_v2 import ROOT


def main():
    base = ROOT/'research'
    output = base/'isafety-factory-comparison-r1'
    if output.exists():
        raise ValueError('Existing comparison preserved')
    paths = [base/'isafety-2026-10-08'/'_XXq1kmmBYY_trim_6.mp4',
             base/'isafety-2026-10-08-offset-12'/'ZNOHrOs9VMA_trim_1.mp4']
    output.mkdir()
    records = []
    for path in paths:
        cap = cv2.VideoCapture(str(path))
        expected = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        indexes = {0, max(0, expected//2), max(0, expected-1)}
        decoded, saved = 0, []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if decoded in indexes:
                target = output/f'{path.stem}-frame-{decoded:06d}.png'
                if not cv2.imwrite(str(target), frame):
                    raise ValueError('Cannot preserve keyframe')
                saved.append(dict(path=str(target), frame_index=decoded,
                                  sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
            decoded += 1
        cap.release()
        records.append(dict(video_path=str(path), video_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                            reported_frames=expected, decoded_frames=decoded,
                            decode_count_matches=(expected==decoded), keyframes=saved,
                            full_video_visually_reviewed=False, approved_for_training=False))
    (output/'comparison.ndjson').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    print(json.dumps(records))


if __name__ == '__main__':
    main()
