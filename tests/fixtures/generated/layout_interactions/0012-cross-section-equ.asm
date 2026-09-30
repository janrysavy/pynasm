cpu 8086
bits 16
org 256
length equ payload_end-payload
section .text
start:
 mov cx,length
 mov si,payload
 call finish
 jmp exit
finish: mov ax,0x1234
 ret
exit: ret
section .data align=8
payload: incbin "payload.bin",6,6
payload_end:
 dw length,start,finish,$-$$
section .bss
scratch: resb length
section .text
 dw scratch
