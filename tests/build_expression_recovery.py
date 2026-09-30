"""Capture outcomes from the actual native reference, without consulting pynasm."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from expression_recovery_cases import cases, LEVELS
from nasm_reference import reference, verify_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nasm', required=True, type=Path)
    args = parser.parse_args()
    rows = []
    version = verify_version(args.nasm)
    for group, body in cases():
        source = 'cpu 8086\nbits 16\n' + body
        for level in LEVELS:
            result = reference(args.nasm, source, level)
            rows.append(dict(group=group, source=source, level=level,
                             hex=None if result is None else result.hex()))
    report = dict(native_version=version,
                  native_sha256=hashlib.sha256(args.nasm.read_bytes()).hexdigest(),
                  cases=rows)
    output = Path(__file__).parent / 'fixtures/generated/expression_recovery.json.gz'
    with gzip.GzipFile(str(output), 'wb', mtime=0) as stream:
        stream.write(json.dumps(report, sort_keys=True).encode())
    print(len(rows), 'native outcomes;', sum(r['hex'] is None for r in rows), 'rejections')


if __name__ == '__main__':
    main()
