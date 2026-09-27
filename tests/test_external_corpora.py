"""Pinned upstream goldens and an optional, independently authored corpus."""

import os
import shutil
import subprocess
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from pynasm import Assembler, AssemblyError


FIXTURES = Path(__file__).parent / "fixtures"
NASM = os.environ.get("NASM") or shutil.which("nasm")
INDEPENDENT = os.environ.get("PYNASM_INDEPENDENT_CORPUS")
INDEPENDENT_COMMIT = "1979e794d1cbcd92714d0863a2fd17fd89af4fcd"


class PinnedCorpusTests(unittest.TestCase):
    def test_interacting_forward_branches_and_alignment(self):
        """Branch relaxation must converge across other branches and ALIGN."""
        root = FIXTURES / "generated"
        for stem in ("layout_boundary", "layout_alignment_boundary",
                     "layout_branch_interaction"):
            source = (root / f"{stem}.asm").read_text(encoding="ascii")
            for level in (0, 1, 9):
                for cpu in ("8086", "8088"):
                    with self.subTest(source=stem, optimization=level, cpu=cpu):
                        alias_source = source.replace("cpu 8086\n", f"cpu {cpu}\n", 1)
                        actual = Assembler(optimize=level, compatibility="nasm3").assemble(
                            alias_source)
                        self.assertEqual(actual,
                                         (root / f"{stem}.O{level}.bin").read_bytes())

    def test_official_nasm_8086_cases(self):
        """The upstream travis goldens were built with NASM 3.02 -Ox."""
        root = FIXTURES / "nasm_official"
        for stem, golden_name in (("andbyte", "andbyte.bin.t"),
                                  ("bcd", "bcd.bin.t"),
                                  ("bintest", "bintest-ox.bin.t"),
                                  ("br2003451", "br2003451.bin.t"),
                                  ("br3026808", "br3026808.bin.t"),
                                  ("float", "float.bin.t"),
                                  ("float8", "float8.bin.t"),
                                  ("floatb-8086", "floatb-8086.bin.t"),
                                  ("floatx", "floatx.bin.t"),
                                  ("floatize", "floatize.bin.t"),
                                  ("hexfp", "hexfp.bin.t"),
                                  ("ifid", "ifid.bin.t"),
                                  ("ifmacro", "ifmacro.bin.t"),
                                  ("iftoken", "iftoken.bin.t"),
                                  ("nasmformat", "nasmformat.bin.t"),
                                  ("radix", "radix.bin.t"),
                                  ("radix-integer", "radix-integer.bin.t"),
                                  ("xdefine", "xdefine.bin.t")):
            with self.subTest(case=stem):
                source = "cpu 8086\n" + (root / f"{stem}.asm").read_text(encoding="latin-1")
                actual = Assembler(optimize=9, compatibility="nasm3").assemble(source)
                self.assertEqual(actual, (root / golden_name).read_bytes())

    def test_official_forward_immediate_does_not_widen_memory_operand(self):
        root = FIXTURES / "nasm_official"
        source = (root / "br2003451.asm").read_text(encoding="latin-1")
        self.assertEqual(Assembler(optimize=0, compatibility="nasm3").assemble(source),
                         (root / "br2003451.bin.t").read_bytes())

    def test_case_insensitive_single_line_macros(self):
        source = """cpu 8086
%idefine Foo 7
db foo, FOO, Foo
%ixdefine Bar Foo
%idefine Foo 8
db bar, BAR, foo
%idefine Twice(x) ((x)*2)
db twice(3), TWICE(4)
%ifdef fOo
db 9
%endif
%undef fOo
%ifndef Foo
db 10
%endif
"""
        self.assertEqual(Assembler(compatibility="nasm3").assemble(source),
                         bytes((7, 7, 7, 7, 7, 8, 6, 8, 9, 10)))

    def test_case_sensitive_macro_existence_checks(self):
        source = """cpu 8086
%macro foo 0
 db 1
%endmacro
%imacro bar 0
 db 2
%endmacro
%ifdef FOO
 db 3
%endif
%ifndef FOO
 db 4
%endif
%ifmacro FOO
 db 5
%endif
%ifnmacro FOO
 db 6
%endif
%ifdef BAR
 db 7
%endif
%ifmacro BAR
 db 8
%endif
foo
BAR
"""
        self.assertEqual(Assembler(compatibility="nasm3").assemble(source), bytes((4, 6, 1, 2)))

    def test_context_stack_labels_macros_and_conditions(self):
        source = """cpu 8086
%macro repeat 0
 %push repeat
 %$begin:
%endmacro
%macro until 0
 jmp %$begin
 %pop repeat
%endmacro
repeat
nop
until
repeat
int 3
until
%if 0
db %$missing
%endif
%push outer
%assign %$x 5
%push inner
db %$$x
%assign %$x 7
db %$x
%pop inner
db %$x
%repl changed
%if 0
%elifctx changed
db 11
%endif
%ifnctx outer
db 12
%endif
%pop changed
"""
        self.assertEqual(Assembler(optimize=9, compatibility="nasm3").assemble(source),
                         bytes.fromhex("90 eb fd cd 03 eb fc 05 07 05 0b 0c"))
        self.assertEqual(Assembler(compatibility="nasm3").assemble("db 1 ; %$comment"), b"\x01")

    def test_official_integer_functions(self):
        root = FIXTURES / "nasm_official"
        source = "cpu 8086\n" + (root / "ilog.asm").read_text(encoding="latin-1")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            actual = Assembler(optimize=9, compatibility="nasm3", defines={"WARNING": "1"}).assemble(source)
        self.assertEqual(actual, (root / "ilog.bin.t").read_bytes())
        self.assertEqual(len(caught), 25)
        with self.assertRaises(AssemblyError):
            Assembler(compatibility="nasm3").assemble("cpu 8086\n%use ifunc\ndb ilog2(3)")

    def test_timestamp_builtins_with_fixed_clock(self):
        source = ("db __UTC_DATE__,0,__UTC_TIME__,0\n"
                  "dd __UTC_DATE_NUM__,__UTC_TIME_NUM__,__POSIX_TIME__")
        actual = Assembler(compatibility="nasm3", timestamp=1262293242).assemble(source)
        expected = (b"2009-12-31\x0021:00:42\x00" +
                    (20091231).to_bytes(4, "little") +
                    (210042).to_bytes(4, "little") +
                    (1262293242).to_bytes(4, "little"))
        self.assertEqual(actual, expected)

    @unittest.skipUnless(NASM, "NASM reference executable is unavailable")
    def test_official_timestamp_source(self):
        source = "cpu 8086\n" + (FIXTURES / "nasm_official" / "time.asm").read_text(encoding="latin-1")
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "time.asm"
            output_file = Path(directory) / "time.bin"
            input_file.write_text(source, encoding="latin-1")
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", str(output_file),
                                  str(input_file)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            expected = output_file.read_bytes()
        timestamp = int.from_bytes(expected[-4:], "little")
        actual = Assembler(optimize=9, compatibility="nasm3", timestamp=timestamp).assemble(source)
        self.assertEqual(actual, expected)

    def test_official_warning_stack(self):
        root = FIXTURES / "nasm_official"
        source = "cpu 8086\n" + (root / "warnstack.asm").read_text(encoding="latin-1")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            actual = Assembler(optimize=9, compatibility="nasm3").assemble(source)
        self.assertEqual(actual, (root / "warnstack.bin.t").read_bytes())
        self.assertEqual([str(item.message).split(": ", 1)[1] for item in caught],
                         ["Good warning", "Good warning", "warning stack empty", "Good warning"])

    def test_object_section_attributes_in_flat_binary(self):
        root = FIXTURES / "nasm_official"
        for stem, warning_count in (("alonesym-obj", 4), ("winalign", 5)):
            with self.subTest(source=stem), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                source = "cpu 8086\n" + (root / f"{stem}.asm").read_text(encoding="latin-1")
                actual = Assembler(optimize=0, compatibility="nasm3").assemble(source)
                self.assertEqual(actual, (root / f"{stem}.flat.bin").read_bytes())
                self.assertEqual(len(caught), warning_count)

    def test_official_exe_macro_package(self):
        root = FIXTURES / "nasm_official"
        path = root / "binexe.asm"
        source = "cpu 8086\n" + path.read_text(encoding="latin-1")
        actual = Assembler(optimize=0, compatibility="nasm3", include_paths=[root]).assemble(
            source, filename=str(path))
        self.assertEqual(actual, (root / "binexe.flat.bin").read_bytes())

    def test_official_nested_includes_and_preinclude(self):
        root = FIXTURES / "nasm_official"
        repeated = root / "br890790.asm"
        actual = Assembler(optimize=9, compatibility="nasm3", include_paths=[root]).assemble(
            "cpu 8086\n" + repeated.read_text(encoding="latin-1"), filename=str(repeated))
        self.assertEqual(actual, (root / "br890790.bin.t").read_bytes())

        path = root / "inctest.asm"
        actual = Assembler(optimize=9, compatibility="nasm3", include_paths=[root],
                           preincludes=["inc3.asm"]).assemble(
                               "cpu 8086\n" + path.read_text(encoding="latin-1"), filename=str(path))
        golden = (root / "inctest.com.t").read_bytes()
        self.assertEqual(actual, golden)
        from pynasm.cli import main
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "inctest.com"
            self.assertEqual(main(["-O9", "--compatibility", "nasm3", "-I", str(root),
                                   "-p", "inc3.asm", "-o", str(output), str(path)]), 0)
            self.assertEqual(output.read_bytes(), golden)
            preinclude = Path(directory) / "pre.inc"
            entry = Path(directory) / "entry.asm"
            preinclude.write_text("%define PRE_VALUE 7\n", encoding="ascii")
            entry.write_text("cpu 8086\ndb PRE_VALUE\n", encoding="ascii")
            self.assertEqual(main(["-p", str(preinclude), "-o", str(output), str(entry)]), 0)
            self.assertEqual(output.read_bytes(), b"\x07")

    def test_unstable_labels_and_stable_neighbor(self):
        source = (FIXTURES / "mininasm" / "unstable.nasm").read_text(encoding="latin-1")
        with self.assertRaisesRegex(AssemblyError, "did not converge"):
            Assembler(optimize=9).assemble(source)
        stable = Assembler(optimize=9, defines={"REP": "65"}).assemble(source)
        self.assertEqual(stable, b"\xeb\x7e" + b"\x90" * 126)

    def test_official_environment_macro_case(self):
        root = FIXTURES / "nasm_official"
        source = "cpu 8086\n" + (root / "br3028880.asm").read_text(encoding="latin-1")
        with patch.dict(os.environ, {"PROJECTBASEDIR": "./travis/test"}):
            actual = Assembler(optimize=9, compatibility="nasm3").assemble(source)
        self.assertEqual(actual, (root / "br3028880.bin.t").read_bytes())

    def test_invalid_input_and_later_cpu_are_distinct(self):
        invalid_syntax = ("mov [bx],[si]", "mov ax,[bx+bp]", "jmp undefined_label")
        later_cpu = ("pusha", "bound ax,[bx]", "shl ax,2", "mov ax,[eax]", "bits 32")
        for category, sources in (("invalid syntax", invalid_syntax),
                                  ("post-8086 ISA", later_cpu)):
            for source in sources:
                with self.subTest(category=category, source=source):
                    with self.assertRaises(AssemblyError):
                        Assembler(compatibility="nasm3").assemble("cpu 8086\n" + source)

    @unittest.skipUnless(NASM, "NASM reference executable is unavailable")
    def test_official_file_and_line_builtins(self):
        source = "cpu 8086\n" + (FIXTURES / "nasm_official" / "_file_.asm").read_text(
            encoding="latin-1")
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "_file_.asm"
            output_file = Path(directory) / "_file_.bin"
            input_file.write_text(source, encoding="latin-1")
            run = subprocess.run([NASM, "-f", "bin", "-O9", "-o", str(output_file),
                                  str(input_file)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            actual = Assembler(optimize=9, compatibility="nasm3").assemble(
                source, filename=str(input_file))
            self.assertEqual(actual, output_file.read_bytes())


@unittest.skipUnless(NASM and INDEPENDENT,
                     "set NASM and PYNASM_INDEPENDENT_CORPUS to run the external corpus")
class IndependentCorpusTests(unittest.TestCase):
    def test_all_8086_disassembler_sources(self):
        """Exercise the separate j-helland program corpus without vendoring it."""
        root = Path(INDEPENDENT)
        asm = root / "asm"
        self.assertTrue(asm.is_dir(), f"missing asm directory: {asm}")
        revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(revision, INDEPENDENT_COMMIT)
        files = sorted(asm.glob("*.asm"))
        self.assertEqual(len(files), 19)
        with tempfile.TemporaryDirectory() as directory:
            input_file = Path(directory) / "case.asm"
            output_file = Path(directory) / "case.bin"
            for file in files:
                source = "cpu 8086\n" + file.read_text(encoding="latin-1")
                input_file.write_text(source, encoding="latin-1")
                for level in (0, 1, 9):
                    with self.subTest(source=file.name, optimization=level):
                        run = subprocess.run([NASM, "-f", "bin", f"-O{level}",
                                              "-o", str(output_file), str(input_file)],
                                             capture_output=True, text=True)
                        self.assertEqual(run.returncode, 0, run.stderr)
                        actual = Assembler(optimize=level, compatibility="nasm3").assemble(
                            source, filename=str(file))
                        self.assertEqual(actual, output_file.read_bytes())
                        alias_source = source.replace("cpu 8086\n", "cpu 8088\n", 1)
                        alias_actual = Assembler(optimize=level, compatibility="nasm3").assemble(
                            alias_source, filename=str(file))
                        self.assertEqual(alias_actual, output_file.read_bytes())


if __name__ == "__main__":
    unittest.main()
