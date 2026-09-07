#!/usr/bin/env python3
"""
SPINE-64 Assembler (ThornASM)
Compiles .tsm assembly source to x86-64 binary.

Usage:
    python assembler.py <source.tsm> [output] [options]

Options:
    --bin       Output flat binary (for bootloaders)
    --elf       Output ELF64 executable (default)
    --kernel    Enable kernel mode (disallow m1/m2 registers)
    --base ADDR Set base address (default: 0x400000 for ELF, 0x7C00 for boot)
    --help      Show this message
"""

import sys
import os
from lexer import tokenize_source
from parser import Parser
from codegen import assemble


def main():
    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print(__doc__)
        sys.exit(0)

    source_path = args[0]
    output_path = None
    fmt = None
    kernel = False
    base_addr = 0x400000

    positional = [a for a in args[1:] if not a.startswith('-')]
    if positional:
        output_path = positional[0]

    if '--bin' in args:
        fmt = 'bin'
    elif '--elf' in args:
        fmt = 'elf'
    if '--kernel' in args:
        kernel = True
    if '--base' in args:
        idx = args.index('--base')
        if idx + 1 < len(args):
            base_addr = int(args[idx + 1], 0)

    if not os.path.exists(source_path):
        print(f"error: file not found: {source_path}")
        sys.exit(1)

    with open(source_path) as f:
        source = f.read()

    # Auto-detect bootloader from origin directive (only if user didn't specify format)
    if fmt is None:
        if 'origin 0x7C00' in source or 'origin 0x7c00' in source:
            fmt = 'bin'
            base_addr = 0x7C00
        else:
            fmt = 'elf'

    if not output_path:
        base = os.path.splitext(source_path)[0]
        output_path = base + '.bin' if fmt == 'bin' else base

    try:
        result = assemble(source, output_path=output_path, format=fmt,
                         kernel=kernel, base_addr=base_addr)
        print(f"done: {output_path} ({len(result)} bytes)")
    except SyntaxError as e:
        print(f"syntax error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
