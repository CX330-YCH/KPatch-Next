#!/usr/bin/env python3
"""Exercise the real kptools parser/unpatcher on legacy and enlarged Next images."""
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

TOOL = str(pathlib.Path(sys.argv.pop(1) if len(sys.argv) > 1 else 'tools/kptools').resolve())


def image(enlarged=False, extra=b'\0' * 128):
    original = bytearray(4096)
    struct.pack_into('<I', original, 0, 0x14000020)
    struct.pack_into('<Q', original, 16, 0x10000)
    original[56:60] = b'ARM\x64'
    original[128:128 + len(b'Linux version 6.12.30-test\0')] = b'Linux version 6.12.30-test\0'
    # A false positive magic in ordinary kernel data must not mask the real preset.
    original[512:520] = b'KP2026\0\0'
    core = bytearray(4096)
    core[:8] = b'KP2026\0\0'
    core[8:12] = bytes([0, 5, 13, 0])
    for offset, value in [(8,4096), (16,4096), (24,0x10000), (32,12), (40,4096),
                          (48,0x10000), (56,len(extra))]:
        struct.pack_into('<Q', core, 64 + offset, value)
    core[64+144:64+152] = original[:8]
    patched = original + core + extra
    struct.pack_into('<I', patched, 0, 0x14000800)
    if enlarged:
        struct.pack_into('<Q', patched, 16, 0x20000)
    return original, patched


class PresetUpgrade(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name)

    def call(self, data, *args):
        src = self.path / 'kernel'
        src.write_bytes(data)
        return subprocess.run([TOOL, *args, '-i', str(src)], capture_output=True, text=True)

    def test_legacy_and_enlarged_header_roundtrip(self):
        for enlarged in (False, True):
            original, patched = image(enlarged)
            listed = self.call(patched, '-l')
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn('patched=true', listed.stdout)
            dest = self.path / 'original'
            unpatched = self.call(patched, '-u', '-o', str(dest))
            self.assertEqual(unpatched.returncode, 0, unpatched.stderr)
            self.assertEqual(dest.read_bytes(), original)
            self.assertIn('patched=false', self.call(original, '-l').stdout)

    def test_truncated_preset_rejected_for_unpatch(self):
        _, patched = image()
        result = self.call(patched[:4096+128], '-u', '-o', str(self.path / 'bad'))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.path / 'bad').exists())

    def test_invalid_extra_lengths_rejected(self):
        for args_len, content_len in [(-1,0), (0,-1), (4096,0), (0,4096)]:
            extra = bytearray(128)
            extra[:4] = b'kpe\0'
            struct.pack_into('<iii', extra, 8, args_len, content_len, 1)
            _, patched = image(extra=extra)
            self.assertNotEqual(self.call(patched, '-l').returncode, 0)

    def test_extra_count_bounded(self):
        extra = bytearray(128)
        extra[:4] = b'kpe\0'
        struct.pack_into('<i', extra, 16, 4)
        _, patched = image(extra=extra * 33)
        self.assertNotEqual(self.call(patched, '-l').returncode, 0)

    def test_unterminated_banner_rejected(self):
        original, _ = image()
        original[128:] = b'Linux version 6.12.30' + b'x' * (4096-128-len(b'Linux version 6.12.30'))
        self.assertNotEqual(self.call(original, '-l').returncode, 0)

    def test_legacy_aligned_arguments_are_bounded(self):
        for arglen in (16, 32):
            args = b'a' * arglen
            content = b'PAYLOAD_BOUNDARY'
            extra = bytearray(128)
            extra[:4] = b'kpe\0'
            struct.pack_into('<iii', extra, 8, arglen, len(content), 4)
            extra[20:24] = b'raw\0'
            original, patched = image(extra=extra + args + content + bytes(128))
            listed = self.call(patched, '-l')
            self.assertEqual(listed.returncode, 0, listed.stderr)
            self.assertIn('args=' + args.decode() + '\n', listed.stdout)
            self.assertNotIn('PAYLOAD', listed.stdout)
            dest = self.path / 'original'
            unpatched = self.call(patched, '-u', '-o', str(dest))
            self.assertEqual(unpatched.returncode, 0, unpatched.stderr)
            self.assertEqual(dest.read_bytes(), original)

    def test_tiny_image_rejected(self):
        self.assertNotEqual(self.call(b'ARM\x64', '-l').returncode, 0)


if __name__ == '__main__':
    unittest.main()
