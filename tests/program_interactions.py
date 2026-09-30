"""Whole-program interactions missing from the original branch-only matrix.

These are assembler-byte comparisons, not claims of execution as DOS programs.
Source cases and include bytes are generated without importing the SUT.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

PORTABLE_COUNT = 24
PORTABLE_SEED = 20260930


@dataclass(frozen=True)
class Program:
    name: str
    family: str
    source: str
    files: dict[str, bytes]


TEMPLATES = {
    'copy-data-bss': """org @ORG@
section .text
start:
 mov si,payload
 mov di,buffer
 mov cx,payload_end-payload
 cld
 rep movsb
 call check
 jmp exit
check:
 mov bx,table
 mov ax,[bx]
 ret
exit: mov ax,0x4c00
 int 0x21
section .data align=16
table: dw start,payload,payload_end,buffer
payload: incbin "payload.bin",@OFFSET@,@LEN@
payload_end:
section .bss align=16
buffer: resb payload_end-payload
alignb 32
end_buffer: resw 2
section .data
dw end_buffer-buffer,$-$$
""",
    'absolute-record': """org @ORG@
absolute @OFFSET@
record:
.kind: resb 1
alignb 4
.value: resw 1
.end:
section .text
start:
 mov bx,0x200
 mov al,[bx+record.kind]
 mov dx,[bx+record.value]
 dw record.end-record,record.value,record.end
 times 32-($-$$) db 0xa5
""",
    'follows-vstart': """org @ORG@
section .text
start: mov ax,item
 call worker
 ret
section .data follows=.text align=16 vstart=0x2000
item: dw start,worker,$,$$
 incbin "payload.bin",@OFFSET@,@LEN@
section .extra follows=.data align=8
worker: mov bx,item
 ret
section .bss vfollows=.data
space: resb @LEN@
space_end:
section .text
dw space,space_end,worker
""",
    'include-macro-local': """org @ORG@
%include "layout.inc"
%macro block 1
 %%begin:
 mov cx,%1
 %%loop:
 inc ax
 loop %%loop
 jmp %%done
 times (%1 & 3) db FILL
 %%done:
 dw %%done-%%begin
%endmacro
start:
 block @COUNT@
 block @COUNT2@
 times 64-($-$$) db FILL
align 16, db FILL
payload: incbin "payload.bin",@OFFSET@,@LEN@
.end:
 dw payload.end-payload,$-$$
""",
    'cross-section-equ': """org @ORG@
length equ payload_end-payload
section .text
start:
 mov cx,length
 mov si,payload
 call finish
 jmp exit
finish: mov ax,0x1234
 ret
exit: ret
section .data align=8
payload: incbin "payload.bin",@OFFSET@,@LEN@
payload_end:
 dw length,start,finish,$-$$
section .bss
scratch: resb length
section .text
 dw scratch
""",
    'incbin-layout-range': """org @ORG@
start:
 mov ax,0x1234
 jmp next
 times 24-($-$$) db 0
next:
 incbin "payload.bin",@OFFSET@+($-$$)-24,24+@LEN@-($-$$)
.tail:
 dw next-start,next.tail-next
 times 64-($-$$) db 0
 dw 0xaa55
""",
    'alignb-in-data': """org @ORG@
section .text
start: jmp code
 dw value,ending
alignb 16
code:
 mov ax,[value]
 ret
section .data align=32
value: db @FILL@
alignb 8
ending: dw code-start,$-$$
""",
    'forward-fill': """org @ORG@
jmp target
n equ ending-target
times n db 0
target: times @LEN@ db @FILL@
ending:
 dw target,ending,n
""",
}

REJECTIONS = {
    "conflicting-org": "org 0\nnop\norg 1\nnop\n",
    "invalid-section-alignment": "section .data align=3\ndb 1\n",
    "overlapping-sections": "section .text start=0\ntimes 8 db 0\nsection .data start=4\ndb 1\n",
    "nonconverging-times": "start:\ntimes 1-(end-start) db 0\nend:\n",
    "code-in-absolute": "db 1\nabsolute 32\nresb 2\nnop\nsection .text\ndw $-$$\n",
    "mixed-nobits-placement": "section .data\ndb 1\nsection .bss align=16 vstart=512\nfield: resb 1\nsection .text\ndw field\n",
}

# Verified 2026-09-30: NASM 3.02 times out at O0/O1/O9 with a 5-second limit.
# Never send this source through an ordinary live matrix or count it as a
# matched rejection. Pynasm's prompt rejection is checked separately.
REFERENCE_EXCLUSIONS = {
    "cyclic-follows": "section .a follows=.b\ndb 1\nsection .b follows=.a\ndb 2\n",
}


def interaction_programs(count: int, seed: int):
    if count < 0:
        raise ValueError("program count must be nonnegative")
    rng = random.Random(seed)
    templates = tuple(TEMPLATES.items())
    for number in range(count):
        family, template = templates[number % len(templates)]
        count_value = rng.randrange(1, 16)
        values = {"ORG": (0, 256, 31744)[(number // len(templates)) % 3],
                  "LEN": rng.randrange(1, 18), "OFFSET": rng.randrange(0, 8),
                  "COUNT": count_value, "COUNT2": count_value + 1,
                  "FILL": rng.randrange(256)}
        source = template
        for key, value in values.items():
            source = source.replace("@" + key + "@", str(value))
        files = {"payload.bin": bytes(rng.randrange(256) for _ in range(64)),
                 "layout.inc": b'%include "nested/constants.inc"\n',
                 "nested/constants.inc": f"%define FILL {values['FILL']}\n".encode("ascii")}
        yield Program(f"{number:04d}-{family}", family,
                      "cpu 8086\nbits 16\n" + source, files)


def rejected_programs():
    for name, body in REJECTIONS.items():
        yield Program(name, "rejection", "cpu 8086\nbits 16\n" + body, {})
