@echo off
qemu-system-x86_64 -cdrom "%~dp0ThornOS.iso" -m 16 -display sdl
