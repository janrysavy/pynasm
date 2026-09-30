"""Regenerate the location matrix with the independent NASM 3.02 executable."""
import argparse
import gzip
import hashlib
import itertools
import json
from pathlib import Path

from nasm_reference import reference, verify_version
from preprocessor_location_cases import sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nasm", type=Path, required=True)
    args = parser.parse_args()
    version = verify_version(args.nasm)
    rows = []
    for (name, body, files), cpu, level in itertools.product(sources(), ("8086", "8088"), (0, 1, 9)):
        source = f"cpu {cpu}\nbits 16\n" + body
        expected = reference(args.nasm, source.replace("cpu 8088", "cpu 8086"), level,
                             files={name: data.encode("ascii") for name, data in files.items()})
        rows.append(dict(name=name, source=source, files=files, cpu=cpu, level=level,
                         hex=None if expected is None else expected.hex()))
    data = dict(version=version, oracle_sha256=hashlib.sha256(args.nasm.read_bytes()).hexdigest(), cases=rows)
    output = Path(__file__).parent / "fixtures/preprocessor_location.json.gz"
    output.write_bytes(gzip.compress((json.dumps(data, sort_keys=True) + "\n").encode(), mtime=0))
    print(f"Wrote {len(rows)} independent NASM cases to {output}")


if __name__ == "__main__":
    main()
