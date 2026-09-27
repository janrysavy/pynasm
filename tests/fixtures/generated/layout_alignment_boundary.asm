cpu 8086
bits 16
org 0x100
label_0:
jmp label_12
jz label_8
jc label_0
add byte [es:di],7
align 8, db 0x90
times 120 db 0
label_1:
jc label_4
call label_0
jmp label_10
mov bx,[si+127]
times 1 db 0
label_2:
jnz label_12
jz label_10
inc ax
align 16, db 0x90
times 129 db 0
label_3:
call label_4
add byte [es:di],7
align 8, db 0x90
times 126 db 0
label_4:
jc label_10
inc ax
times 0 db 0
label_5:
call label_0
rep movsb
times 126 db 0
label_6:
jnc label_1
jnz label_10
add byte [es:di],7
times 0 db 0
label_7:
jmp label_5
mov bx,[si+127]
align 16, db 0x90
times 1 db 0
label_8:
call label_12
rep movsb
times 129 db 0
label_9:
call label_2
jz label_9
jmp label_1
inc ax
times 129 db 0
label_10:
jnc label_7
nop
times 129 db 0
label_11:
jz label_0
nop
times 1 db 0
label_12:
jz label_9
jnc label_13
nop
align 2, db 0x90
times 126 db 0
label_13:
jnc label_12
jmp label_3
jz label_12
add byte [es:di],7
times 129 db 0
end_label: ret
