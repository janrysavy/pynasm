"""Expanded-source listings, with resolved bytes from the final assembly pass.

This is not NASM's macro/include event listing. Offsets are section-relative;
records also expose physical file offsets and virtual addresses separately.
"""
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class ListingLine:
    filename: str
    number: int
    text: str
    section: str | None
    offset: int
    address: int
    file_offset: int | None
    size: int
    data: bytes


def render_listing(lines: tuple[ListingLine, ...]) -> str:
    result = ['; pynasm expanded listing: section offsets, resolved bytes',
              '; BSS/ABSOLUTE reservations have no file bytes; section padding is not a source row']
    context = None
    for line in lines:
        current = (line.filename, line.section)
        if current != context:
            result.append('; source=' + json.dumps(line.filename) +
                          ' section=' + json.dumps(line.section))
            context = current
        text = line.text.replace('\x00', '<internal>')
        if not line.size:
            result.append(f'{line.number:6d} {"":8} {"":18} {text}')
        elif line.file_offset is None:
            result.append(f'{line.number:6d} {line.offset:08X} {"<res " + str(line.size) + ">":18} {text}')
        else:
            for start in range(0, len(line.data), 8):
                chunk = line.data[start:start + 8].hex().upper()
                more = '-' if start + 8 < len(line.data) else ''
                result.append(f'{line.number:6d} {line.offset + start:08X} {chunk + more:18} '
                              f'{text if start == 0 else ""}')
    return '\n'.join(result) + '\n'
