cpu 8086
bits 16
section .a follows=.b
db 1
section .b follows=.a
db 2
