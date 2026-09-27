"""Generated 8086 encodings checked against an installed NASM binary.

Set NASM to the executable path when it is not on PATH. These tests stay
optional so the Python package itself has no native dependency.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from pynasm import AssemblyError, assemble


NASM = os.environ.get("NASM") or shutil.which("nasm")


def instruction_cases():
    regs8 = "al cl dl bl ah ch dh bh".split()
    regs16 = "ax cx dx bx sp bp si di".split()
    addresses = ["[bx]", "[bp]", "[si]", "[di]", "[bx+si]", "[bx+di]",
                 "[bp+si]", "[bp+di]", "[0x1234]", "[bx+5]", "[bp-1]",
                 "[si+128]", "[es:bx]"]
    for op in ("mov", "add", "adc", "sub", "cmp", "and", "or", "xor", "sbb", "test", "xchg"):
        for registers in (regs8, regs16):
            for a in registers:
                for b in registers:
                    yield f"{op} {a},{b}"
                for address in addresses:
                    yield f"{op} {a},{address}"
                    yield f"{op} {address},{a}"
        for a, b in (("ax", "bx"), ("al", "bl"), ("ax", "[bx]"),
                     ("[bx]", "ax"), ("word [bp]", "ax"),
                     ("byte [si]", "al")):
            yield f"{op} {a},{b}"
        if op != "xchg":
            for width, reg in ((8, "al"), (16, "ax")):
                for imm in ("0", "1", "127", "128", "255", "256", "-1", "0x1234"):
                    yield f"{op} {reg},{imm}"
                    yield f"{op} {['byte', 'word'][width == 16]} [bp+5],{imm}"
    for op in ("inc", "dec", "not", "neg", "mul", "imul", "div", "idiv"):
        for operand in regs8 + regs16 + ["byte [bx]", "word [bp]", "[si]"]:
            yield f"{op} {operand}"
    for op in ("rol", "ror", "rcl", "rcr", "shl", "shr", "sar"):
        for operand in ("al", "ax", "byte [bx]", "word [bp]", "[si]"):
            for amount in ("1", "cl"):
                yield f"{op} {operand},{amount}"
    for reg in regs8 + regs16:
        for address in addresses:
            yield f"mov {reg},{address}"
            yield f"mov {address},{reg}"
    for op in ("lea", "lds", "les"):
        for address in addresses:
            yield f"{op} ax,{address}"
    for address in ("0x1234", "5"):
        yield f"lea ax,{address}"
    for op in ("jmp", "call"):
        for operand in ("ax", "[bx]", "word [bp]", "far [bp]"):
            yield f"{op} {operand}"


@unittest.skipUnless(NASM, "NASM reference executable is unavailable")
class DifferentialTests(unittest.TestCase):
    def test_generated_8086_encodings(self):
        cases = list(instruction_cases())
        source = "cpu 8086\nbits 16\n" + "\n".join(cases) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "cases.asm", path / "cases.bin"
            input_file.write_text(source)
            for level in (0, 1, 9):
                with self.subTest(optimization=level):
                    run = subprocess.run([NASM, "-f", "bin", f"-O{level}", "-o", output_file, input_file],
                                         capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(assemble(source, optimize=level, compatibility="nasm3"), output_file.read_bytes())

    def test_displacement_and_immediate_boundaries(self):
        values = ("-129", "-128", "-127", "-1", "0", "1", "127", "128", "129",
                  "0xff7f", "0xff80", "0xffff", "0x10000")
        cases = []
        for mnemonic in ("mov", "add", "sub", "cmp", "test", "xchg"):
            for value in values:
                for base in ("bx", "bp", "si", "bx+di"):
                    cases.extend((f"{mnemonic} word [{base}+{value}],ax",
                                  f"{mnemonic} ax,word [{base}+{value}]"))
        for mnemonic in ("mov", "add", "sub", "cmp", "test"):
            for value in values:
                cases.extend((f"{mnemonic} word [bp+127],{value}",
                              f"{mnemonic} ax,{value}"))
        source = "cpu 8086\n" + "\n".join(cases) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "boundaries.asm", path / "boundaries.bin"
            input_file.write_text(source)
            for level in (0, 1, 9):
                with self.subTest(optimization=level):
                    run = subprocess.run([NASM, "-f", "bin", f"-O{level}", "-o", output_file, input_file],
                                         capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(assemble(source, optimize=level, compatibility="nasm3"),
                                     output_file.read_bytes())

    def test_branch_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "branch.asm", path / "branch.bin"
            for mnemonic in ("jmp", "call", "jz", "jnz", "loop", "jcxz"):
                for padding in (0, 126, 127, 128, 200):
                    if mnemonic in ("loop", "jcxz") and padding > 127:
                        continue
                    for level in (0, 1, 9):
                        with self.subTest(mnemonic=mnemonic, padding=padding, optimization=level):
                            source = f"cpu 8086\n{mnemonic} target\ntimes {padding} db 0\ntarget: nop\n"
                            input_file.write_text(source)
                            run = subprocess.run([NASM, "-f", "bin", f"-O{level}", "-o", output_file, input_file],
                                                 capture_output=True, text=True)
                            self.assertEqual(run.returncode, 0, run.stderr)
                            self.assertEqual(assemble(source, optimize=level, compatibility="nasm3"), output_file.read_bytes())

    def test_misc_8086_forms(self):
        instructions = [
            "aaa", "aad", "aad 7", "aam", "aas", "cbw", "cwd", "daa", "das",
            "clc", "cld", "cli", "cmc", "hlt", "int 0x21", "int3", "into",
            "iret", "lahf", "movsb", "movsw", "cmpsb", "cmpsw", "stosb",
            "stosw", "lodsb", "lodsw", "scasb", "scasw", "pause", "popf",
            "pushf", "sahf", "salc", "xlat", "stc", "std", "sti", "wait",
            "rep movsb", "repne scasb", "lock inc word [bx]", "push cs",
            "pop cs", "mov cs,ax", "mov ds,[bx]", "mov [bx],es", "in al,dx",
            "in ax,0x40", "out dx,al", "out 0x40,ax",
            "call far 0x1234:0x5678", "jmp far 0x1234:0x5678",
            "ret", "ret 4", "retf", "retf 4",
            "iretw", "pushfw", "popfw", "retw", "retw 4",
            "retnw", "retnw 4", "retfw", "retfw 4",
            "brkpt", "int03", "fwait",
            "movabs ax,[0x1234]", "movabs [0x1234],ax",
            "movabs ax,0x1234", "movabs al,[0x1234]",
            "lea ax,5", "lea bx,0x1234", "mov ax,es:5",
            "mov ax,es:bx+5", "add ax,es:5", "lea ax,es:5",
            "jmp es:5", "call es:5",
            "mov ax,abs 5", "movabs ax,abs 5", "jmp abs $+5",
            "lea ax,abs 5", "mov ax,abs [5]",
            "lds ax,far [bx]", "les ax,far [bx]", "lea ax,far [bx]",
            "mov ax,far [bx]", "mov far [bx],ax", "xchg ax,far [bx]",
            "test ax,far [bx]", "add ax,far [bx]",
            "mov far [bx],1", "add far [bx],1", "test far [bx],1",
        ]
        source = "cpu 8086\nbits 16\n" + "\n".join(instructions) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "misc.asm", path / "misc.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O0", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, compatibility="nasm3"), output_file.read_bytes())

    def test_optimizer_aliases(self):
        aliases = ("bswap ax", "bswap cx", "bswap dx", "bswap bx",
                   "movsx ax,al", "movsxb ax,al")
        source = "cpu 8086\nbits 16\n" + "\n".join(aliases) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "aliases.asm", path / "aliases.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())
            for level in (0, 1):
                with self.subTest(optimization=level):
                    run = subprocess.run([NASM, "-f", "bin", f"-O{level}", "-o", output_file, input_file],
                                         capture_output=True, text=True)
                    self.assertNotEqual(run.returncode, 0)
                    with self.assertRaises(AssemblyError):
                        assemble(source, optimize=level, compatibility="nasm3")

    def test_loop_variants(self):
        mnemonics = ("jcxz", "loop", "loope", "loopne", "loopz", "loopnz",
                     "loopw", "loopew", "loopnew", "loopzw", "loopnzw")
        cases = [f"{mnemonic} $+2" for mnemonic in mnemonics]
        cases += [f"{mnemonic} $+2,cx" for mnemonic in mnemonics[:6]]
        cases += ["jcxz near $+2", "loop near $+2", "loopw near $+2"]
        source = "cpu 8086\nbits 16\n" + "\n".join(cases) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "loops.asm", path / "loops.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())

    def test_jump_relocation_classes(self):
        source = """cpu 8086
org 0x100
CONST equ 0x110
start: nop
jmp CONST
jmp 0x110
jmp $+5
jmp $$+5
jmp $-$$+0x110
mid: nop
DIFF equ mid-start
jmp DIFF
jmp mid-start+0x110
jmp mid
jmp start
jmp start+2
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "relocations.asm", path / "relocations.bin"
            input_file.write_text(source)
            for level in (0, 1, 9):
                with self.subTest(optimization=level):
                    run = subprocess.run([NASM, "-f", "bin", f"-O{level}", "-o", output_file, input_file],
                                         capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(assemble(source, optimize=level, compatibility="nasm3"),
                                     output_file.read_bytes())

    def test_macro_rotation(self):
        source = """cpu 8086
%macro multipush 1-*
%rep %0
push %1
%rotate 1
%endrep
%endmacro
%macro multipop 1-*
%rep %0
%rotate -1
pop %1
%endrep
%endmacro
multipush ax,bx,cx
multipop ax,bx,cx
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "rotation.asm", path / "rotation.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())

    def test_preprocessor_exitrep(self):
        source = """cpu 8086
%assign i 0
%assign j 1
%rep 100
%if j > 100
%exitrep
%endif
dw j
%assign k j+i
%assign i j
%assign j k
%endrep
%rep 3
%rep 5
db 7
%exitrep
%endrep
db 8
%endrep
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "repetition.asm", path / "repetition.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())

    def test_preprocessor_exitmacro(self):
        source = """cpu 8086
%macro emit 1
db %1
%if %1
%rep 3
%exitmacro
%endrep
%endif
db 9
%endmacro
emit 1
emit 0
db 8
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "exitmacro.asm", path / "exitmacro.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())

    def test_preprocessor_token_conditions(self):
        checks = (
            ("%ifid foo bar", 1), ("%ifnid 3", 2),
            ("%ifnum -7", 3), ("%ifnnum foo", 4),
            ("%ifstr \"hello\"", 5), ("%ifnstr foo", 6),
            ("%iftoken ax", 7), ("%ifntoken -1", 8),
            ("%ifempty", 9), ("%ifnempty ax", 10),
            ("%ifidn foo bar,foo    bar", 11),
            ("%ifidni Foo,foo", 12),
            ("%ifmacro tag 2", 13), ("%ifnmacro tag 3", 14),
        )
        source = "cpu 8086\n%macro tag 1-2\n%endmacro\n" + "\n".join(
            f"{condition}\ndb {value}\n%endif" for condition, value in checks
        ) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "conditions.asm", path / "conditions.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())

    def test_macro_defaults_greedy_and_unmacro(self):
        source = """cpu 8086
%macro emit 1-3 6,7
db %0,%1,%2,%3
%endmacro
emit 5
emit 5,8
%macro collect 2-3+
db %0
db %3
%endmacro
collect 1,2,3,4,5
%define VALUE 1
%macro captured 0-1 VALUE
db %1
%endmacro
%undef VALUE
%define VALUE 2
captured
%unmacro emit 1-3
%ifnmacro emit 1-3
db 9
%endif
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "defaults.asm", path / "defaults.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())

    def test_macro_invocation_label(self):
        source = """cpu 8086
%macro emit 1
%00: db %1
%endmacro
%macro emit_plain 1
db %1
%endmacro
first: emit 5
second emit 6
third: emit_plain 7
dw first,second,third
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "labels.asm", path / "labels.bin"
            input_file.write_text(source)
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", output_file, input_file],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(assemble(source, optimize=9, compatibility="nasm3"), output_file.read_bytes())

    def test_binary_sections_and_references(self):
        sources = [
            "section .text\ndb 1\nsection .data\ndb 2",
            "section .data\ndb 1\nsection .text\ndb 2",
            "org 0x100\nsection .data\ndata: db 3\nsection .text\nmov ax,data",
            "org 0x100\nsection .text\nmov ax,var\nsection .bss\nvar: resb 3",
            "section .text\ndb 1\nsection .data align=16\ndb 2",
            "section foo\ndb 3\nsection .text\ndb 2",
            "org 0x100\nsection .text\ndb 1\nsection .data\ndw section..data.start",
            "section foo start=16\ndb 2\nsection bar start=8\ndb 3",
            "org 0x100\nsection .text\ndb 1\nsection foo vstart=0x200\ndw $$",
            "section .text\ndb 1\nsection foo follows=.text align=1\ndb 2",
            "section .text\ndb 1\nsection foo vfollows=.text\ndw $$",
            "section foo follows=bar\ndb 1\nsection bar\ndb 2",
            "section .text\ndb 1\nsection .data",
            "section .text\njmp data\nsection .data\ndata: nop",
            "section .text\njz data\nsection .data\ndata: nop",
            "section .text\nloop data\nsection .data\ndata: nop",
            "section .text\njmp short data\nsection .data\ndata: nop",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "sections.asm", path / "sections.bin"
            for source in sources:
                with self.subTest(source=source):
                    source = "cpu 8086\n" + source + "\n"
                    input_file.write_text(source)
                    run = subprocess.run([NASM, "-f", "bin", "-O0", "-o", output_file, input_file],
                                         capture_output=True, text=True)
                    self.assertEqual(run.returncode, 0, run.stderr)
                    self.assertEqual(assemble(source, compatibility="nasm3"), output_file.read_bytes())

    def test_invalid_8086_forms(self):
        cases = [
            "pusha", "popa", "enter 4,0", "leave", "bound ax,[bx]",
            "insb", "outsb", "shl ax,2",
            "mov [bx],[si]", "mov ax,byte 1", "mov al,word 1",
            "mov word [bx],byte 1", "add byte [bx],word 1",
            "mov ax,[bx+bx]", "mov ax,[bx*2]", "mov ax,[bx+bp]",
            "jmp missing_symbol",
            "aam ax", "aad [bx]", "int word 1", "ret byte 1",
            "mov ax,far 1", "add al,far 1", "shl ax,far 1",
            "mov ax,far bx",
            "in al,word 1", "out word 1,ax",
            "bswap si", "movsx bx,al", "movabs bx,[0x1234]",
            "loop $+2,ax", "loopw $+2,cx", "jcxz far $+2",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "invalid.asm", path / "invalid.bin"
            for case in cases:
                with self.subTest(case=case):
                    source = "cpu 8086\n" + case + "\n"
                    input_file.write_text(source)
                    run = subprocess.run([NASM, "-f", "bin", "-o", output_file, input_file],
                                         capture_output=True, text=True)
                    self.assertNotEqual(run.returncode, 0, case)
                    with self.assertRaises(AssemblyError):
                        assemble(source, compatibility="nasm3")

    def test_dword_branch_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            input_file, output_file = path / "branch32.asm", path / "branch32.bin"
            for mnemonic in ("jmp", "call", "jo", "jnz", "loop", "jcxz"):
                for padding in (0, 1, 125, 126, 127, 128, 129):
                    for direction in ("forward", "backward"):
                        if mnemonic in ("loop", "jcxz") and (
                                direction == "backward" and padding >= 125 or
                                direction == "forward" and padding >= 128):
                            continue
                        body = (f"{mnemonic} dword target\ntimes {padding} db 0\ntarget: nop"
                                if direction == "forward" else
                                f"target: nop\ntimes {padding} db 0\n{mnemonic} dword target")
                        source = "cpu 8086\nbits 16\n" + body + "\n"
                        input_file.write_text(source, encoding="ascii")
                        for level in (0, 1, 9):
                            with self.subTest(mnemonic=mnemonic, padding=padding,
                                              direction=direction, optimize=level):
                                reference = subprocess.run(
                                    [NASM, "-f", "bin", f"-O{level}", "-o", output_file, input_file],
                                    capture_output=True, text=True)
                                self.assertEqual(reference.returncode, 0, reference.stderr)
                                self.assertEqual(assemble(source, compatibility="nasm3", optimize=level),
                                                 output_file.read_bytes())


if __name__ == "__main__":
    unittest.main()
