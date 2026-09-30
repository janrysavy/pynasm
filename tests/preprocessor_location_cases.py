"""Location-sensitive programs for an independently captured NASM 3.02 oracle."""
import itertools


def sources():
    for base, count in itertools.product((0, 1, 32, 256), (0, 1, 7)):
        yield f"absolute-{base}-{count}", (f"absolute {base}\nresb {count}\n"
            f"%if $ = {base + count}\nsection .text\ndb 1\n"
            "%else\nsection .text\ndb 2\n%endif\n"), {}
    for prefix in ("", "org 256\n", "section .data align=16\n"):
        for count in (0, 1, 7):
            yield f"difference-{prefix!r}-{count}", (prefix + f"times {count} db 0\n"
                f"%if $-$$ = {count}\ndb 1\n%else\ndb 2\n%endif\n"), {}
    for expression in ("$", "$$", "entry", "entry+1", "alias"):
        yield f"relocatable-{expression}", ("org 256\nentry: nop\nalias equ entry\n"
            f"%if {expression}\ndb 1\n%endif\n"), {}
    for expression in ("$-$$", "$-entry", "last-entry", "alias"):
        yield f"label-{expression}", ("entry: nop\nlast: nop\nalias equ last-entry\n"
            f"%assign n {expression}\ntimes n db 7\n"), {}
    yield "branch", "jmp end\n%if $-$$ = 2\ndb 1\n%else\ndb 2\n%endif\nend: nop\n", {}
    yield "rep", "%rep 4\n%assign n $-$$\ndb n\n%endrep\n", {}
    yield "macro", "%macro emit 0\n%assign n $-$$\ndb n\n%endmacro\nemit\nemit\nemit\n", {}
    yield "include", "db 9\n%include \"position.inc\"\n", {"position.inc": "%assign n $-$$\ndb n\n"}
    yield "absolute-label", "absolute 32\na: resw 3\n%assign n $-a\nsection .text\ndb n\n", {}
    yield "absolute-align", "absolute 33\nalignb 8\n%assign n $\nsection .text\ndb n\n", {}
    yield "absolute-origin", "absolute 32\nresb 3\n%assign n $$\nsection .text\ndb n\n", {}
    yield "section-switch", "db 1\nsection .data\ndb 2,3\nsection .text\n%assign n $-$$\ndb n\n", {}
    yield "bss", "section .bss\nresb 7\n%assign n $-$$\nsection .text\ndb n\n", {}
    yield "cross-section", "a: db 1\nsection .data\nb: db 2\n%if b-a\ndb 3\n%endif\n", {}
    yield "unknown", "%if missing\ndb 1\n%endif\n", {}
    yield "follows", "section foo follows=bar\ndb 1\nsection bar\ndb 2\n", {}
    yield "unknown-follows", "section foo follows=bar\ndb 1\n", {}
    yield "vfollows", "section .bss vfollows=.data\nf: resb 3\nsection .data\ndb 1\nsection .text\ndw f\n", {}
    yield "local-label", "entry: nop\n.last: nop\n%assign n .last-entry\ndb n\n", {}
    yield "alias", "%define loc $-$$\ndb 1\n%assign n loc\ndb n\n", {}
    yield "absolute-relocatable", "a: nop\nabsolute a\n%if $\nsection .text\ndb 1\n%endif\n", {}
    yield "absolute-relocatable-label", "a: nop\nabsolute a\nf: resb 1\n%if f\nsection .text\ndb 1\n%endif\n", {}
    yield "absolute-relative-distance", "a: nop\nabsolute a\nf: resb 3\n%assign n $-f\nsection .text\ndb n\n", {}
