cpu 8086
bits 16
org 31744
%include "layout.inc"
%macro block 1
 %%begin:
 mov cx,%1
 %%loop:
 inc ax
 loop %%loop
 jmp %%done
 times (%1 & 3) db FILL
 %%done:
 dw %%done-%%begin
%endmacro
start:
 block 7
 block 8
 times 64-($-$$) db FILL
align 16, db FILL
payload: incbin "payload.bin",7,9
.end:
 dw payload.end-payload,$-$$
