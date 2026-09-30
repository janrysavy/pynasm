cpu 8086
bits 16
org 0
absolute 1
record:
.kind: resb 1
alignb 4
.value: resw 1
.end:
section .text
start:
 mov bx,0x200
 mov al,[bx+record.kind]
 mov dx,[bx+record.value]
 dw record.end-record,record.value,record.end
 times 32-($-$$) db 0xa5
