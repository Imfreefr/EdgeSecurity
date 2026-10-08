"""Read a public ZIP directory with bounded HTTP ranges, no full download."""
import argparse
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

import requests


class RangeReader(io.RawIOBase):
    def __init__(self, url):
        if not url.startswith('https://'):
            raise ValueError('HTTPS source required')
        self.url, self.position, self.transferred = url, 0, 0
        with requests.get(url, headers={'Range': 'bytes=0-0', 'Accept-Encoding': 'identity'},
                          stream=True, timeout=30) as response:
            match = re.fullmatch(r'bytes 0-0/(\d+)', response.headers.get('Content-Range', ''))
            if response.status_code != 206 or not match:
                raise ValueError('Source does not support bounded ranges; full download refused')
            self.size = int(match[1])

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else (self.position if whence == 1 else self.size)+offset
        if position < 0 or position > self.size:
            raise ValueError('Invalid archive seek')
        self.position = position
        return position

    def read(self, count=-1):
        count = min(self.size-self.position, count if count >= 0 else self.size-self.position)
        if count == 0:
            return b''
        if self.transferred+count > 8*1024*1024:
            raise ValueError('ZIP inspection transfer budget exceeded (8 MiB)')
        start, end = self.position, self.position+count-1
        with requests.get(self.url, headers={'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity'},
                          stream=True, timeout=30) as response:
            if response.status_code != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{self.size}':
                raise ValueError('Unexpected range response; full download refused')
            data = response.raw.read(count+1)
            if len(data) != count:
                raise ValueError('Invalid range length')
        self.position += count
        self.transferred += count
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    args = parser.parse_args()
    reader = RangeReader(args.url)
    with zipfile.ZipFile(reader) as archive:
        entries = [{'name': info.filename, 'bytes': info.file_size,
                    'compressed_bytes': info.compress_size} for info in archive.infolist() if not info.is_dir()]
    print(json.dumps({'source': args.url, 'archive_bytes': reader.size,
                      'transferred_bytes': reader.transferred,
                      'by_extension': dict(Counter(Path(entry['name']).suffix.lower() for entry in entries)),
                      'entries': entries}, indent=2))


if __name__ == '__main__':
    main()
