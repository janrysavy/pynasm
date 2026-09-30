cpu 8086
bits 16
org 31744
section .text
start: jmp code
 dw value,ending
alignb 16
code:
 mov ax,[value]
 ret
section .data align=32
value: db 211
alignb 8
ending: dw code-start,$-$$
