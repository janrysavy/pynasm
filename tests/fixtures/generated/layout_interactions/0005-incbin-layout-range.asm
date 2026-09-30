cpu 8086
bits 16
org 0
start:
 mov ax,0x1234
 jmp next
 times 24-($-$$) db 0
next:
 incbin "payload.bin",3+($-$$)-24,24+4-($-$$)
.tail:
 dw next-start,next.tail-next
 times 64-($-$$) db 0
 dw 0xaa55
