cpu 8086
bits 16
org 0x100
label_0:
jz label_14
jnc label_12
nop
times 7 db 0
label_1:
jz label_14
jnc label_5
mov bx,[si+127]
times 1 db 0
label_2:
jz label_2
inc ax
times 7 db 0
label_3:
jnc label_2
jz label_4
jnc label_14
rep movsb
times 120 db 0
label_4:
jc label_3
jz label_10
jc label_13
inc ax
align 2, db 0x90
times 63 db 0
label_5:
jz label_2
jmp label_14
jc label_3
mov bx,[si+127]
align 4, db 0x90
times 128 db 0
label_6:
jz label_6
nop
times 129 db 0
label_7:
jc label_12
inc ax
times 125 db 0
label_8:
jmp label_11
mov bx,[si+127]
times 7 db 0
label_9:
jmp label_1
jnz label_1
jnc label_3
nop
times 63 db 0
label_10:
jnz label_14
jc label_6
jnc label_3
mov bx,[si+127]
times 0 db 0
label_11:
jc label_13
jnz label_0
jc label_0
nop
align 4, db 0x90
times 120 db 0
label_12:
jnc label_10
jmp label_3
jmp label_6
inc ax
times 126 db 0
label_13:
call label_8
jmp label_2
rep movsb
times 128 db 0
label_14:
call label_2
jnz label_12
jc label_10
mov bx,[si+127]
times 127 db 0
end_label: ret
