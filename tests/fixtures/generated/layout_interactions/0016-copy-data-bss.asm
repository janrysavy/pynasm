cpu 8086
bits 16
org 31744
section .text
start:
 mov si,payload
 mov di,buffer
 mov cx,payload_end-payload
 cld
 rep movsb
 call check
 jmp exit
check:
 mov bx,table
 mov ax,[bx]
 ret
exit: mov ax,0x4c00
 int 0x21
section .data align=16
table: dw start,payload,payload_end,buffer
payload: incbin "payload.bin",4,14
payload_end:
section .bss align=16
buffer: resb payload_end-payload
alignb 32
end_buffer: resw 2
section .data
dw end_buffer-buffer,$-$$
