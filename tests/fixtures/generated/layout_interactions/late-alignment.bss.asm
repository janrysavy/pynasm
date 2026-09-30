cpu 8086
bits 16
mov ax,item
section .bss align=16
item: resb 1
alignb 32
