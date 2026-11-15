#!/usr/bin/env python3
"""Offline upgrade regression using a real KP2026-patched kernel and a core image.

No device is accessed. All generated images live in a temporary directory.
Usage: python3 checks/test_real_upgrade.py KPTTOOLS PATCHED_KERNEL KPIMG
"""
import pathlib
import struct
import subprocess
import sys
import tempfile

if len(sys.argv) != 4:
    raise SystemExit(__doc__)
tool, source, core = map(lambda p: pathlib.Path(p).resolve(), sys.argv[1:])


def preset(data):
    for offset in range(4096, len(data) - 1304 + 1, 4096):
        if data[offset:offset+8] != b'KP2026\0\0':
            continue
        saved, core_len = struct.unpack_from('<QQ', data, offset+64+8)
        if (saved + 4095) & ~4095 != offset:
            continue
        return offset, saved, core_len
    raise AssertionError('no complete KP2026 preset')


def run(*args):
    result = subprocess.run([str(tool), *map(str, args)], capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


with tempfile.TemporaryDirectory(prefix='kpatch-upgrade-') as directory:
    tmp = pathlib.Path(directory)
    original = tmp / 'original'
    run('-u', '-i', source, '-o', original)
    baseline = original.read_bytes()
    for arglen in (16, 32):
        old = bytearray(source.read_bytes())
        offset, _, core_len = preset(old)
        content = b'PAYLOAD_BOUNDARY'
        header = bytearray(128)
        header[:4] = b'kpe\0'
        struct.pack_into('<iii', header, 8, arglen, len(content), 4)
        header[20:27] = b'legacy\0'
        # This is the exact non-NUL encoding produced by original Next.
        extra = header + b'a' * arglen + content + bytes(128)
        old = old[:offset+core_len] + extra
        struct.pack_into('<Q', old, offset+64+56, len(extra))
        oldpath = tmp / 'legacy'
        oldpath.write_bytes(old)
        values = []
        for attempt in range(2):
            output = tmp / f'new-{attempt}'
            run('-p', '-i', oldpath, '-k', core, '-o', output, '-E', 'legacy')
            data = output.read_bytes()
            offset, _, core_len = preset(data)
            values.append((struct.unpack_from('<Q', data, 16)[0],
                           struct.unpack_from('<Q', data, offset+64+48)[0]))
            eoffset = offset + core_len
            args_size, con_size = struct.unpack_from('<ii', data, eoffset+8)
            assert args_size == ((arglen+1+15) & ~15)
            assert data[eoffset+128:eoffset+128+arglen] == b'a' * arglen
            assert data[eoffset+128+arglen] == 0
            assert data[eoffset+128+args_size:eoffset+128+args_size+con_size] == content
            listed = run('-l', '-i', output)
            assert 'args=' + 'a' * arglen + '\n' in listed
            assert 'PAYLOAD' not in listed
            unpatched = tmp / 'unpatched'
            run('-u', '-i', output, '-o', unpatched)
            assert unpatched.read_bytes() == baseline, 'unpatch must restore the same base kernel'
            oldpath = output
        assert values[0] == values[1], 'repatch must not grow image_size/start_offset'
        print(f'PASS: legacy {arglen}-byte args preserved through two repatches and exact unpatch')
