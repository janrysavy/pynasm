cpu 8086
bits 16
mov ax,item
section .data align=16
item: db 1
align 32,db 0
