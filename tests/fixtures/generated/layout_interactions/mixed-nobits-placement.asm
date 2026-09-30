cpu 8086
bits 16
section .data
db 1
section .bss align=16 vstart=512
field: resb 1
section .text
dw field
