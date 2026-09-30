cpu 8086
bits 16
org 0
jmp target
n equ ending-target
times n db 0
target: times 16 db 60
ending:
 dw target,ending,n
