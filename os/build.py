#!/usr/bin/env python3
"""Build ThornOS - assembles bootloader + kernel, creates floppy image."""
import subprocess
import struct
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NASM = 'nasm'

def run(cmd, desc):
    print(f"  {desc}...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr}")
        sys.exit(1)
    if result.stdout.strip():
        print(f"    {result.stdout.strip()}")

def main():
    print("=== Building ThornOS ===\n")

    # Check for nasm
    try:
        subprocess.run([NASM, '--version'], capture_output=True)
    except FileNotFoundError:
        print("ERROR: nasm not found. Install with: winget install nasm")
        sys.exit(1)

    # Step 1: Assemble bootloader
    print("1. assembling bootloader")
    run([NASM, '-f', 'bin', 'boot.asm', '-o', 'boot.bin'], 'boot.asm -> boot.bin')

    # Step 2: Assemble kernel
    print("2. assembling kernel")
    run([NASM, '-f', 'bin', 'kernel.asm', '-o', 'kernel.bin'], 'kernel.asm -> kernel.bin')

    # Step 3: Create floppy image
    print("3. creating floppy image")
    boot = open(os.path.join(SCRIPT_DIR, 'boot.bin'), 'rb').read()
    kernel = open(os.path.join(SCRIPT_DIR, 'kernel.bin'), 'rb').read()

    print(f"    boot: {len(boot)} bytes, kernel: {len(kernel)} bytes")

    # 1.44MB floppy
    floppy = bytearray(1474560)

    # Boot sector at sector 0
    floppy[:len(boot)] = boot

    # Kernel at sector 2 (offset 1024)
    floppy[1024:1024+len(kernel)] = kernel

    # Boot signature
    floppy[510] = 0x55
    floppy[511] = 0xAA

    img_path = os.path.join(SCRIPT_DIR, '..', 'ThornOS.img')
    with open(img_path, 'wb') as f:
        f.write(floppy)
    print(f"    created ThornOS.img ({len(floppy)} bytes)")

    print(f"\n4. done!")
    print(f"   test: qemu-system-x86_64 -fda ThornOS.img")

if __name__ == '__main__':
    main()
