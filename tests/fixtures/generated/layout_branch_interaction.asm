cpu 8086
bits 16
org 0x100
label_0:
jz label_2
jmp label_1
call label_0
rep movsb
times 1 db 0
label_1:
jnc label_2
jc label_3
mov bx,[si+127]
times 120 db 0
label_2:
jmp label_3
nop
align 16, db 0x90
times 1 db 0
label_3:
call label_5
add byte [es:di],7
times 7 db 0
label_4:
call label_2
jc label_7
rep movsb
times 129 db 0
label_5:
jmp label_6
jz label_1
jnc label_2
nop
align 4, db 0x90
times 125 db 0
label_6:
call label_3
inc ax
times 7 db 0
label_7:
jc label_7
add byte [es:di],7
times 7 db 0
end_label: ret
