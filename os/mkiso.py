#!/usr/bin/env python3
"""Create a minimal bootable ISO 9660 image with El Torito boot."""
import struct
import os

def create_iso(boot_bin_path, output_path):
    with open(boot_bin_path, 'rb') as f:
        boot_data = f.read()

    assert len(boot_data) == 512, f"Boot sector must be 512 bytes, got {len(boot_data)}"

    # ISO 9660 structures
    # We create a minimal ISO with:
    # - System Area (32KB, first 16 sectors) - contains El Torito boot catalog
    # - Volume Descriptor (at sector 16)
    # - Root Directory (at sector 17)
    # - Boot Catalog (at sector 18)
    # - Boot Image (at sector 19)

    SECTOR = 2048
    sectors = []

    # Sector 0-15: System Area (El Torito boot record)
    system_area = bytearray(SECTOR * 16)

    # El Torito Boot Record at sector 17 (offset in system area)
    # Boot Catalog is at sector 18
    boot_catalog_lba = 18

    # Boot Record Volume Descriptor at sector 16
    brvd = bytearray(SECTOR)
    brvd[0] = 0x43  # type: Boot Record
    brvd[1:6] = b'CD001'
    brvd[6] = 0x01  # version
    brvd[7:24] = b'EL TORITO SPECIFICATION'
    brvd[88] = 0x00  # unused
    struct.pack_into('<I', brvd, 73, boot_catalog_lba)  # boot catalog pointer
    sectors.append(brvd)

    # Boot Catalog (sector 18)
    catalog = bytearray(SECTOR)

    # Validation Entry (offset 0)
    catalog[0] = 0x01  # Header ID
    catalog[1] = 0x00  # Platform ID (x86)
    catalog[2:4] = b'\x00\x00'  # reserved
    catalog[4:32] = b'ThornOS Bootable ISO'  # ID string (24 bytes)
    catalog[32:34] = struct.pack('<H', 0xAA55)  # checksum
    catalog[34] = 0x55  # key byte 1
    catalog[35] = 0xAA  # key byte 2

    # Initial/Default Entry (offset 32)
    entry = bytearray(32)
    entry[0] = 0x88  # bootable flag
    entry[1] = 0x00  # media type (no emulation)
    entry[2:4] = b'\x00\x00'  # load segment
    entry[4] = 0x00  # system type
    entry[5] = 0x00  # unused
    struct.pack_into('<H', entry, 6, 1)  # number of 512-byte sectors
    struct.pack_into('<I', entry, 8, 19)  # load LBA
    entry[12:32] = b'\x00' * 20  # unused

    catalog[32:64] = entry
    sectors.append(catalog)

    # Boot Image (sector 19) - our bootloader padded to 2048 bytes
    boot_sector = bytearray(SECTOR)
    boot_sector[:len(boot_data)] = boot_data
    sectors.append(boot_sector)

    # Root Directory Entry (sector 17)
    root_dir = bytearray(SECTOR)

    # Volume Descriptor Set Terminator (at end of system area, sector 15)
    terminator = bytearray(SECTOR)
    terminator[0] = 0xFF  # type: terminator
    terminator[1:6] = b'CD001'
    terminator[6] = 0x01

    # Build the image
    image = bytearray()

    # System area (16 sectors = 32KB)
    image.extend(system_area)

    # BRVD (sector 16)
    image.extend(sectors[0])

    # Root directory (sector 17)
    image.extend(root_dir)

    # Boot catalog (sector 18)
    image.extend(sectors[1])

    # Boot image (sector 19)
    image.extend(sectors[2])

    # Pad to at least 512KB for ISO
    while len(image) < 512 * 1024:
        image.extend(b'\x00' * SECTOR)

    with open(output_path, 'wb') as f:
        f.write(image)

    print(f"created {output_path} ({len(image)} bytes)")

if __name__ == '__main__':
    import sys
    boot = sys.argv[1] if len(sys.argv) > 1 else 'boot.bin'
    out = sys.argv[2] if len(sys.argv) > 2 else 'ThornOS.iso'
    create_iso(boot, out)
