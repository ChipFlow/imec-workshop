all: test.bin

test.elf: sections.lds start.s flashio.s main.c
	riscv64-unknown-elf-gcc -g -march=rv32i -mabi=ilp32 -Wl,--build-id=none,-Bstatic,-T,sections.lds,--strip-debug -static -ffreestanding -nostdlib -o test.elf start.s flashio.s main.c

test.bin: test.elf
	riscv64-unknown-elf-objcopy -O binary test.elf test.bin
