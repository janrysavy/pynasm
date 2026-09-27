cpu 8086
dq 1|2==1
dq 1&2==0
dq 1^^0&&0
dq 1 ? 2 : 3 ? 4 : 5
dq 0 ? 2 : 3 ? 4 : 5
dq 1 ? 2 ? 7 : 8 : 9
dq -1 >> 1
dq -1 >>> 1
dq 0x100000000 / 2
dq 1 <=> 2
dq 2 <=> 2
dq 3 <=> 2
dq 1 <> 2
dq 1 = 1
dq 1 <<< 4
dq -1 >>> 4
dq 0 ? 7 : 8+2*3
dq 1 ? 7 : 8+2*3
dq 1 << -1
dq 1 >> -1
dq 1 <<< -1
dq 1 >>> -1
dq 1 << 64
dq -1 >> 64
dq -1 >>> 64
dq (0xffffffffffffffff+1) ? 1 : 2
dq !(0xffffffffffffffff+1)
dq (0xffffffffffffffff+1) && 1
dq (0xffffffffffffffff+1) || 1
dq (0x8000000000000000*2) ? 1 : 2
dq -3 < 0x7fffffffffffffff
dq 0 < 0x8000000000000000
dq 0x8000000000000000 > 1
dq 0x7fffffffffffffff < -1
%if (0xffffffffffffffff+1)
db 0xff
%else
db 0xa1
%endif
