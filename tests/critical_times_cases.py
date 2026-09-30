"""Deterministic first-pass TIMES corpus, independent of assembler tables."""


def programs():
    operators = ('+', '-', '*', '/', '//', '%', '%%', '&', '|', '^', '<<', '>>',
                 '==', '!=', '<', '<=', '>', '>=', '&&', '||', '^^', '<=>')
    expressions = ['f', 'a', 'g', 'f-f', 'f-g', 'f*0', '(0 ? f : 1)',
                   '(1 ? f : 0)', '(f-f)+1', '__?ilog2f?__(f)']
    for left, right in (('f', 'g'), ('f', 'f'), ('f', '2'), ('a', 'f'), ('a', 'a')):
        expressions.extend(f'({left} {operator} {right})' for operator in operators)
    expressions.extend([
        '+f', '-f', '~f', '!f', 'f*0+1', 'f-f+1', 'f*2-f-f+1', '(f+2)-(f+1)',
        '(f==f)', '(f==g)', '(f!=f)', '(f>=f)', '(f||0)-(g||0)+1',
        '(__?ilog2f?__(f)-__?ilog2f?__(g)+1)', '0 ? (f/0) : 1', '(f ? 1 : 1)',
        '(f-f ? 2 : 1)', '(f-f ? g : 1)', '((f*g)-(g*f)+1)',
    ])
    result = [f'cpu 8086\na equ f\ntimes ({expr}) db 7\nf equ 2\ng equ 3\n'
              for expr in expressions]
    result.extend([
        'cpu 8086\na: db 1\ntimes ((f+a)-(g+a)+1) db 7\nf equ 2\ng equ 2\n',
        'cpu 8086\na:db 1\ntimes ((f*a)-(f*a)+1) db 7\nf equ 0\n',
        'cpu 8086\ntimes (finish - start) db 7\nstart: db 1\nfinish: db 2\n',
        'cpu 8086\ncount equ end-start\ntimes count db 7\nstart: db 1\nend: db 2\n',
        'cpu 8086\ntimes f times 0 nop\nf equ 2\n',
        'cpu 8086\na equ f-f+1\ntimes a db 7\nf equ 2\n',
    ])
    return result
