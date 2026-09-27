import unittest

from pynasm import AssemblyError, assemble


class AssemblerTests(unittest.TestCase):
    def test_boot_sector_layout(self):
        source = """cpu 8086
bits 16
org 0x7c00
start: xor ax,ax
       mov ds,ax
       mov si,message
again: lodsb
       test al,al
       jz done
       mov ah,0x0e
       int 0x10
       jmp again
done:  hlt
message: db 'Hi',0
times 510-($-$$) db 0
dw 0xaa55
"""
        binary = assemble(source, optimize=9)
        self.assertEqual(len(binary), 512)
        self.assertEqual(binary[-2:], b"\x55\xaa")
        self.assertIn(b"Hi\x00", binary)

    def test_bracketed_directives(self):
        self.assertEqual(assemble("[bits 16]\n[org 0x100]\nmov ax,$"), bytes.fromhex("b80001"))
        self.assertEqual(assemble("db 1\nalign 8, inc ax"), b"\x01" + b"\x40" * 7)

    def test_forward_local_label_and_relative_jump(self):
        binary = assemble("org 0x100\njmp .end\ndb 0x90\n.end: ret\n")
        self.assertEqual(binary, bytes.fromhex("e9010090c3"))
        self.assertEqual(assemble("org 0x100\njmp .end\ndb 0x90\n.end: ret\n", optimize=9),
                         bytes.fromhex("eb0190c3"))

    def test_many_cascading_branch_relaxations(self):
        source = "cpu 8086\n" + "\n".join(
            f"jbe target{i}\ntimes 128 db 0\ntarget{i}: nop" for i in range(25)) + "\n"
        block = bytes.fromhex("7703e98000") + bytes(128) + b"\x90"
        self.assertEqual(assemble(source, compatibility="nasm3", optimize=0), block * 25)

    def test_far_qualifier_on_register_transfer(self):
        self.assertEqual(assemble("jmp far ax\ncall far bx\n", compatibility="nasm3"),
                         bytes.fromhex("ffe0ffd3"))

    def test_far_qualifier_requires_memory_outside_transfers(self):
        for source in ("push far ax", "pop far ds", "inc far ax", "not far al",
                       "shl far ax,1", "mov far ax,bx"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3")

    def test_lea_ignores_memory_data_width(self):
        source = "lea ax,byte [bx]\nlea bx,dword [si]\nlea cx,qword [di]\n"
        self.assertEqual(assemble(source, compatibility="nasm3"), bytes.fromhex("8d078d1c8d0d"))

    def test_8086_integer_operands_reject_later_widths(self):
        for source in ("inc dword [bx]", "neg qword [bx]", "mov dword [bx],1",
                       "test dword [bx],0", "rol dword [bx],1"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble("cpu 8086\n" + source, compatibility="nasm3")

    def test_8088_alias_matches_8086_instructions_and_rejections(self):
        program = ("bits 16\norg 0x100\nstart: mov ax,[bx+si+127]\n"
                   "rep movsb\nadd byte [es:di],7\n"
                   "jz done\ncall near done\n"
                   "done: fadd st0,st1\nret\n")
        for level in (0, 1, 9):
            with self.subTest(optimize=level):
                expected = assemble("cpu 8086\n" + program,
                                    compatibility="nasm3", optimize=level)
                self.assertEqual(assemble("cpu 8088\n" + program,
                                          compatibility="nasm3", optimize=level), expected)
                self.assertEqual(assemble("cpu 8088\n" + program,
                                          compatibility="nasm09839", optimize=level),
                                 assemble("cpu 8086\n" + program,
                                          compatibility="nasm09839", optimize=level))
        for instruction in ("pusha", "enter 4,0", "mov ax,[eax]",
                            "inc dword [bx]"):
            with self.subTest(instruction=instruction):
                with self.assertRaises(AssemblyError):
                    assemble("cpu 8088\n" + instruction, compatibility="nasm3")

    def test_8086_shift_count_forms(self):
        self.assertEqual(assemble("rol ax,cx\nshl byte [bx],cx\n", compatibility="nasm3"),
                         bytes.fromhex("d3c0d227"))
        self.assertEqual(assemble("rol ax,ecx\nrol ax,rcx\n", compatibility="nasm3"),
                         bytes.fromhex("d3c0d3c0"))
        for amount in ("byte 1", "word 1", "near 1", "short 1"):
            with self.subTest(amount=amount), self.assertRaises(AssemblyError):
                assemble(f"rol ax,{amount}", compatibility="nasm3")
            for level in (1, 9):
                with self.subTest(amount=amount, optimize=level):
                    self.assertEqual(assemble(f"rol ax,{amount}", compatibility="nasm3",
                                              optimize=level), bytes.fromhex("d1c0"))
        with self.assertRaises(AssemblyError):
            assemble("rol ax,strict byte 1", compatibility="nasm3", optimize=9)

    def test_nasm3_absolute_conditional_jump_selection(self):
        for level in (0, 1, 9):
            with self.subTest(optimize=level):
                self.assertEqual(assemble("jo 1", compatibility="nasm3", optimize=level),
                                 bytes.fromhex("7103e9fcff"))
                self.assertEqual(assemble("jo near $+1", compatibility="nasm3", optimize=level),
                                 bytes.fromhex("7103e9fcff"))
        self.assertEqual(assemble("jo $+1", compatibility="nasm3", optimize=9), b"\x70\xff")
        self.assertEqual(assemble("jo byte 1", compatibility="nasm3", optimize=9), b"\x70\xff")
        with self.assertRaisesRegex(AssemblyError, "short jump is out of range"):
            assemble("jo byte $+130", compatibility="nasm3", optimize=9)

    def test_nasm3_dword_branch_templates_under_cpu_8086(self):
        expected = {
            0: ("66e9ffffffff", "66e8ffffffff", "667002"),
            1: ("66e9ffffffff", "66e8ffffffff", "7103e9feffffff"),
            9: ("66eb02", "66e8ffffffff", "667002"),
        }
        for level, encodings in expected.items():
            for source, encoding in zip(("jmp dword $+5", "call dword $+5",
                                         "jo dword $+5"), encodings):
                with self.subTest(source=source, optimize=level):
                    self.assertEqual(assemble("cpu 8086\n" + source,
                                              compatibility="nasm3", optimize=level),
                                     bytes.fromhex(encoding))
        self.assertEqual(assemble("loop dword $+5\njcxz dword $+5",
                                  compatibility="nasm3", optimize=9),
                         bytes.fromhex("66e20266e302"))
        self.assertEqual(assemble("jmp word $+5", compatibility="nasm3", optimize=9),
                         bytes.fromhex("eb03"))

    def test_nasm3_explicit_prefix_order_and_branch_length(self):
        self.assertEqual(assemble("rep lock nop\nrep es movsb\nwait rep nop",
                                  compatibility="nasm3"),
                         bytes.fromhex("f0f39026f3a49bf390"))
        self.assertEqual(assemble("rep jmp $+2", compatibility="nasm3", optimize=9),
                         bytes.fromhex("f3ebff"))
        for level in (0, 1, 9):
            for source in ("repne jo $+2", "repne jo short $+2"):
                with self.subTest(source=source, optimize=level):
                    self.assertEqual(assemble(source, compatibility="nasm3", optimize=level),
                                     bytes.fromhex("f27103e9fcff"))
            self.assertEqual(assemble("repne jo dword $+3", compatibility="nasm3",
                                      optimize=level), bytes.fromhex("f27103e9fbffffff"))
        self.assertEqual(assemble("rep rep nop\nes es nop", compatibility="nasm3"),
                         bytes.fromhex("f3902690"))
        for source in ("rep repe nop", "es cs nop", "repne call $+3",
                       "repne ret", "repne ret 2", "repne retn",
                       "es mov ax,[es:bx]", "es mov ax,[cs:bx]",
                       "es fadd dword [cs:bx]"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3")

    def test_nasm3_combined_operand_qualifiers(self):
        expected = {
            "mov byte word [bx],1": "c60701",
            "mov word byte [bx],1": "c7070100",
            "jmp strict $+3": "e90000",
            "jo strict $+3": "7103e9feff",
            "jmp short near $+3": "eb01",
            "jmp near far $+3": "e90000",
        }
        for source, encoding in expected.items():
            with self.subTest(source=source):
                self.assertEqual(assemble(source, compatibility="nasm3", optimize=9),
                                 bytes.fromhex(encoding))
        for source in ("mov ax,far short 1", "jo far short $+3"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3", optimize=9)

    def test_nasm3_displacement_size_qualifiers(self):
        expected = {
            "mov ax,[byte bx]": "8b4700",
            "mov ax,[word bx]": "8b870000",
            "mov ax,[byte 0x1234]": "8b063412",
            "mov ax,[word byte 0x1234]": "8b063412",
            "mov ax,[byte word 0x1234]": "a13412",
            "mov ax,[dword 0x1234]": "67a134120000",
            "lea ax,[dword 0x1234]": "678d0534120000",
            "mov ax,[dword es:0x1234]": "2667a134120000",
            "rep mov ax,[dword 0x1234]": "67f3a134120000",
            "mov ax,[a16 bx]": "8b07",
            "mov ax,[a32 0x1234]": "67a134120000",
            "a32 mov ax,[0x1234]": "67a134120000",
            "a32 rep movsb": "67f3a4",
            "a32 jmp $+2": "67ebff",
        }
        for source, encoding in expected.items():
            with self.subTest(source=source):
                self.assertEqual(assemble(source, compatibility="nasm3", optimize=9),
                                 bytes.fromhex(encoding))
        for source in ("mov ax,[a32 word 0x1234]", "mov ax,[a16 dword 0x1234]",
                       "a32 mov ax,[bx]", "a16 a32 nop"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3", optimize=9)

    def test_nasm3_a32_legacy_loop_counter_forms(self):
        for source in ("a32 jcxz $+2", "a32 loopw $+2", "a32 loopew $+2",
                       "a32 loopzw $+2", "a32 loopnew $+2", "a32 loopnzw $+2",
                       "a32 loop $+2,cx", "a32 jcxz $+2,cx"):
            with self.subTest(source=source):
                self.assertEqual(assemble("cpu 8086\n" + source,
                                          compatibility="nasm3", optimize=9), b"")
        self.assertEqual(assemble("cpu 8086\na32 loop $+2",
                                  compatibility="nasm3", optimize=9),
                         bytes.fromhex("67e2ff"))
        for source in ("a32 loopw $+2,cx", "a32 loopw ax", "a32 jcxz ax"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble("cpu 8086\n" + source, compatibility="nasm3", optimize=9)

    def test_nasm3_operand_size_prefixes(self):
        expected = {
            "o32 nop": "6690",
            "o32 mov ax,[dword 0x1234]": "6766a134120000",
            "o32 jmp $+2": "66ebff",
            "o32 jmp word $+2": "66ebff",
            "o16 jmp dword $+2": "eb00",
            "o32 call $+3": "66e8fdffffff",
            "o32 jo $+3": "667000",
            "o32 finit": "9b66dbe3",
            "o32 wait finit": "9b66dbe3",
        }
        for source, encoding in expected.items():
            with self.subTest(source=source):
                self.assertEqual(assemble(source, compatibility="nasm3", optimize=9),
                                 bytes.fromhex(encoding))
        self.assertEqual(assemble("o32 jmp $+2", compatibility="nasm3", optimize=0),
                         bytes.fromhex("66e9fcffffff"))
        with self.assertRaises(AssemblyError):
            assemble("o16 o32 nop", compatibility="nasm3")

    def test_effective_addresses(self):
        binary = assemble("mov cx,[bx+si]\nmov cx,[bp]\nmov [es:0x1234],al\n")
        self.assertEqual(binary, bytes.fromhex("8b088b4e0026a23412"))

    def test_nasm3_linear_effective_address_expressions(self):
        expected = {
            "mov ax,[1*bx+si]": "8b00",
            "mov ax,[2*bx-bx]": "8b07",
            "mov ax,[bx+bx-bx]": "8b07",
            "mov ax,[0*(bx+si)]": "a10000",
            "mov ax,[ax-ax]": "a10000",
            "mov ax,[bx+si+(3<<2)]": "8b400c",
        }
        for source, encoding in expected.items():
            with self.subTest(source=source):
                self.assertEqual(assemble(source, compatibility="nasm3"),
                                 bytes.fromhex(encoding))
        with self.assertRaises(AssemblyError):
            assemble("mov ax,[bx*2]", compatibility="nasm3")

    def test_nasm3_displacement_before_brackets(self):
        expected = {
            "mov ax,5[bx]": "8b4705",
            "mov ax,5[word bx]": "8b870500",
            "mov ax,5[dword 0x1234]": "67a139120000",
            "mov ax,bx[si]": "8b00",
            "mov ax,target[bx]\ntarget: nop": "8b87040090",
        }
        for source, encoding in expected.items():
            with self.subTest(source=source):
                self.assertEqual(assemble(source, compatibility="nasm3", optimize=9),
                                 bytes.fromhex(encoding))
        self.assertEqual(assemble("mov ax,(target-$$)[bx]\ntarget: nop",
                                  compatibility="nasm3", optimize=0),
                         bytes.fromhex("8b470390"))
        with self.assertRaises(AssemblyError):
            assemble("mov ax,5[bx][si]", compatibility="nasm3")

    def test_include_and_define(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "body.inc").write_text("mov ax, VALUE\n")
            from pynasm import Assembler
            assembler = Assembler(include_paths=[path])
            self.assertEqual(assembler.assemble('%define VALUE 0x1234\n%include "body.inc"\n'),
                             bytes.fromhex("b83412"))

    def test_nasm3_include_path_precedence_and_quotes(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pynasm import Assembler

        with TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "nested"
            nested.mkdir()
            (root / "body.inc").write_text("db 65\n", encoding="ascii")
            (nested / "body.inc").write_text("db 66\n", encoding="ascii")
            filename = str(nested / "source.asm")
            modern = Assembler(compatibility="nasm3", include_paths=[root])
            self.assertEqual(modern.assemble('%include "body.inc"', filename=filename), b"A")
            self.assertEqual(modern.assemble('%include `body.inc`', filename=filename), b"A")
            with self.assertRaises(AssemblyError):
                modern.assemble('%include body.inc', filename=filename)
            self.assertEqual(Assembler(include_paths=[root]).assemble(
                '%include "body.inc"', filename=filename), b"B")
            (root / "pre.inc").write_text("db 67\n", encoding="ascii")
            (nested / "pre.inc").write_text("db 68\n", encoding="ascii")
            self.assertEqual(Assembler(compatibility="nasm3", include_paths=[root],
                                       preincludes=["pre.inc"]).assemble(
                                           "db 1", filename=filename), b"C\x01")
            self.assertEqual(Assembler(include_paths=[root], preincludes=["pre.inc"]).assemble(
                "db 1", filename=filename), b"D\x01")

    def test_nasm3_iffile_uses_exact_path(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pynasm import Assembler

        with TemporaryDirectory() as directory:
            root = Path(directory)
            present = root / "present.bin"
            present.write_bytes(b"A")
            assembler = Assembler(compatibility="nasm3", include_paths=[root])
            self.assertEqual(assembler.assemble(
                f'%iffile "{present.as_posix()}"\ndb 1\n%else\ndb 2\n%endif'), b"\x01")
            self.assertEqual(assembler.assemble(
                '%iffile "present.bin"\ndb 1\n%else\ndb 2\n%endif'), b"\x02")
            self.assertEqual(assembler.assemble(
                '%if 0\ndb 3\n%eliffile present.bin\ndb 1\n'
                '%else\ndb 2\n%endif'), b"")

    def test_nasm3_pathsearch_require_and_depend(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pynasm import Assembler

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "body.inc").write_text("db 65\n", encoding="ascii")
            assembler = Assembler(compatibility="nasm3", include_paths=[root])
            self.assertEqual(assembler.assemble('%pathsearch P "body.inc"\n%include P'), b"A")
            self.assertEqual(assembler.assemble('%require "body.inc"\n%require "body.inc"'), b"A")
            self.assertEqual(assembler.assemble('%include "body.inc"\n%require "body.inc"'), b"A")
            self.assertEqual(assembler.assemble('%require "missing.inc"\n'
                                                '%depend "missing.inc"\ndb 1'), b"\x01")

    def test_nasm3_incbin_ranges(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pynasm import Assembler

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.bin").write_bytes(bytes(range(5)))
            filename = str(root / "source.asm")
            assembler = Assembler(compatibility="nasm3", include_paths=[root])
            self.assertEqual(assembler.assemble(
                'incbin `sample.bin`,1,2\nincbin "sample.bin",6\n'
                'incbin "sample.bin",', filename=filename),
                bytes.fromhex("01020001020304"))
            self.assertEqual(assembler.assemble(
                'incbin "sample.bin",-1,0', filename=filename), b"")
            for source in ('incbin "sample.bin",1,2,3',
                           'incbin "sample.bin",0,"2"'):
                with self.subTest(source=source), self.assertRaises(AssemblyError):
                    assembler.assemble(source, filename=filename)
            nested = root / "nested"
            nested.mkdir()
            (nested / "sample.bin").write_bytes(b"X")
            nested_source = str(nested / "source.asm")
            self.assertEqual(assembler.assemble('incbin "sample.bin"',
                                                filename=nested_source), bytes(range(5)))
            self.assertEqual(Assembler(include_paths=[root]).assemble(
                'incbin "sample.bin"', filename=nested_source), b"X")

    def test_rejects_later_cpu_instructions(self):
        for source in ("pusha", "enter 4,0", "shl ax,2", "mov ax,[eax]", "bits 32"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source)

    def test_undefined_label(self):
        with self.assertRaisesRegex(AssemblyError, "undefined symbol"):
            assemble("jmp missing")

    def test_data_strings_and_alignment(self):
        self.assertEqual(assemble('dw "ABC"\ndd "ABCDE"\nalign 16, db 0xff'),
                         b"ABC\x00ABCDE\x00\x00\x00" + b"\xff" * 4)
        self.assertEqual(assemble(r'db "a\n",`a\n`'), b"a\\na\n")

    def test_nasm3_data_dup_and_negative_reserve(self):
        self.assertEqual(assemble("db 2 dup (2 dup (3),4)",
                                  compatibility="nasm3"), bytes.fromhex("030304030304"))
        self.assertEqual(assemble("db 1,word 2,3\ndw byte 0x1234\n"
                                  "db word (1,2)\ndb %(3,4)", compatibility="nasm3"),
                         bytes.fromhex("0102000334010002000304"))
        self.assertEqual(assemble("db tword 1.5\ndb oword 'ABC'",
                                  compatibility="nasm3"),
                         bytes.fromhex("00000000000000c0ff3f" + "414243" + "00" * 13))
        self.assertEqual(assemble("dy 'A'\nresz 1", compatibility="nasm3"),
                         b"A" + bytes(31 + 64))
        self.assertEqual(assemble("db 1\nresb -1\nend: dw end",
                                  compatibility="nasm3"), bytes.fromhex("010100"))
        for source in ("db 1 dup (2 dup (3))", "db 2 dup (1,2 dup (3))",
                       "db tword 42"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3")

    def test_invalid_effective_addresses(self):
        for address in ("[bx+bx]", "[bx*2]", "[si-bx]", "[bx+bp]"):
            with self.subTest(address=address), self.assertRaises(AssemblyError):
                assemble("mov ax," + address)

    def test_memory_immediate_size_rules(self):
        self.assertEqual(assemble("mov [bx],1\nadd [bx],1\ntest [bx],1\n"),
                         bytes.fromhex("c60701800701f60701"))
        self.assertEqual(assemble("add word [bx],byte 1"), bytes.fromhex("830701"))
        for source in ("mov ax,byte 1", "mov word [bx],byte 1", "add byte [bx],word 1"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source)

    def test_level_one_keeps_forward_jump_wide(self):
        self.assertEqual(assemble("add ax,1\nadd bx,1\njmp target\ntarget: nop", optimize=1),
                         bytes.fromhex("05010083c301e9000090"))

    def test_nasm3_level_one_widens_conditional_jump(self):
        self.assertEqual(assemble("cpu 8086\nstart: jnz start\n", optimize=1,
                                  compatibility="nasm3"), bytes.fromhex("7403e9fbff"))
        self.assertEqual(assemble("cpu 8086\nstart: jnz short start\n", optimize=1,
                                  compatibility="nasm3"), bytes.fromhex("75fe"))

    def test_multiline_macro_and_local_label(self):
        source = """%macro two_nops 0
%%again: nop
         jmp %%again
%endmacro
two_nops
two_nops
"""
        self.assertEqual(assemble(source), bytes.fromhex("90ebfd90ebfd"))
        self.assertEqual(assemble("%macro emit 1\ndb %1\n%endmacro\nhere: emit 5\ndw here"),
                         bytes.fromhex("050000"))

    def test_rep_and_assign(self):
        source = "%assign value 1\n%rep 3\ndb value\n%assign value value+1\n%endrep\n"
        self.assertEqual(assemble(source), b"\x01\x02\x03")

    def test_preprocessor_builtins_and_xdefine(self):
        source = """%define FIRST 1
%xdefine SECOND FIRST
%define FIRST 2
%ifidn __OUTPUT_FORMAT__, bin
db SECOND,FIRST,__BITS__
%endif
"""
        self.assertEqual(assemble(source), b"\x01\x02\x10")
        self.assertEqual(assemble("%if-1\ndb 7\n%endif"), b"\x07")

    def test_defstr_empty_and_quoted_source(self):
        source = '%defstr EMPTY\n%defstr QUOTED "hello"\ndb EMPTY,QUOTED\n'
        self.assertEqual(assemble(source), b'"hello"')

    def test_file_and_line_builtins(self):
        self.assertEqual(assemble("db __FILE__,0\ndw __LINE__", filename="source.asm"),
                         b"source.asm\x00\x02\x00")

    def test_malformed_radix_literals(self):
        for literal in ("0xg", "09q", "0y2", "123abc", "0b1012"):
            with self.subTest(literal=literal), self.assertRaisesRegex(
                    AssemblyError, "invalid number"):
                assemble("dd " + literal)

    def test_expression_divisor_wrapping_to_zero(self):
        with self.assertRaisesRegex(AssemblyError, "division by zero"):
            assemble("dq 1/(0xffffffffffffffff+1)")

    def test_nasm3_less_comparison_unknown_in_critical_expressions(self):
        self.assertEqual(assemble("db (1 <=> 2) ? 7 : 8", compatibility="nasm3"), b"\x00")
        for source in ("%if 1 <=> 2\n%endif", "%assign X 1 <=> 2", "times (1 <=> 2) db 1"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3")

    def test_elif_condition_families(self):
        conditions = ("%elif 1", "%elifdef FLAG", "%elifndef ABSENT",
                      "%elifidn A,A", "%elifidni A,a", "%elifnum 2",
                      "%elifnnum A", '%elifstr "x"', "%eliftoken <<",
                      "%elifempty", "%elifmacro emit 1")
        source = "cpu 8086\n%define FLAG 1\n%macro emit 1\n%endmacro\n"
        source += "".join(f"%if 0\ndb 255\n{condition}\ndb {index}\n"
                          "%else\ndb 254\n%endif\n"
                          for index, condition in enumerate(conditions, 1))
        self.assertEqual(assemble(source, compatibility="nasm3"), bytes(range(1, 12)))

    def test_nasm3_ifdirective_names(self):
        expected = {"bits": True, "db": True, "map": True, "export": False,
                    "limit": False, "%if": True, "%fatal": True,
                    "%unknown": False, '"[org 0x100]"': True}
        for name, recognized in expected.items():
            source = f"%ifdirective {name}\ndb 1\n%else\ndb 2\n%endif"
            with self.subTest(name=name):
                self.assertEqual(assemble(source, compatibility="nasm3"),
                                 b"\x01" if recognized else b"\x02")
        self.assertEqual(assemble("%if 0\ndb 3\n%elifndirective export\n"
                                  "db 1\n%else\ndb 2\n%endif",
                                  compatibility="nasm3"), b"\x01")

    def test_nasm3_use_package_conditions(self):
        source = ("%ifusable smartalign\ndb 1\n%endif\n"
                  "%ifusable standard\ndb 255\n%endif\n"
                  "%ifusing fp\ndb 255\n%else\ndb 2\n%endif\n"
                  "%use fp\n%ifusing FP\ndb 3\n%endif\n"
                  "%if 0\ndb 255\n%elifnusing ifunc\ndb 4\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("01020304"))
        self.assertEqual(assemble("%if 0\ndb 3\n%elifusable 1\ndb 1\n"
                                  "%else\ndb 2\n%endif",
                                  compatibility="nasm3"), b"")

    def test_nasm3_altreg_package(self):
        source = ("%use altreg\nmov R0W,R1W\nmov r0b,r2h\n"
                  "%ifusing altreg\ndb 1\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("89c888f001"))
        self.assertEqual(assemble("%use altreg\n%undef r0w\n%use altreg\n"
                                  "%ifdef r0w\ndb 1\n%else\ndb 2\n%endif",
                                  compatibility="nasm3"), b"\x02")
        self.assertEqual(assemble("%use altreg\n%ifdef __USE_ALTREG__\n"
                                  "db 1\n%else\ndb 2\n%endif",
                                  compatibility="nasm3"), b"\x02")

    def test_nasm3_smartalign_package(self):
        self.assertEqual(
            assemble("%use smartalign\n%ifdef __?ALIGNMODE?__\ndb 1\n%endif\n"
                     "%ifdef __ALIGNMODE__\ndb 2\n%endif\n"
                     "db __?ALIGN_JMP_THRESHOLD?__\nalignmode k8,nojmp\n"
                     "db __?ALIGN_JMP_THRESHOLD?__", compatibility="nasm3"),
            bytes.fromhex("010208ff"))
        self.assertEqual(
            assemble("%use smartalign\nalignmode generic,nojmp\n"
                     "db 1\nalign 8\ndb 2", compatibility="nasm3"),
            bytes.fromhex("018db400008d7d0002"))
        # The NASM k7 macro leaves the previous 16-bit group size in place.
        self.assertEqual(
            assemble("%use smartalign\nalignmode k7,nojmp\n"
                     "db 0\nalign 16\ndb 2", compatibility="nasm3"),
            bytes.fromhex("008db400008dbd00008db400008d7d0002"))
        self.assertEqual(
            assemble("%use smartalign\ndb 1\nalign 32\ndb 2",
                     compatibility="nasm3", optimize=9),
            b"\x01\xeb\x1d" + b"\x90" * 29 + b"\x02")
        self.assertEqual(assemble("org 0x101\ndb 1", compatibility="nasm3"), b"\x01")
        self.assertEqual(assemble("org 0x101\nsectalign 4\ndb 1",
                                  compatibility="nasm3"), b"\x00" * 3 + b"\x01")
        self.assertEqual(
            assemble("org 0x101\n%use smartalign\nalignmode generic,nojmp\n"
                     "db 1\nalign 16\ndb 2", compatibility="nasm3"),
            b"\x00" * 15 + b"\x01" + bytes.fromhex("8db400008dbd00008db400008d7d00") + b"\x02")

    def test_nasm3_masm_package(self):
        source = ("%use masm\nentry proc far\nret\nentry endp\n"
                  "mov ax,word ptr item\nmov bx,offset item\n"
                  "item: db 1\nend")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("cba10700bb070001"))
        self.assertEqual(assemble("%use masm\nfld st(0)", compatibility="nasm3"),
                         bytes.fromhex("d9c0"))
        self.assertEqual(assemble("%use masm\nmov ax,ptr byte item\n"
                                  "item: db 1", compatibility="nasm3"),
                         bytes.fromhex("8b06040001"))
        self.assertEqual(assemble("%use vtern\n%ifmacro vpternlogd 4\ndb 1\n%endif",
                                  compatibility="nasm3"), b"\x01")

    def test_nasm3_standard_section_macros(self):
        source = ("%ifdef __SECT__\ndb 1\n%endif\n"
                  "sectalign off\n%if __SECTALIGN_ALIGN_UPDATES_SECTION__\n"
                  "db 255\n%else\ndb 2\n%endif\n"
                  "section .data\n[section .text]\ndb 3\n__SECT__\ndb 4")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("0102030004"))
        self.assertEqual(
            assemble("org 0x101\nsectalign off\ndb 1\nalign 16\ndb 2",
                     compatibility="nasm3"),
            b"\x01" + b"\x90" * 15 + b"\x02")
        self.assertEqual(
            assemble("org 0x101\nsectalign off\n%use smartalign\n"
                     "alignmode generic,nojmp\ndb 1\nalign 16\ndb 2",
                     compatibility="nasm3"),
            b"\x00" * 15 + b"\x01" + bytes.fromhex("8db400008dbd00008db400008d7d00") + b"\x02")
        self.assertEqual(
            assemble("sectalign off\ndb 1\nalign 3\ndb 2",
                     compatibility="nasm3"), b"\x01\x90\x90\x02")
        with self.assertRaises(AssemblyError):
            assemble("sectalign on\ndb 1\nalign 3\ndb 2", compatibility="nasm3")

    def test_nasm3_absolute_space(self):
        source = ("absolute 0x20\na: resb 1\nb: resw 2\n"
                  "section .text\ndw a,b,$-$$")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("200021000000"))
        with self.assertRaises(AssemblyError):
            assemble("absolute 0x20\ndb 1", compatibility="nasm3")

    def test_nasm3_standard_structures(self):
        source = ("section .data\nstruc Pair\n.a: resb 1\n.b: resw 1\n"
                  "endstruc\nistruc Pair\nat .a, db 7\n"
                  "at .b, dw 0x1234\niend")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("073412"))
        self.assertEqual(assemble("%unimacro struc 1-2\n"
                                  "%ifmacro struc 1-2\ndb 1\n%else\ndb 2\n%endif",
                                  compatibility="nasm3"), b"\x02")

    def test_nasm3_preprocessor_aliases(self):
        source = ("%define target 1\n%defalias copy target\n"
                  "%define copy 2\ndb target,copy\n"
                  "%undefalias copy\n%ifdef target\ndb 3\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("020203"))
        self.assertEqual(assemble("%aliases off\ndb __?BITS?__\n"
                                  "%aliases on\ndb __BITS__",
                                  compatibility="nasm3"), bytes.fromhex("1010"))
        self.assertEqual(assemble("%defalias B A\n%ifidn B,A\ndb 1\n"
                                  "%else\ndb 2\n%endif",
                                  compatibility="nasm3"), b"\x01")
        self.assertEqual(assemble("%defalias B A\n%ifdefalias B\ndb 1\n"
                                  "%endif\n%ifndefalias A\ndb 2\n%endif",
                                  compatibility="nasm3"), b"\x01\x02")

    def test_nasm3_reserved_multiline_macro_aliases(self):
        source = ("%irmacro M 0\ndb 11\n%endmacro\n"
                  "%ifdef m\ndb 1\n%else\ndb 2\n%endif\n"
                  "%ifmacro M 0\ndb 3\n%endif\n"
                  "%ifmacro m 0\ndb 4\n%endif\nm")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x02\x03\x0b")

    def test_nasm3_reserved_difi_condition_suppresses_else(self):
        source = ("%ifdifi A,a\ndb 1\n%else\ndb 2\n%endif\n"
                  "%ifndifi A,a\ndb 3\n%else\ndb 4\n%endif\n"
                  "%if 0\n%elifdifi A,a\ndb 5\n%else\ndb 6\n%endif\n"
                  "%if 1\ndb 7\n%elifndifi A,a\ndb 8\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x07")

    def test_nasm3_conditional_identifier_lists(self):
        from unittest.mock import patch
        import os

        source = ("%define A 1\n%defalias B A\n%push Context\n"
                  "%ifdef X A\ndb 1\n%endif\n"
                  "%ifndef X A\ndb 2\n%endif\n"
                  "%ifdefalias X B\ndb 3\n%endif\n"
                  "%ifctx missing CONTEXT\ndb 4\n%endif\n"
                  "%ifenv PYNASM_MULTI_MISSING PYNASM_MULTI_PRESENT\ndb 5\n%endif\n"
                  "%ifnenv PYNASM_MULTI_MISSING PYNASM_MULTI_PRESENT\ndb 6\n%endif\n"
                  "%define V PYNASM_MULTI_PRESENT\n%ifenv V\ndb 7\n%endif\n%pop")
        with patch.dict(os.environ, {"PYNASM_MULTI_PRESENT": "yes"}, clear=True):
            self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01\x03\x04\x05\x07")

    def test_nasm3_ifidn_compares_unquoted_string_tokens(self):
        source = ("%ifidn 'A',\"A\"\ndb 1\n%else\ndb 2\n%endif\n"
                  "%ifidni `a`,'A'\ndb 3\n%else\ndb 4\n%endif\n"
                  "%ifidn A,A,B\ndb 5\n%else\ndb 6\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01\x03\x06")

    def test_nasm3_ifnum_repeated_sign_tokens(self):
        source = ("%ifnum --1\ndb 1\n%endif\n"
                  "%ifnnum - + 0xff\ndb 2\n%else\ndb 3\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01\x03")

    def test_nasm3_ifmacro_parameter_validation(self):
        source = ("%macro M 1-3\ndb %1\n%endmacro\n"
                  "%ifmacro M 1 trailing\ndb 1\n%else\ndb 2\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01")
        for condition in ("%ifmacro", "%ifnmacro", "%ifmacro 123",
                          "%ifmacro ABSENT junk", "%ifmacro M 2-1"):
            with self.subTest(condition=condition), self.assertRaises(AssemblyError):
                assemble("%macro M 1-3\n%endmacro\n" + condition +
                         "\ndb 1\n%else\ndb 2\n%endif", compatibility="nasm3")

    def test_nasm3_if_expression_ignores_trailing_tokens(self):
        source = ("%if 1 trailing\ndb 1\n%else\ndb 2\n%endif\n"
                  "%if 1 (2)\ndb 3\n%endif\n"
                  "%if 0\n%elif 0 trailing\ndb 4\n%else\ndb 5\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01\x03\x05")
        self.assertEqual(assemble("%ifn 0\ndb 6\n%endif\n"
                                  "%if 0\n%elifn 0\ndb 7\n%endif",
                                  compatibility="nasm3"), b"\x06\x07")
        with self.assertRaises(AssemblyError):
            assemble("%if 1 +\ndb 1\n%endif", compatibility="nasm3")

    def test_nasm3_unmacro_matches_greedy_signature(self):
        source = ("%macro M 1+\ndb %1\n%endmacro\n"
                  "%unmacro M 1\n%ifmacro M 1\ndb 1\n%endif\n"
                  "%unmacro M 1+\n%ifmacro M 1\ndb 2\n"
                  "%else\ndb 3\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01\x03")
        with self.assertRaises(AssemblyError):
            assemble("%unmacro M 2-1\ndb 1", compatibility="nasm3")

    def test_nasm3_pragma_controls_empty_macro_expansion(self):
        macro = "%define E\n%macro M 1\ndb %0\n%endmacro\nM E"
        self.assertEqual(assemble(macro, compatibility="nasm3"), b"\x00")
        self.assertEqual(assemble("%pragma preproc sane_empty_expansion yes\n" + macro,
                                  compatibility="nasm3"), b"")
        self.assertEqual(assemble("%pragma preproc unknown_option yes\n"
                                  "%pragma dbg ignored option\ndb 1",
                                  compatibility="nasm3"), b"\x01")

    def test_nasm3_multiline_macro_overloads(self):
        source = ("%macro M 0\ndb 1\n%endmacro\n"
                  "%macro M 1\ndb 2\n%endmacro\n"
                  "%ifmacro M 0\ndb 3\n%endif\n"
                  "M\nM 7\n%unmacro M 1\nM\n"
                  "%ifmacro M 1\ndb 4\n%else\ndb 5\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x03\x01\x02\x01\x05")

    def test_nasm3_multiline_macro_braces_and_empty_tail(self):
        source = ("%macro A 1\ndb %1\n%endmacro\nA {7,8}\n"
                  "%macro B 2\ndb %0\n%endmacro\nB 1,\n"
                  "%macro C 1-2 {9}\ndb %0,%2\n%endmacro\nC 1,")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x07\x08\x01\x02\x09")

    def test_nasm3_macro_commas_inside_parentheses_and_brackets(self):
        source = ("%macro M 2\ndb %0\n%endmacro\nM (1,2)\nM [1,2]\n"
                  "%macro N 1-3 (7,8)\ndb %0\n%endmacro\nN 1")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x02\x02\x03")

    def test_nasm3_macro_range_names_and_quoted_literals(self):
        source = ("%macro M 3\ndb %{3:1}\ndb '%1'\n%endmacro\nM 1,2,3\n"
                  "%imacro Foo 0\n%ifidn %?,foo\ndb 4\n%endif\n"
                  "%ifidn %??,Foo\ndb 5\n%endif\n%endmacro\nfoo")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x03\x02\x01%1\x04\x05")

    def test_nasm3_macro_condition_code_parameters(self):
        source = ("cpu 8086\n%macro M 2\n%rotate 1\n"
                  "j%+1 L\nj%-2 L\nL:\ndb '%+1', '%-2'\n%endmacro\nM e,ne")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("75027500") + b"%+1%-2")
        for condition in ("cxz", "ecxz", "rcxz", "foo"):
            source = ("%macro M 1\n%ifidn %-1,cxz\ndb 1\n%endif\n"
                      f"%endmacro\nM {condition}")
            with self.subTest(condition=condition), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3")

    def test_nasm3_macro_indirection(self):
        source = ("%define N 16\n%define Foo16 7\n"
                  "%define Eager %[Foo%[N]]\n%undef Foo16\n"
                  "db Eager, '%[N]'\n"
                  "%define Foo16 8\n%macro M%[N] 0\ndb Foo%[N]\n%endmacro\nM16")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x07%[N]\x08")
        self.assertEqual(assemble("db 1 ; %[unterminated", compatibility="nasm3"),
                         b"\x01")

    def test_nasm3_single_line_macro_name_references(self):
        source = ("%idefine Foo x%?\nfoo equ 7\nFOO equ 8\n"
                  "db xfoo,xFOO\n%undef Foo\n"
                  "%idefine Foo x%??\nfoo equ 9\ndb xFoo")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x07\x08\x09")
        source = ("%imacro M 0\n%idefine Foo x%*?\n%endmacro\n"
                  "M\nfoo equ 7\ndb xfoo")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x07")

    def test_nasm3_greedy_single_line_macro_and_conditional_comma(self):
        source = ("%define F(a,b,c+) a + 66 %, b * 3 %, c\n"
                  "db F(1,2)\ndb F(1,2,3,4)\n"
                  "%define E\n%define G(x) 1 %, x\ndb G(E)\n"
                  "%define H(a,b) 7\ndb H([1,2])")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("4306430603040107"))
        with self.assertRaises(AssemblyError):
            assemble("%define H(a,b) 7\ndb H([1,2],3)",
                     compatibility="nasm3")

    def test_nasm3_single_line_macro_parameter_flags(self):
        source = ("%define F(=x,&y) x,y\ndb F(2+3,Hi)\n"
                  "%define U(,x) x\ndb U(1,7)\n"
                  "%define N() 9\ndb N(4)\n"
                  "%define Q(!&x) x\ndb Q(  A  )")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x05Hi\x07\x09 A ")
        for source in ("%define F(=x) x\ndb F(missing)",
                       "%define F(=x/z) x\ndb F(7)"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source, compatibility="nasm3")

    def test_nasm3_single_line_macro_overloads(self):
        source = ("%define F(x) x+1\n%define F(x,y) x+y\n"
                  "db F(2),F(2,3)\n"
                  "%idefine Foo(x) %??\n%idefine fOO(x,y) %??\n"
                  "%ifidn foo(7),Foo\ndb 6\n%endif\n"
                  "%ifidn FOO(7,8),fOO\ndb 7\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x03\x05\x06\x07")
        with self.assertRaises(AssemblyError):
            assemble("%define F 1\n%define F(x) 2\ndb F(7)",
                     compatibility="nasm3")

    def test_nasm3_single_line_macro_recursion_guard(self):
        source = ("%define A A+1\n%defstr SA A,A\ndb SA\n"
                  "%define F(x) 1+F(x)\n%defstr SF F(3)\ndb SF\n"
                  "%define B C\n%define C B\n%defstr SB B\ndb SB")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"A+1,A+11+F(3)B")

    def test_nasm3_deep_acyclic_single_line_macro_chain(self):
        chain = "\n".join(f"%define M{index} M{index + 1}"
                          for index in range(513))
        source = f"{chain}\n%define M513 7\ndb M0"
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x07")

    def test_nasm3_dollarhex_switch_and_dollar_symbol(self):
        source = ("db $1a\n[dollarhex off]\n$12: db $12-$\n"
                  "%define $1a 3\ndb $1a\n[dollarhex on]\ndb $12")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         b"\x1a\x00\x03\x12")
        with self.assertRaises(AssemblyError):
            assemble("db $ff", compatibility="nasm3")

    def test_nasm3_float_rounding_and_denormal_switches(self):
        source = ("[float up]\ndd 1.0000001\n"
                  "[float down]\ndd -1.0000001\n"
                  "[float daz]\ndd 1e-40\n"
                  "[float default]\ndd 1e-40")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("0100803f010080bf00000000c2160100"))
        source = ("float daz,up\n%ifidni __?FLOAT_ROUND?__,up\n"
                  "db 7\n%endif\n%ifidni __?FLOAT_DAZ?__,daz\n"
                  "db 8\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x07\x08")

    def test_nasm3_float_directed_rounding_precision_boundaries(self):
        source = ("[float up]\ndd 1e-40,1.1e10,1.000000059604644775390625\n"
                  "dw 1.0001\n[float down]\ndd -1e-50")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("c2160100abe923500000803f003c00000080"))

    def test_nasm3_default_bnd_and_explicit_bnd(self):
        source = "[default bnd]\ncall L\nL: ret\n[default nobnd]\nret"
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("f2e80000f2c3c3"))
        self.assertEqual(assemble("[default bnd]\njmp L\nL: nop",
                                  compatibility="nasm3", optimize=9),
                         bytes.fromhex("eb0090"))
        self.assertEqual(assemble("bnd jmp L\nL: nop",
                                  compatibility="nasm3", optimize=9),
                         bytes.fromhex("f2e9000090"))

    def test_nasm3_flat_binary_global_directive_acceptance(self):
        source = ("[list -]\n[debug foo bar]\n[prefix X]\n"
                  "[extern unused]\n[required later]\n[static here]\n"
                  "here: db 7\nlater: db 8")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x07\x08")
        with self.assertRaises(AssemblyError):
            assemble("[extern missing]\ndw missing", compatibility="nasm3")

    def test_nasm3_nested_rep_exit_and_macro_rotation(self):
        source = ("%macro M 2\n%rep 2\ndb %1\n%rep 3\ndb %2\n"
                  "%exitrep\n%endrep\n%rotate 1\n%endrep\n%endmacro\nM 4,5")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x04\x05\x05\x04")

    def test_nasm3_braced_preprocessor_tokens(self):
        source = ("%{define} N 7\n%macro M 0\n"
                  "%{%local}: db N\njmp %{%local}\n%endmacro\n"
                  "M\ndb 5 %{} 2")
        self.assertEqual(assemble(source, compatibility="nasm3", optimize=9),
                         bytes.fromhex("07ebfd01"))

    def test_nasm3_clear_macro_categories_and_context(self):
        source = ("%define A 1\n%defalias B A\n%macro M 0\ndb 3\n%endmacro\n"
                  "%clear defalias\ndb A\n%clear define\n"
                  "%ifdef A\ndb 2\n%endif\nM\n%clear macro\n"
                  "%ifmacro M 0\ndb 4\n%else\ndb 5\n%endif")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01\x03\x05")
        source = ("%define A 1\n%push C\n%define %$B 2\n"
                  "%clear context define\ndb A\n"
                  "%ifdef %$B\ndb 3\n%else\ndb 4\n%endif\n%pop")
        self.assertEqual(assemble(source, compatibility="nasm3"), b"\x01\x04")
        self.assertEqual(assemble("%clear\n%ifdef __?LINE?__\ndb 1\n"
                                  "%else\ndb 2\n%endif", compatibility="nasm3"), b"\x02")
        self.assertEqual(assemble("%define __?LINE?__ 7\ndb __?LINE?__",
                                  compatibility="nasm3"), b"\x07")

    def test_nasm3_line_directive_and_macro_body_location(self):
        self.assertEqual(assemble("%line 40+2 'virtual.asm'\ndb __LINE__\n"
                                  "db __LINE__\ndb __FILE__",
                                  compatibility="nasm3"), bytes((42, 44)) + b"virtual.asm")
        self.assertEqual(assemble("%macro M 0\ndb __LINE__\n%endmacro\n"
                                  "%line 30\nM\ndb __LINE__",
                                  compatibility="nasm3"), b"\x02\x20")
        self.assertEqual(assemble("%rep 2\n%line 20\ndb __LINE__\n"
                                  "%endrep\ndb __LINE__",
                                  compatibility="nasm3"), b"\x15\x15\x17")

    def test_nasm3_16_bit_stack_argument_and_local_directives(self):
        self.assertEqual(assemble("%stacksize large\n%arg a:WORD,b:WORD\n"
                                  "mov ax,[a]\nmov bx,[b]",
                                  compatibility="nasm3"), bytes.fromhex("8b46048b5e06"))
        self.assertEqual(assemble("%push C\n%assign %$localsize 0\n"
                                  "%stacksize small\n%local a:WORD\n"
                                  "mov ax,[a]\ndb %$localsize\n%pop",
                                  compatibility="nasm3"), bytes.fromhex("8b46fe02"))
        self.assertEqual(assemble("%arg a:WORD\n%stacksize large\nmov ax,[a]",
                                  compatibility="nasm3"), bytes.fromhex("8b4604"))

    def test_nasm3_preprocessor_string_directives(self):
        source = ("%strcat S 'ab','cd'\n%strlen N S\ndb N,S\n"
                  "%substr T S,2,2\ndb T\n"
                  "%deftok OP 'mov ax,1'\nOP")
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("04616263646263b80100"))
        self.assertEqual(assemble("%strcat S `a\\n`,'b'\ndb S",
                                  compatibility="nasm3"), b"a\nb")
        self.assertEqual(assemble("%substr S 'abcdef' (1+1),3\ndb S",
                                  compatibility="nasm3"), b"bcd")
        self.assertEqual(assemble("%substr S 'abcdef',2 3\ndb S",
                                  compatibility="nasm3"), b"b")
        self.assertEqual(assemble("%substr S 'abcdef',2,3,4\ndb S",
                                  compatibility="nasm3"), b"bcd")

    def test_nasm3_user_message_directives(self):
        import warnings

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            self.assertEqual(assemble("%note 'checking'\ndb 1",
                                      compatibility="nasm3"), b"\x01")
            self.assertIn("checking", str(recorded[0].message))
        with self.assertRaisesRegex(AssemblyError, "stop"):
            assemble("%define MESSAGE 'stop'\n%fatal MESSAGE",
                     compatibility="nasm3")
        with self.assertRaisesRegex(AssemblyError, "stop"):
            assemble("%define MESSAGE 'stop'\n%error MESSAGE",
                     compatibility="nasm3")

    def test_multi_character_operator_is_one_preprocessor_token(self):
        source = "".join(f"%iftoken {operator}\ndb {index}\n%endif\n"
                         for index, operator in enumerate(("^^", "<=>", "<<<", ">>>", "<>"), 1))
        self.assertEqual(assemble(source, compatibility="nasm3"), bytes(range(1, 6)))

    def test_cli_define_without_value(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from pynasm.cli import main

        with TemporaryDirectory() as directory:
            source = Path(directory) / "define.asm"
            output = Path(directory) / "define.bin"
            source.write_text("%ifempty TEST\ndb 1\n%else\ndb 2\n%endif\n")
            self.assertEqual(main(["-DTEST", "-o", str(output), str(source)]), 0)
            self.assertEqual(output.read_bytes(), b"\x01")
            self.assertEqual(main(["-DTEST=1", "-o", str(output), str(source)]), 0)
            self.assertEqual(output.read_bytes(), b"\x02")

    def test_environment_conditional_absent(self):
        from unittest.mock import patch
        import os

        source = "%ifenv PYNASM_TEST_UNSET\ndb 1\n%elifnenv PYNASM_TEST_UNSET\ndb 2\n%endif\n"
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(assemble(source), b"\x02")

    def test_environment_substitution_skips_string_literals(self):
        from unittest.mock import patch
        import os

        source = "db '%!PYNASM_TEST_VALUE',0\n%defstr VALUE %!PYNASM_TEST_VALUE\ndb VALUE\n"
        with patch.dict(os.environ, {"PYNASM_TEST_VALUE": "HELLO"}):
            self.assertEqual(assemble(source), b"%!PYNASM_TEST_VALUE\x00HELLO")

    def test_fp_package_conversion_aliases(self):
        source = "%use fp\ndw float16(1.5),bfloat16(1.5)\ndd float32(1.5)\n"
        self.assertEqual(assemble(source, compatibility="nasm3"),
                         bytes.fromhex("003ec03f0000c03f"))

    def test_pinned_nasm_encoding_choice(self):
        self.assertEqual(assemble("xchg al,bl"), bytes.fromhex("86d8"))
        self.assertEqual(assemble("xchg al,bl", compatibility="nasm3"), bytes.fromhex("86c3"))

    def test_function_define_and_preprocessor_condition_errors(self):
        source = "%define twice(x) (x)*2\n%define sum(x,y) (x)+(y)\ndb twice(sum(1,2))\n"
        self.assertEqual(assemble(source), b"\x06")
        with self.assertRaises(AssemblyError):
            assemble("%if MISSING\ndb 1\n%endif")

    def test_legacy_profile_rejects_modern_aliases(self):
        for source in ("brkpt", "int03", "fwait", "iretw", "retw", "loopw $+2",
                       "lea ax,5", "mov ax,es:5", "mov ax,abs 5"):
            with self.subTest(source=source), self.assertRaises(AssemblyError):
                assemble(source)


if __name__ == "__main__":
    unittest.main()
