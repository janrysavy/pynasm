; Representative 8086 non-FPU rows from NASM 3.02 insns.dat, expanded with preinsns.pl
; Pinned NASM commit: 4a56d66ed9626d5a3ded5414c9d8b7f1a48ce065
cpu 8086
bits 16
nop ; row 47: NOP void
mov al,[0x1234] ; row 54: MOV reg_al,mem_offs
mov ax,[0x1234] ; row 55: MOV reg_ax,mem_offs
mov [0x1234],al ; row 58: MOV mem_offs,reg_al
mov [0x1234],ax ; row 59: MOV mem_offs,reg_ax
movabs al,[0x1234] ; row 62: MOVABS reg_al,mem_offs
movabs ax,[0x1234] ; row 63: MOVABS reg_ax,mem_offs
movabs [0x1234],al ; row 66: MOVABS mem_offs,reg_al
movabs [0x1234],ax ; row 67: MOVABS mem_offs,reg_ax
mov byte [bx+5],cl ; row 70: MOV rm8,reg8
mov word [bx+5],cx ; row 71: MOV rm16,reg16
mov cl,byte [bx+5] ; row 74: MOV reg8,rm8
mov cx,word [bx+5] ; row 75: MOV reg16,rm16
mov cl,7 ; row 80: MOV reg8,imm8
mov cx,0x1234 ; row 81: MOV reg16,imm16
mov cl,7 ; row 84: MOV reg8,imm8|abs
mov cx,0x1234 ; row 85: MOV reg16,imm16|abs
movabs cl,7 ; row 88: MOVABS reg8,imm8
movabs cx,0x1234 ; row 89: MOVABS reg16,imm16
mov byte [bx+5],7 ; row 92: MOV rm8,imm8
mov word [bx+5],0x1234 ; row 93: MOV rm16,imm16
lea cx,[bx+5] ; row 106: LEA reg16,mem
lea cx,0x1234 ; row 109: LEA reg16,imm16
add byte [bx+5],cl ; row 114: ADD rm8,reg8
add word [bx+5],cx ; row 115: ADD rm16,reg16
add cl,byte [bx+5] ; row 118: ADD reg8,rm8
add cx,word [bx+5] ; row 119: ADD reg16,rm16
add al,7 ; row 122: ADD reg_al,imm8
add byte [bx+5],7 ; row 123: ADD rm8,imm8
add word [bx+5],byte 1 ; row 124: ADD rm16,sbyteword16
add ax,0x1234 ; row 125: ADD reg_ax,imm16
add word [bx+5],0x1234 ; row 126: ADD rm16,imm16
or byte [bx+5],cl ; row 148: OR rm8,reg8
or word [bx+5],cx ; row 149: OR rm16,reg16
or cl,byte [bx+5] ; row 152: OR reg8,rm8
or cx,word [bx+5] ; row 153: OR reg16,rm16
or al,7 ; row 156: OR reg_al,imm8
or byte [bx+5],7 ; row 157: OR rm8,imm8
or word [bx+5],byte 1 ; row 158: OR rm16,sbyteword16
or ax,0x1234 ; row 159: OR reg_ax,imm16
or word [bx+5],0x1234 ; row 160: OR rm16,imm16
adc byte [bx+5],cl ; row 182: ADC rm8,reg8
adc word [bx+5],cx ; row 183: ADC rm16,reg16
adc cl,byte [bx+5] ; row 186: ADC reg8,rm8
adc cx,word [bx+5] ; row 187: ADC reg16,rm16
adc al,7 ; row 190: ADC reg_al,imm8
adc byte [bx+5],7 ; row 191: ADC rm8,imm8
adc word [bx+5],byte 1 ; row 192: ADC rm16,sbyteword16
adc ax,0x1234 ; row 193: ADC reg_ax,imm16
adc word [bx+5],0x1234 ; row 194: ADC rm16,imm16
sbb byte [bx+5],cl ; row 216: SBB rm8,reg8
sbb word [bx+5],cx ; row 217: SBB rm16,reg16
sbb cl,byte [bx+5] ; row 220: SBB reg8,rm8
sbb cx,word [bx+5] ; row 221: SBB reg16,rm16
sbb al,7 ; row 224: SBB reg_al,imm8
sbb byte [bx+5],7 ; row 225: SBB rm8,imm8
sbb word [bx+5],byte 1 ; row 226: SBB rm16,sbyteword16
sbb ax,0x1234 ; row 227: SBB reg_ax,imm16
sbb word [bx+5],0x1234 ; row 228: SBB rm16,imm16
and byte [bx+5],cl ; row 250: AND rm8,reg8
and word [bx+5],cx ; row 251: AND rm16,reg16
and cl,byte [bx+5] ; row 254: AND reg8,rm8
and cx,word [bx+5] ; row 255: AND reg16,rm16
and al,7 ; row 258: AND reg_al,imm8
and byte [bx+5],7 ; row 259: AND rm8,imm8
and word [bx+5],byte 1 ; row 260: AND rm16,sbyteword16
and ax,0x1234 ; row 261: AND reg_ax,imm16
and word [bx+5],0x1234 ; row 262: AND rm16,imm16
sub byte [bx+5],cl ; row 284: SUB rm8,reg8
sub word [bx+5],cx ; row 285: SUB rm16,reg16
sub cl,byte [bx+5] ; row 288: SUB reg8,rm8
sub cx,word [bx+5] ; row 289: SUB reg16,rm16
sub al,7 ; row 292: SUB reg_al,imm8
sub byte [bx+5],7 ; row 293: SUB rm8,imm8
sub word [bx+5],byte 1 ; row 294: SUB rm16,sbyteword16
sub ax,0x1234 ; row 295: SUB reg_ax,imm16
sub word [bx+5],0x1234 ; row 296: SUB rm16,imm16
xor byte [bx+5],cl ; row 318: XOR rm8,reg8
xor word [bx+5],cx ; row 319: XOR rm16,reg16
xor cl,byte [bx+5] ; row 322: XOR reg8,rm8
xor cx,word [bx+5] ; row 323: XOR reg16,rm16
xor al,7 ; row 326: XOR reg_al,imm8
xor byte [bx+5],7 ; row 327: XOR rm8,imm8
xor word [bx+5],byte 1 ; row 328: XOR rm16,sbyteword16
xor ax,0x1234 ; row 329: XOR reg_ax,imm16
xor word [bx+5],0x1234 ; row 330: XOR rm16,imm16
cmp byte [bx+5],cl ; row 352: CMP rm8,reg8
cmp word [bx+5],cx ; row 353: CMP rm16,reg16
cmp cl,byte [bx+5] ; row 356: CMP reg8,rm8
cmp cx,word [bx+5] ; row 357: CMP reg16,rm16
cmp al,7 ; row 360: CMP reg_al,imm8
cmp byte [bx+5],7 ; row 361: CMP rm8,imm8
cmp word [bx+5],byte 1 ; row 362: CMP rm16,sbyteword16
cmp ax,0x1234 ; row 363: CMP reg_ax,imm16
cmp word [bx+5],0x1234 ; row 364: CMP rm16,imm16
test byte [bx+5],cl ; row 373: TEST rm8,reg8
test word [bx+5],cx ; row 374: TEST rm16,reg16
test cl,byte [bx+5] ; row 377: TEST reg8,mem8
test cx,word [bx+5] ; row 378: TEST reg16,mem16
test al,7 ; row 381: TEST reg_al,imm8
test ax,0x1234 ; row 382: TEST reg_ax,imm16
test byte [bx+5],7 ; row 385: TEST rm8,imm8
test word [bx+5],0x1234 ; row 386: TEST rm16,imm16
rol byte [bx+5],1 ; row 391: ROL rm8,unity
rol word [bx+5],1 ; row 392: ROL rm16,unity
rol byte [bx+5],cl ; row 395: ROL rm8,reg_cl
rol word [bx+5],cl ; row 396: ROL rm16,reg_cl
rol byte [bx+5],cx ; row 399: ROL rm8,reg_cx
rol word [bx+5],cx ; row 400: ROL rm16,reg_cx
rol byte [bx+5],ecx ; row 403: ROL rm8,reg_ecx
rol word [bx+5],ecx ; row 404: ROL rm16,reg_ecx
rol byte [bx+5],rcx ; row 407: ROL rm8,reg_rcx
rol word [bx+5],rcx ; row 408: ROL rm16,reg_rcx
ror byte [bx+5],1 ; row 415: ROR rm8,unity
ror word [bx+5],1 ; row 416: ROR rm16,unity
ror byte [bx+5],cl ; row 419: ROR rm8,reg_cl
ror word [bx+5],cl ; row 420: ROR rm16,reg_cl
ror byte [bx+5],cx ; row 423: ROR rm8,reg_cx
ror word [bx+5],cx ; row 424: ROR rm16,reg_cx
ror byte [bx+5],ecx ; row 427: ROR rm8,reg_ecx
ror word [bx+5],ecx ; row 428: ROR rm16,reg_ecx
ror byte [bx+5],rcx ; row 431: ROR rm8,reg_rcx
ror word [bx+5],rcx ; row 432: ROR rm16,reg_rcx
rcl byte [bx+5],1 ; row 439: RCL rm8,unity
rcl word [bx+5],1 ; row 440: RCL rm16,unity
rcl byte [bx+5],cl ; row 443: RCL rm8,reg_cl
rcl word [bx+5],cl ; row 444: RCL rm16,reg_cl
rcl byte [bx+5],cx ; row 447: RCL rm8,reg_cx
rcl word [bx+5],cx ; row 448: RCL rm16,reg_cx
rcl byte [bx+5],ecx ; row 451: RCL rm8,reg_ecx
rcl word [bx+5],ecx ; row 452: RCL rm16,reg_ecx
rcl byte [bx+5],rcx ; row 455: RCL rm8,reg_rcx
rcl word [bx+5],rcx ; row 456: RCL rm16,reg_rcx
rcr byte [bx+5],1 ; row 463: RCR rm8,unity
rcr word [bx+5],1 ; row 464: RCR rm16,unity
rcr byte [bx+5],cl ; row 467: RCR rm8,reg_cl
rcr word [bx+5],cl ; row 468: RCR rm16,reg_cl
rcr byte [bx+5],cx ; row 471: RCR rm8,reg_cx
rcr word [bx+5],cx ; row 472: RCR rm16,reg_cx
rcr byte [bx+5],ecx ; row 475: RCR rm8,reg_ecx
rcr word [bx+5],ecx ; row 476: RCR rm16,reg_ecx
rcr byte [bx+5],rcx ; row 479: RCR rm8,reg_rcx
rcr word [bx+5],rcx ; row 480: RCR rm16,reg_rcx
shl byte [bx+5],1 ; row 487: SHL rm8,unity
shl word [bx+5],1 ; row 488: SHL rm16,unity
shl byte [bx+5],cl ; row 491: SHL rm8,reg_cl
shl word [bx+5],cl ; row 492: SHL rm16,reg_cl
shl byte [bx+5],cx ; row 495: SHL rm8,reg_cx
shl word [bx+5],cx ; row 496: SHL rm16,reg_cx
shl byte [bx+5],ecx ; row 499: SHL rm8,reg_ecx
shl word [bx+5],ecx ; row 500: SHL rm16,reg_ecx
shl byte [bx+5],rcx ; row 503: SHL rm8,reg_rcx
shl word [bx+5],rcx ; row 504: SHL rm16,reg_rcx
sal byte [bx+5],1 ; row 511: SAL rm8,unity
sal word [bx+5],1 ; row 512: SAL rm16,unity
sal byte [bx+5],cl ; row 515: SAL rm8,reg_cl
sal word [bx+5],cl ; row 516: SAL rm16,reg_cl
sal byte [bx+5],cx ; row 519: SAL rm8,reg_cx
sal word [bx+5],cx ; row 520: SAL rm16,reg_cx
sal byte [bx+5],ecx ; row 523: SAL rm8,reg_ecx
sal word [bx+5],ecx ; row 524: SAL rm16,reg_ecx
sal byte [bx+5],rcx ; row 527: SAL rm8,reg_rcx
sal word [bx+5],rcx ; row 528: SAL rm16,reg_rcx
shr byte [bx+5],1 ; row 535: SHR rm8,unity
shr word [bx+5],1 ; row 536: SHR rm16,unity
shr byte [bx+5],cl ; row 539: SHR rm8,reg_cl
shr word [bx+5],cl ; row 540: SHR rm16,reg_cl
shr byte [bx+5],cx ; row 543: SHR rm8,reg_cx
shr word [bx+5],cx ; row 544: SHR rm16,reg_cx
shr byte [bx+5],ecx ; row 547: SHR rm8,reg_ecx
shr word [bx+5],ecx ; row 548: SHR rm16,reg_ecx
shr byte [bx+5],rcx ; row 551: SHR rm8,reg_rcx
shr word [bx+5],rcx ; row 552: SHR rm16,reg_rcx
sar byte [bx+5],1 ; row 559: SAR rm8,unity
sar word [bx+5],1 ; row 560: SAR rm16,unity
sar byte [bx+5],cl ; row 563: SAR rm8,reg_cl
sar word [bx+5],cl ; row 564: SAR rm16,reg_cl
sar byte [bx+5],cx ; row 567: SAR rm8,reg_cx
sar word [bx+5],cx ; row 568: SAR rm16,reg_cx
sar byte [bx+5],ecx ; row 571: SAR rm8,reg_ecx
sar word [bx+5],ecx ; row 572: SAR rm16,reg_ecx
sar byte [bx+5],rcx ; row 575: SAR rm8,reg_rcx
sar word [bx+5],rcx ; row 576: SAR rm16,reg_rcx
inc cx ; row 925: INC reg16
inc byte [bx+5] ; row 927: INC rm8
inc word [bx+5] ; row 928: INC rm16
dec cx ; row 935: DEC reg16
dec byte [bx+5] ; row 937: DEC rm8
dec word [bx+5] ; row 938: DEC rm16
imul byte [bx+5] ; row 946: IMUL rm8
imul word [bx+5] ; row 947: IMUL rm16
mul byte [bx+5] ; row 973: MUL rm8
mul word [bx+5] ; row 974: MUL rm16
idiv byte [bx+5] ; row 1006: IDIV rm8
idiv word [bx+5] ; row 1007: IDIV rm16
div byte [bx+5] ; row 1014: DIV rm8
div word [bx+5] ; row 1015: DIV rm16
neg byte [bx+5] ; row 1023: NEG rm8
neg word [bx+5] ; row 1024: NEG rm16
not byte [bx+5] ; row 1031: NOT rm8
not word [bx+5] ; row 1032: NOT rm16
aaa ; row 1181: AAA void
aad ; row 1182: AAD void
aad 7 ; row 1183: AAD imm8
aam ; row 1184: AAM void
aam 7 ; row 1185: AAM imm8
aas ; row 1186: AAS void
daa ; row 1187: DAA void
das ; row 1188: DAS void
cbw ; row 1211: CBW void
cwd ; row 1215: CWD void
xchg ax,cx ; row 1274: XCHG reg_ax,reg16
xchg cx,ax ; row 1276: XCHG reg16,reg_ax
xchg cl,byte [bx+5] ; row 1282: XCHG reg8,rm8
xchg cx,word [bx+5] ; row 1283: XCHG reg16,rm16
xchg byte [bx+5],cl ; row 1286: XCHG rm8,reg8
xchg word [bx+5],cx ; row 1287: XCHG rm16,reg16
jmp short $+2 ; row 1303: JMP imm16|short
jmp dword short $+3 ; row 1304: JMP imm32|short
jmp near $+3 ; row 1306: JMP imm16|near
jmp dword near $+7 ; row 1307: JMP imm32|near
jmp near $+3 ; row 1310: JMP imm16|near
jmp dword near $+7 ; row 1311: JMP imm32|near
jmp word [bx+5] ; row 1314: JMP rm16|near
jmp far 0x1234:0x5678 ; row 1318: JMP imm16|far
jmp 0x1234:0x5678 ; row 1321: JMP imm16:imm16
jmp far 0x1234:0x5678 ; row 1323: JMP imm16:imm16|far
jmp 0x1234:0x5678 ; row 1326: JMP imm16:imm16
jmp far 0x1234:0x5678 ; row 1328: JMP imm16:imm16|far
jmp far [bx+5] ; row 1332: JMP mem16|far
jmp word [bx+5] ; row 1337: JMP rm16
jz short $+2 ; row 1341: Jcc imm16|short
jz dword short $+3 ; row 1342: Jcc imm32|short
jz near $+3 ; row 1344: Jcc imm16|near
jz dword near $+7 ; row 1345: Jcc imm32|near
jz 0x1234 ; row 1354: Jcc imm
jcxz short $+2 ; row 1358: JCXZ imm16|near|short
jcxz dword short $+3 ; row 1360: JCXZ imm32|near|short
jcxz short $+2,cx ; row 1364: JCXZ imm16|near|short,reg_cx
jcxz dword short $+3,cx ; row 1366: JCXZ imm32|near|short,reg_cx
loop short $+2 ; row 1371: LOOP imm16|near|short
loopw short $+2 ; row 1372: LOOPW imm16|near|short
loop dword short $+3 ; row 1374: LOOP imm32|near|short
loopw dword short $+3 ; row 1375: LOOPW imm32|near|short
loope short $+2 ; row 1380: LOOPE imm16|near|short
loopew short $+2 ; row 1381: LOOPEW imm16|near|short
loope dword short $+3 ; row 1383: LOOPE imm32|near|short
loopew dword short $+3 ; row 1384: LOOPEW imm32|near|short
loopne short $+2 ; row 1389: LOOPNE imm16|near|short
loopnew short $+2 ; row 1390: LOOPNEW imm16|near|short
loopne dword short $+3 ; row 1392: LOOPNE imm32|near|short
loopnew dword short $+3 ; row 1393: LOOPNEW imm32|near|short
loopz short $+2 ; row 1398: LOOPZ imm16|near|short
loopzw short $+2 ; row 1399: LOOPZW imm16|near|short
loopz dword short $+3 ; row 1401: LOOPZ imm32|near|short
loopzw dword short $+3 ; row 1402: LOOPZW imm32|near|short
loopnz short $+2 ; row 1407: LOOPNZ imm16|near|short
loopnzw short $+2 ; row 1408: LOOPNZW imm16|near|short
loopnz dword short $+3 ; row 1410: LOOPNZ imm32|near|short
loopnzw dword short $+3 ; row 1411: LOOPNZW imm32|near|short
loop short $+2,cx ; row 1416: LOOP imm16|near|short,reg_cx
loop dword short $+3,cx ; row 1418: LOOP imm32|near|short,reg_cx
loope short $+2,cx ; row 1422: LOOPE imm16|near|short,reg_cx
loope dword short $+3,cx ; row 1424: LOOPE imm32|near|short,reg_cx
loopne short $+2,cx ; row 1428: LOOPNE imm16|near|short,reg_cx
loopne dword short $+3,cx ; row 1430: LOOPNE imm32|near|short,reg_cx
loopz short $+2,cx ; row 1434: LOOPZ imm16|near|short,reg_cx
loopz dword short $+3,cx ; row 1436: LOOPZ imm32|near|short,reg_cx
loopnz short $+2,cx ; row 1440: LOOPNZ imm16|near|short,reg_cx
loopnz dword short $+3,cx ; row 1442: LOOPNZ imm32|near|short,reg_cx
call near $+3 ; row 1467: CALL imm16|near
call dword near $+7 ; row 1468: CALL imm32|near
call word [bx+5] ; row 1471: CALL rm16|near
call far 0x1234:0x5678 ; row 1475: CALL imm16|far
call 0x1234:0x5678 ; row 1478: CALL imm16:imm16
call far 0x1234:0x5678 ; row 1480: CALL imm16:imm16|far
call 0x1234:0x5678 ; row 1483: CALL imm16:imm16
call far 0x1234:0x5678 ; row 1485: CALL imm16:imm16|far
call far [bx+5] ; row 1489: CALL mem16|far
call word [bx+5] ; row 1494: CALL rm16
ret ; row 1498: RET void
retw ; row 1499: RETW void
ret 0x1234 ; row 1502: RET imm16
retw 0x1234 ; row 1503: RETW imm16
retf ; row 1506: RETF void
retfw ; row 1507: RETFW void
retf 0x1234 ; row 1510: RETF imm16
retfw 0x1234 ; row 1511: RETFW imm16
retn ; row 1514: RETN void
retnw ; row 1515: RETNW void
retn 0x1234 ; row 1518: RETN imm16
retnw 0x1234 ; row 1519: RETNW imm16
int 7 ; row 1524: INT imm8
int3 ; row 1528: INT3 void
int03 ; row 1529: INT03 void
brkpt ; row 1530: BRKPT void
into ; row 1531: INTO void
iret ; row 1539: IRET void
iretw ; row 1540: IRETW void
clc ; row 1548: CLC void
cld ; row 1549: CLD void
cli ; row 1550: CLI void
stc ; row 1553: STC void
std ; row 1554: STD void
sti ; row 1555: STI void
cmc ; row 1558: CMC void
lahf ; row 1560: LAHF void
sahf ; row 1561: SAHF void
salc ; row 1562: SALC void
pushf ; row 1564: PUSHF void
pushfw ; row 1565: PUSHFW void
popf ; row 1568: POPF void
popfw ; row 1569: POPFW void
cmpsb ; row 1574: CMPSB void
cmpsw ; row 1575: CMPSW void
lodsb ; row 1578: LODSB void
lodsw ; row 1579: LODSW void
movsb ; row 1582: MOVSB void
movsw ; row 1583: MOVSW void
stosb ; row 1586: STOSB void
stosw ; row 1587: STOSW void
scasb ; row 1590: SCASB void
scasw ; row 1591: SCASW void
hlt ; row 1715: HLT void
pause ; row 1717: PAUSE void
in al,7 ; row 1748: IN reg_al,imm8
in ax,7 ; row 1749: IN reg_ax,imm8
in al,dx ; row 1751: IN reg_al,reg_dx
in ax,dx ; row 1752: IN reg_ax,reg_dx
out 7,al ; row 1754: OUT imm8,reg_al
out 7,ax ; row 1755: OUT imm8,reg_ax
out dx,al ; row 1757: OUT reg_dx,reg_al
out dx,ax ; row 1758: OUT reg_dx,reg_ax
mov word [bx+5],ds ; row 1762: MOV mem16,reg_sreg
mov cx,ds ; row 1763: MOV reg16,reg_sreg
mov ds,word [bx+5] ; row 1766: MOV reg_sreg,mem16
mov ds,cx ; row 1767: MOV reg_sreg,reg16
lds cx,word [bx+5] ; row 1771: LDS reg16,mem16
les cx,word [bx+5] ; row 1773: LES reg16,mem16
push es ; row 1785: PUSH reg_es
push cs ; row 1786: PUSH reg_cs
push ss ; row 1787: PUSH reg_ss
push ds ; row 1788: PUSH reg_ds
pop es ; row 1792: POP reg_es
pop cs ; row 1793: POP reg_cs
pop ss ; row 1794: POP reg_ss
pop ds ; row 1795: POP reg_ds
push cx ; row 2173: PUSH reg16
push word [bx+5] ; row 2176: PUSH rm16
pop cx ; row 2187: POP reg16
pop word [bx+5] ; row 2190: POP rm16
fwait ; row 2273: FWAIT void
xlatb ; row 2275: XLATB void
xlat ; row 2276: XLAT void
