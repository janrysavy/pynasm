cpu 8086
bits 16
org 256
jmp target
n equ ending-target
times n db 0
target: times 12 db 236
ending:
 dw target,ending,n
