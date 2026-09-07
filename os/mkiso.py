#!/usr/bin/env python3
"""Create a minimal bootable ISO 9660 image with El Torito boot."""
import struct

def create_iso(boot_bin_path, output_path):
    with open(boot_bin_path, 'rb') as f:
        boot_data = f.read()

    assert len(boot_data) == 512, f"Boot sector must be 512 bytes, got {len(boot_data)}"

    SECTOR = 2048
    image = bytearray()

    # Sector 0-15: System Area (16 sectors, 32KB) - all zeros except El Torito
    image.extend(b'\x00' * (SECTOR * 16))

    # Sector 16: Boot Record Volume Descriptor
    brvd = bytearray(SECTOR)
    brvd[0] = 0x43  # 'C' = Boot Record
    brvd[1:6] = b'CD001'
    brvd[6] = 0x01  # version
    brvd[7:24] = b'EL TORITO SPECIFICATION'
    struct.pack_into('<I', brvd, 73, 18)  # boot catalog at LBA 18
    image.extend(brvd)

    # Sector 17: Unused (or could be another descriptor)
    image.extend(b'\x00' * SECTOR)

    # Sector 18: El Torito Boot Catalog
    catalog = bytearray(SECTOR)

    # Validation Entry (bytes 0-31)
    catalog[0] = 0x01    # Header ID
    catalog[1] = 0x00    # Platform: x86
    catalog[2:4] = b'\x00\x00'
    id_str = b'ThornOS Bootable ISO'
    catalog[4:4+len(id_str)] = id_str
    # Checksum: sum of all 16-bit words should be 0x55AA
    checksum = 0
    for i in range(0, 32, 2):
        checksum += struct.unpack_from('<H', catalog, i)[0]
    checksum = (0x10000 - (checksum - 0x55AA)) & 0xFFFF
    struct.pack_into('<H', catalog, 32, checksum)
    catalog[34] = 0x55
    catalog[35] = 0xAA

    # Initial/Default Entry (bytes 32-63)
    entry = bytearray(32)
    entry[0] = 0x88      # Bootable
    entry[1] = 0x00      # No emulation
    struct.pack_into('<H', entry, 2, 0x0000)  # Load segment
    entry[4] = 0x00      # System type
    entry[5] = 0x00
    struct.pack_into('<H', entry, 6, 1)       # Sector count (1 = 512 bytes)
    struct.pack_into('<I', entry, 8, 19)      # Boot LBA = sector 19
    catalog[32:64] = entry

    image.extend(catalog)

    # Sector 19: Boot Image (our bootloader, padded to 2048)
    boot_sector = bytearray(SECTOR)
    boot_sector[:len(boot_data)] = boot_data
    image.extend(boot_sector)

    # Pad to at least 1MB
    while len(image) < 1024 * 1024:
        image.extend(b'\x00' * SECTOR)

    with open(output_path, 'wb') as f:
        f.write(image)

    print(f"created {output_path} ({len(image)} bytes)")

if __name__ == '__main__':
    import sys
    boot = sys.argv[1] if len(sys.argv) > 1 else 'boot.bin'
    out = sys.argv[2] if len(sys.argv) > 2 else 'ThornOS.iso'
    create_iso(boot, out)
