"""Final-pass byte provenance and CLI listing lifecycle."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pynasm import Assembler, AssemblyError
from pynasm.cli import main
from pynasm.listing import render_listing

NASM = os.environ.get('NASM', shutil.which('nasm'))


class ListingTests(unittest.TestCase):
    def test_final_pass_branch_and_wrapping(self):
        assembler = Assembler(optimize=9, compatibility='nasm3')
        binary = assembler.assemble('org 0x100\njmp end\ntimes 130 db 0x55\nend: ret\n')
        rows = [row for row in assembler.listing if row.size]
        self.assertEqual(binary, bytes.fromhex('e98200') + b'\x55' * 130 + b'\xc3')
        self.assertEqual([(r.offset, r.address, r.size) for r in rows],
                         [(0, 0x100, 3), (3, 0x103, 130), (133, 0x185, 1)])
        self.assertEqual(b''.join(row.data for row in rows), binary)
        listing = render_listing(assembler.listing)
        self.assertIn('00000000 E98200', listing)
        self.assertIn('00000003 5555555555555555-', listing)
        self.assertIn('00000085 C3', listing)
        self.assertEqual(listing.count('times 130'), 1)

    def test_sections_virtual_addresses_bss_and_absolute(self):
        assembler = Assembler(compatibility='nasm3')
        binary = assembler.assemble('section .text vstart=0x1000\ndb 0x11\n'
                                    'section .data start=16 vstart=0x2000\ndb 0x22,0x33\n'
                                    'section .bss\nresb 3\nabsolute 0x5000\nresw 2\n')
        rows = [row for row in assembler.listing if row.size]
        self.assertEqual(binary, b'\x11' + b'\0' * 15 + b'\x22\x33')
        self.assertEqual((rows[0].offset, rows[0].address, rows[0].file_offset), (0, 0x1000, 0))
        self.assertEqual((rows[1].offset, rows[1].address, rows[1].file_offset), (0, 0x2000, 16))
        self.assertEqual((rows[2].section, rows[2].size, rows[2].file_offset, rows[2].data),
                         ('.bss', 3, None, b''))
        self.assertEqual((rows[3].section, rows[3].address, rows[3].size, rows[3].data),
                         (None, 0x5000, 4, b''))
        self.assertIn('<res 3>', render_listing(assembler.listing))

    def test_include_macro_and_incbin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            include = root / 'macro.inc'
            include.write_text('%macro emit 1\ndb %1\n%endmacro\nemit 0x12\n')
            (root / 'data.bin').write_bytes(b'\x34\x56')
            assembler = Assembler(include_paths=[root], compatibility='nasm3')
            binary = assembler.assemble('%include "macro.inc"\nincbin "data.bin"\n', filename='main.asm')
            rows = [row for row in assembler.listing if row.size]
            self.assertEqual(binary, b'\x12\x34\x56')
            self.assertEqual(Path(rows[0].filename), include.resolve())
            self.assertEqual(rows[0].data, b'\x12')
            self.assertIn('0x12', rows[0].text)
            self.assertEqual((rows[1].filename, rows[1].number, rows[1].data),
                             ('main.asm', 2, b'\x34\x56'))

    def test_failed_reuse_does_not_publish_previous_listing(self):
        assembler = Assembler()
        assembler.assemble('db 1')
        self.assertTrue(assembler.listing)
        with self.assertRaises(AssemblyError):
            assembler.assemble('invalid_instruction ax,bx')
        self.assertEqual(assembler.listing, ())

    def test_cli_products_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, binary, listing = root/'probe.asm', root/'probe.bin', root/'probe.lst'
            source.write_text('db 0x12\n')
            args = ['-l', str(listing), '-o', str(binary), str(source)]
            self.assertEqual(main(args), 0)
            self.assertIn('00000000 12', listing.read_text())
            source.write_text('bad_instruction ax,bx\n')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertFalse(binary.exists())
            self.assertFalse(listing.exists())
            source.write_text('db 1\n')
            original = Path.write_text
            def fail_listing(path, data, **kwargs):
                original(path, data[:10], **kwargs)
                raise OSError('simulated listing write failure')
            with patch.object(Path, 'write_text', fail_listing), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 1)
            self.assertFalse(binary.exists())
            self.assertFalse(listing.exists())

    def test_cli_rejects_output_aliases_before_deleting_anything(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, binary = root/'input.asm', root/'input.bin'
            source.write_text('db 1\n'); binary.write_bytes(b'old')
            for listing in (source, binary):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(['-l',str(listing),'-o',str(binary),str(source)]),1)
                self.assertEqual(source.read_text(),'db 1\n')
                self.assertEqual(binary.read_bytes(),b'old')

    @unittest.skipUnless(NASM, 'NASM reference executable is unavailable')
    def test_native_listing_offsets_and_resolved_instruction_bytes(self):
        # No relocation-bearing operands: NASM brackets those in its own format.
        source = 'org 0x100\npush bp\nmov bp,sp\nsub sp,byte 4\nmov ax,0x1234\nret\n'
        assembler = Assembler(optimize=9, compatibility='nasm3')
        actual = assembler.assemble(source)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src, out, listing = root/'test.asm', root/'test.bin', root/'test.lst'
            src.write_text(source)
            run = subprocess.run([NASM,'-Ox','-f','bin','-l',str(listing),'-o',str(out),str(src)],
                                 capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(actual, out.read_bytes())
            native_rows = []
            for line in listing.read_text().splitlines():
                fields = line.split()
                if len(fields) > 2 and len(fields[1]) == 8:
                    native_rows.append((int(fields[1],16), bytes.fromhex(fields[2])))
            self.assertEqual([(r.offset,r.data) for r in assembler.listing if r.size], native_rows)


if __name__ == '__main__':
    unittest.main()
