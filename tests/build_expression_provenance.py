"""Capture NASM 3.02 section identity and ABSOLUTE location regressions."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from nasm_reference import reference, verify_version

PIN = '4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065'
DESTINATION = Path(__file__).parent / 'fixtures/generated/expression_provenance.json.gz'


def sources():
    prefix = ('section .a start=0 vstart=0\na:nop\nfinish:\n'
              'section .b start=1 vstart=0\nb:\n')
    for condition in ('finish-a', 'finish-a-1', '(finish-a)&1',
                      '(finish-a) ? 1 : 0'):
        chosen = f'({condition}) ? a : b'
        for op in ('=', '==', '!=', '<>', '<', '<=', '>', '>=', '<=>'):
            expression = f'({chosen}) {op} b'
            for body in (f'dw {expression}', f'mov ax, [bx + ({expression})]',
                         f'alias: equ {chosen}\nalias2 equ alias\ndw alias2 {op} b'):
                yield 'conditional-identity', prefix + body
        difference = f'({condition}) ? (a-b) : 0'
        for body in (f'dw ({difference}) & 15',
                     f'dw (({difference}) - (a-b)) & 15',
                     f'alias equ {difference}\ndw -alias = (b-a)',
                     f'dw +({difference}) = (a-b)',
                     f'mov ax, [bx + (({difference}) & 15)]'):
            yield 'conditional-difference', prefix + body
    for value in (0, 1, 32, 33, 255, 256):
        for expression in ('$ & 15', '$ / 2', '$ * $', '~$', '$ >> 2',
                           '$ ? 7 : 9', f'$ = {value}', '$ - $$'):
            yield 'absolute-location', (f'absolute {value}\nfield: resb 0\n'
                                       f'alias equ {expression}\n'
                                       'section .text\ndw field, alias')
        yield 'absolute-reserve', (f'absolute {value}\nresb ($ & 3)\n'
                                  'field:\nsection .text\ndw field')
    for expression in ('$ & 15', '$ / 2', '$ * $'):
        yield 'section-not-scalar', f'section .text\nvalue equ {expression}\ndw value'
    yield 'forward-equ-bases', ('alias2 equ alias\n' + prefix +
                               'dw alias2 = b\nalias equ (finish-a) ? a : b')


def build(nasm):
    version = verify_version(nasm)
    rows = []
    for group, body in sources():
        source = 'cpu 8086\nbits 16\n' + body + '\n'
        for level in (0, 1, 9):
            binary = reference(nasm, source, level)
            rows.append(dict(group=group, source=source, level=level,
                             hex=None if binary is None else binary.hex()))
    receipt = dict(version=version, source_pin=PIN,
                   executable_sha256=hashlib.sha256(nasm.read_bytes()).hexdigest(), cases=rows)
    DESTINATION.write_bytes(gzip.compress(json.dumps(receipt, sort_keys=True).encode(), mtime=0))
    print(f'{len(rows)} native outcomes; {sum(r["hex"] is None for r in rows)} rejections')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nasm', type=Path, required=True)
    build(parser.parse_args().nasm.resolve())
