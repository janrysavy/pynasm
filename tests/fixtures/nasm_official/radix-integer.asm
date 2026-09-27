	;;  Integer constants...

	dd 1010_0101		; Decimal
	dd 01010_0101		; Decimal (*not* octal!)
	dd 0d1010_0101		; Decimal
	dd 0t1010_0101		; Decimal
	dd 1010_0101d		; Decimal
	dd 1010_0101t		; Decimal

	dd 0b1010_0101		; Binary
	dd 0y1010_0101		; Binary
	dd 1010_0101b		; Binary
	dd 1010_0101y		; Binary

	dd 0o1010_0101		; Octal
	dd 0q1010_0101		; Octal
	dd 1010_0101o		; Octal
	dd 1010_0101q		; Octal

	dd 0h1010_0101		; Hex
	dd 0x1010_0101		; Hex
	dd 1010_0101h		; Hex
	dd 1010_0101x		; Hex
	dd $1010_0101		; Hex

	db 0h			; Zero!
	db 0x			; Zero!
	db 0b			; Zero!
	db 0dh			; Hex
	db 0bh			; Hex
	db 0dx			; Hex
	db 0bx			; Hex
	db 0hd			; Hex
	db 0hb			; Hex
	db 0xd			; Hex
	db 0xb			; Hex
