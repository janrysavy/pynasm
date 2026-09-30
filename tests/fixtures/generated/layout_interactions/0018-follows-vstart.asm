cpu 8086
bits 16
org 31744
section .text
start: mov ax,item
 call worker
 ret
section .data follows=.text align=16 vstart=0x2000
item: dw start,worker,$,$$
 incbin "payload.bin",3,3
section .extra follows=.data align=8
worker: mov bx,item
 ret
section .bss vfollows=.data
space: resb 3
space_end:
section .text
dw space,space_end,worker
