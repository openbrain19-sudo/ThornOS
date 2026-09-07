#!/usr/bin/env python3
"""Build ThornOS ISO image."""
import subprocess
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
assembler = os.path.join(script_dir, '..', 'thornasm', 'assembler.py')
boot_tsm = os.path.join(script_dir, 'boot.tsm')
boot_bin = os.path.join(script_dir, 'boot.bin')
mkiso = os.path.join(script_dir, 'mkiso.py')
iso_path = os.path.join(script_dir, '..', 'ThornOS.iso')

# Step 1: Assemble bootloader
print("1. assembling bootloader...")
result = subprocess.run(
    ['python', assembler, boot_tsm, boot_bin, '--bin'],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"assembly error: {result.stderr}")
    sys.exit(1)
print(f"   {result.stdout.strip()}")

# Step 2: Create ISO
print("2. creating ISO...")
result = subprocess.run(
    ['python', mkiso, boot_bin, iso_path],
    capture_output=True, text=True
)
if result.returncode != 0:
    print(f"ISO error: {result.stderr}")
    sys.exit(1)
print(f"   {result.stdout.strip()}")

print(f"\n3. done! ISO at: {iso_path}")
print("   test with: qemu-system-x86_64 -cdrom ThornOS.iso")
