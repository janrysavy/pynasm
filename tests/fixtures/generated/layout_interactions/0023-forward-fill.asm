cpu 8086
bits 16
org 31744
jmp target
n equ ending-target
times n db 0
target: times 8 db 187
ending:
 dw target,ending,n
