"""Small source cases for independently captured NASM 3.02 expression outcomes."""

LEVELS = (0, 1, 9)


def cases():
    for op in ('/', '//', '%', '%%'):
        for divisor in ('2', '3', '-2', '0', '18446744073709551616'):
            yield 'forward', f'answer equ 8{op}divisor\ndivisor equ {divisor}\ndb answer\n'
        for form in ('db answer', 'mov ax,answer', 'mov ax,[bx+answer]',
                     'je answer', 'resb answer'):
            yield 'forward', f'{form}\nanswer equ 8{op}divisor\ndivisor equ 2\n'
        yield 'forward', f'factor equ target-target+2\nanswer equ 8{op}factor\ndb answer\ntarget:nop\n'
        yield 'forward', f'answer equ 8{op}missing\ndb answer\n'
        yield 'forward', f'answer equ missing{op}0\ndb answer\n'
    binary = ('/', '//', '%', '%%', '<<', '<<<', '>>', '>>>', '&', '|', '^', '&&', '||', '^^')
    expressions = [f'target{op}1' for op in binary]
    expressions += [f'1{op}target' for op in binary]
    expressions += ['~target', '!target']
    expressions += [f'(target-target+8){op}1' for op in binary]
    expressions += ['~(target-target)', '!(target-target)', 'target==target',
                    'target<target', 'target!=target', 'target-target+1']
    for expr in expressions:
        for form in ('db {}', 'mov ax,[bx+({})]', 'je {}'):
            yield 'scalar', 'org 256\ntarget:nop\n' + form.format(expr) + '\n'
    for expr in ('(b-a)/2', '~(b-a)', '(a-a)/2', '(b-b)/2'):
        yield 'scalar', f'section one\na:nop\nsection two\nb:nop\ndb {expr}\n'
    # Final report's proposed rejections are wrong for our NASM 3.02 profile.
    for source in ("db 'a:b'\n", 'jmp word target\nnop\ntarget:\n',
                   'je near target\ntarget:\n', 'loop word target\ntarget:\n'):
        yield 'report-control', source
