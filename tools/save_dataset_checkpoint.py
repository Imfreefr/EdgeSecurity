"""Atomically persist a local resume pointer; never start processing or training."""
import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile


def save(manifest, checkpoint):
    manifest, checkpoint = Path(manifest).resolve(), Path(checkpoint).resolve()
    data = manifest.read_bytes()
    rows = [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate IDs')
    pending = [r for r in rows if r['status'].startswith('pending')]
    report = dict(schema_version=1, gate=1, dataset_approved=False,
        manifest=str(manifest), manifest_sha256=hashlib.sha256(data).hexdigest(),
        records=len(rows), by_status=dict(Counter(r['status'] for r in rows)),
        first_pending=pending[0]['platform_name'] if pending else None,
        operations_started_by_checkpoint_writer=[], training_launched=False)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    lock = checkpoint.with_suffix(checkpoint.suffix+'.lock')
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    temporary = None
    try:
        os.close(fd)
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=checkpoint.parent,
                                prefix=checkpoint.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, checkpoint)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        lock.unlink()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--checkpoint', required=True)
    print(json.dumps(save(**vars(parser.parse_args())), ensure_ascii=False))
