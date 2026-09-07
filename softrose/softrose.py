#!/usr/bin/env python3
"""
SoftRose — Thorn to ThornASM compiler

Usage:
    python softrose.py <source.rose> [output] [options]

Options:
    --asm       Output ThornASM assembly instead of binary
    --bin       Output flat binary (default)
    --help      Show this message
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compiler import compile_source


def main():
    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print(__doc__)
        sys.exit(0)

    source_path = args[0]
    output_path = None
    asm_only = False

    positional = [a for a in args[1:] if not a.startswith('-')]
    if positional:
        output_path = positional[0]

    if '--asm' in args:
        asm_only = True

    if not os.path.exists(source_path):
        print(f'error: file not found: {source_path}')
        sys.exit(1)

    with open(source_path) as f:
        source = f.read()

    if not output_path:
        base = os.path.splitext(source_path)[0]
        output_path = base + '.tsm' if asm_only else base + '.bin'

    try:
        result = compile_source(source, output_path, keep_asm=asm_only)
        if result:
            print(f'done: {output_path}')
    except SyntaxError as e:
        print(f'syntax error: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
