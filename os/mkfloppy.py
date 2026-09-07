#!/usr/bin/env python3
"""Create a 1.44MB floppy disk image with boot sector."""
import struct

def create_floppy(boot_bin_path, output_path):
    with open(boot_bin_path, 'rb') as f:
        boot_data = f.read()

    TRACKS = 80
    HEADS = 2
    SECTORS_PER_TRACK = 18
    SECTOR_SIZE = 512
    TOTAL_SIZE = TRACKS * HEADS * SECTORS_PER_TRACK * SECTOR_SIZE

    floppy = bytearray(TOTAL_SIZE)

    # Build boot sector:
    # FAT12 BPB goes at bytes 0-61, then our code at offset 0x3E (62)
    # We put a jump at byte 0 to skip the BPB

    # Jump instruction: jmp 0x3E (skip BPB), nop
    floppy[0] = 0xEB  # jmp short
    floppy[1] = 0x3C  # offset (0x3E - 2 = 0x3C)
    floppy[2] = 0x90  # nop

    # OEM name
    floppy[3:11] = b'THORNOS '

    # BPB
    struct.pack_into('<H', floppy, 11, 512)    # bytes per sector
    floppy[13] = 1                              # sectors per cluster
    struct.pack_into('<H', floppy, 14, 1)       # reserved sectors
    floppy[16] = 2                              # number of FATs
    struct.pack_into('<H', floppy, 17, 224)     # root directory entries
    struct.pack_into('<H', floppy, 19, 2880)    # total sectors
    floppy[21] = 0xF0                           # media type
    struct.pack_into('<H', floppy, 22, 9)       # sectors per FAT
    struct.pack_into('<H', floppy, 24, 18)      # sectors per track
    struct.pack_into('<H', floppy, 26, 2)       # number of heads
    struct.pack_into('<I', floppy, 28, 0)       # hidden sectors
    struct.pack_into('<I', floppy, 32, 0)       # large sector count

    # Extended Boot Record
    floppy[36] = 0x80                           # drive number
    floppy[37] = 0x00                           # reserved
    floppy[38] = 0x29                           # extended boot sig
    struct.pack_into('<I', floppy, 39, 0x12345678)
    floppy[43:54] = b'THORNOS    '
    floppy[54:62] = b'FAT12   '

    # Our bootloader code goes at offset 0x3E (62)
    floppy[0x3E:0x3E+len(boot_data)] = boot_data

    # Boot signature
    floppy[510] = 0x55
    floppy[511] = 0xAA

    with open(output_path, 'wb') as f:
        f.write(floppy)

    print(f"created {output_path} ({len(floppy)} bytes)")

if __name__ == '__main__':
    import sys
    boot = sys.argv[1] if len(sys.argv) > 1 else 'boot.bin'
    out = sys.argv[2] if len(sys.argv) > 2 else 'ThornOS.img'
    create_floppy(boot, out)
