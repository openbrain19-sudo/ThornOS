#!/usr/bin/env python3
"""Build ThornOS - writes boot sector directly."""
import struct
import os

def build():
    sector = bytearray(512)

    # FAT12 BPB (bytes 0-61)
    sector[0:3] = b'\xEB\x3C\x90'
    sector[3:11] = b'THORNOS '
    struct.pack_into('<H', sector, 11, 512)
    sector[13] = 1
    struct.pack_into('<H', sector, 14, 1)
    sector[16] = 2
    struct.pack_into('<H', sector, 17, 224)
    struct.pack_into('<H', sector, 19, 2880)
    sector[21] = 0xF0
    struct.pack_into('<H', sector, 22, 9)
    struct.pack_into('<H', sector, 24, 18)
    struct.pack_into('<H', sector, 26, 2)
    struct.pack_into('<I', sector, 28, 0)
    struct.pack_into('<I', sector, 32, 0)
    sector[36] = 0x80
    sector[38] = 0x29
    struct.pack_into('<I', sector, 39, 0x12345678)
    sector[43:54] = b'THORNOS    '
    sector[54:62] = b'FAT12   '

    # String at offset 0xBE
    string = b'Greetings, from ThornOS\n\x00'
    sector[0xBE:0xBE+len(string)] = string

    # Build code at offset 0x3E
    # All offsets are relative to 0x3E
    code = bytearray()

    # Clear screen: int 10h, AH=00h, AL=03h (80x25 text mode)
    code += b'\xB4\x00'              # mov ah, 0x00
    code += b'\xB0\x03'              # mov al, 0x03
    code += b'\xCD\x10'              # int 0x10

    code += b'\xBE\xBE\x7C'          # mov si, 0x7CBE

    loop_off = len(code)              # 3
    code += b'\xAC'                   # 3: lodsb
    code += b'\x84\xC0'              # 4: test al, al
    code += b'\x74\x08'              # 9: jz +8 -> hlt
    code += b'\xB4\x0E'              # 8: mov ah, 0x0E
    code += b'\x30\xFF'              # 10: xor bh, bh
    code += b'\xCD\x10'              # 12: int 0x10
    jmp_back = loop_off - len(code) - 2
    code += b'\xEB' + struct.pack('b', jmp_back)  # 14: jmp loop
    code += b'\xF4'                  # 16: hlt

    print(f"   code: {len(code)} bytes")

    sector[0x3E:0x3E+len(code)] = code

    sector[510] = 0x55
    sector[511] = 0xAA

    floppy = bytearray(1474560)
    floppy[:512] = sector

    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, '..', 'ThornOS.img')
    with open(img_path, 'wb') as f:
        f.write(floppy)
    print(f"   created {img_path}")

if __name__ == '__main__':
    print("building ThornOS...")
    build()
    print("done!")
