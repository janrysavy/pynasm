"""CLI contracts exercised by downstream build systems."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pynasm.cli import main


class CliTests(unittest.TestCase):
    def test_nasm_include_aliases_and_order(self):
        for spelling in ('-i', '-I', '--include', '-iATTACHED', '-IATTACHED'):
            with self.subTest(spelling=spelling), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                first=root/'include one';first.mkdir()
                second=root/'include two';second.mkdir()
                (first/'value.inc').write_text('db 0x12,0x34\n')
                (second/'value.inc').write_text('db 0xFF\n')
                source=root/'input.asm';source.write_text('%include "value.inc"\n')
                output=root/'output.bin'
                option=([spelling.replace('ATTACHED',str(first))] if 'ATTACHED' in spelling
                        else [spelling,str(first)])
                self.assertEqual(main([*option,'-I',str(second),'-o',str(output),str(source)]),0)
                self.assertEqual(output.read_bytes(),bytes.fromhex('1234'))

    def test_failure_removes_stale_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input.asm';output=root/'input.bin'
            source.write_text('db 0x12\n')
            self.assertEqual(main([str(source)]),0)
            self.assertTrue(output.exists())
            source.write_text('not_an_instruction ax,bx\n')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(source)]),1)
            self.assertFalse(output.exists())

    def test_source_is_never_overwritten_or_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.asm';source.write_text('db 1\n')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['-o',str(source),str(source)]),1)
            self.assertEqual(source.read_text(),'db 1\n')

    def test_hardlinked_source_is_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.asm';source.write_text('db 1\n')
            output=Path(tmp)/'alias.bin'
            os.link(source, output)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['-o',str(output),str(source)]),1)
            self.assertEqual(source.read_text(),'db 1\n')
            self.assertTrue(output.samefile(source))

    def test_partial_write_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'input.asm';source.write_text('db 1,2\n')
            output=source.with_suffix('.bin')
            original=Path.write_bytes
            def fail_write(path, data):
                original(path, data[:1])
                raise OSError('simulated full disk')
            with patch.object(Path,'write_bytes',fail_write), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(source)]),1)
            self.assertFalse(output.exists())


if __name__=='__main__':unittest.main()
