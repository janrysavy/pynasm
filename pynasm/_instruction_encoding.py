"""Operand parsing, instruction encoding, and data emission."""

from __future__ import annotations

from ._assembler_syntax import *
from ._layout import combine_layout, scale_layout
from .expression import _bases


class InstructionEncodingMixin:
    def _operand(self, text: str, forced_address_width: int | None = None) -> Operand:
        text = text.strip()
        masm_ptr = "__?masm_ptr?__" in text.lower()
        if masm_ptr:
            marker = re.match(
                r"(?i)^((?:(?:strict|byte|word|dword|qword|tword|short|near|far|abs)\s+)*)"
                r"__\?masm_ptr\?__(?=\s|$)\s*(.*)$", text)
            self._require(marker is not None, "invalid PTR placement")
            remainder = marker.group(2)
            text = marker.group(1) + (remainder if remainder.startswith("[") else f"[{remainder}]")
        width = None
        qualifier = None
        distance_flags: set[str] = set()
        strict = False
        while True:
            match = re.match(r"(?i)^(strict|byte|word|dword|qword|tword|short|near|far|abs)\b\s*", text)
            if not match: break
            word = match.group(1).lower()
            if word == "abs" and self.compatibility != "nasm3":
                raise self._error("ABS operand qualifier is unsupported in this profile")
            text = text[match.end():].strip()
            if word == "strict": strict = True
            elif word in ("byte", "word", "dword", "qword", "tword"):
                if width is None:
                    width = {"byte": 8, "word": 16, "dword": 32,
                             "qword": 64, "tword": 80}[word]
            else:
                distance_flags.add(word)
                qualifier = next((distance for distance in ("short", "near", "far", "abs")
                                  if distance in distance_flags), None)
        if not text: raise self._error("missing operand")
        lower = text.lower()
        if not masm_ptr and lower in REG8:
            if width and width != 8: raise self._error("register size conflict")
            return Operand("reg", 8, REG8[lower], qualifier=qualifier, strict=strict,
                           distance_flags=frozenset(distance_flags))
        if not masm_ptr and lower in REG16:
            if width and width != 16: raise self._error("register size conflict")
            return Operand("reg", 16, REG16[lower], qualifier=qualifier, strict=strict,
                           distance_flags=frozenset(distance_flags))
        if not masm_ptr and lower in ("ecx", "rcx"):
            register_width = 32 if lower == "ecx" else 64
            if width and width != register_width:
                raise self._error("register size conflict")
            return Operand("shift_count", register_width, 1,
                           qualifier=qualifier, strict=strict,
                           distance_flags=frozenset(distance_flags))
        if not masm_ptr and lower in SEGREG:
            return Operand("seg", 16, SEGREG[lower], qualifier=qualifier, strict=strict,
                           distance_flags=frozenset(distance_flags))
        segment = None
        match = re.match(r"(?i)^(es|cs|ss|ds)\s*:\s*(.*)$", text)
        if match:
            segment, text = match.group(1).lower(), match.group(2)
            if not text.startswith("["):
                self._require(self.compatibility == "nasm3")
                inner_width = re.match(r"(?i)^(byte|word|dword|qword|tword)\b\s*(.*)$", text)
                if inner_width:
                    specified = {"byte": 8, "word": 16, "dword": 32,
                                 "qword": 64, "tword": 80}[inner_width.group(1).lower()]
                    if width is not None and width != specified:
                        raise self._error("operand sizes do not match")
                    width = specified
                    text = inner_width.group(2)
        leading_address = None
        if not text.startswith("["):
            displaced = re.fullmatch(r"(.+?)\s*\[([^\[\]]+)\]", text)
            if displaced and "[" not in displaced.group(1) and "]" not in displaced.group(1):
                leading_address = displaced.group(1).strip()
                text = f"[{displaced.group(2)}]"
            elif segment or masm_ptr:
                text = f"[{text}]"
        if text.startswith("[") and text.endswith("]"):
            inner = text[1:-1].strip()
            displacement_width = None
            address_width = forced_address_width
            word_displacement = False
            while True:
                seg_match = re.match(r"(?i)^(es|cs|ss|ds)\s*:\s*(.*)$", inner)
                if seg_match:
                    self._require(segment is None, "conflicting segment overrides")
                    segment, inner = seg_match.group(1).lower(), seg_match.group(2).strip()
                    continue
                address_hint = re.match(r"(?i)^(a16|a32|abs|rel|nosplit)\b\s*(.*)$", inner)
                if address_hint:
                    hint = address_hint.group(1).lower()
                    if hint in ("a16", "a32"):
                        selected_width = 16 if hint == "a16" else 32
                        self._require(address_width in (None, selected_width),
                                      "conflicting address size specifications")
                        address_width = selected_width
                    inner = address_hint.group(2).strip()
                    continue
                address_size = re.match(r"(?i)^(byte|word|dword|qword)\b\s*(.*)$", inner)
                if not address_size:
                    break
                displacement_width = {"byte": 8, "word": 16,
                                      "dword": 32, "qword": 64}[address_size.group(1).lower()]
                word_displacement |= displacement_width != 8
                inner = address_size.group(2).strip()
            direct_byte_form = displacement_width == 8
            if word_displacement and displacement_width == 8:
                displacement_width = 16
            try:
                location = Value(self._line_address, relocation=1,
                                 layout=() if self._section is None else
                                 ((self._section.name, self._line_index, 1),))
                expr, coefficients = evaluate_address(
                    f"({leading_address})+({inner})" if leading_address else inner,
                    self._lookup, location, self._integer_function,
                    strict_scalars=self.compatibility == 'nasm3')
            except ExpressionError as exc:
                raise self._error(str(exc)) from exc
            self._require(all(coefficient == 1 for coefficient in coefficients.values()),
                          "invalid 8086 effective address")
            bases = list(coefficients)
            selection_displacement = None
            if self.compatibility == "nasm3" and expr.relocation == -1 and not expr.unresolved:
                section_terms: dict[str, int] = {}
                for name, _, coefficient in expr.layout or ():
                    section_terms[name] = section_terms.get(name, 0) + coefficient
                section_terms = {name: coefficient for name, coefficient in section_terms.items()
                                 if coefficient}
                self._require(self._section is not None and
                              section_terms == {self._section.name: -1},
                              "invalid effective address: impossible segment base multiplier")
                if bases:
                    # NASM parser.c marks a negative current-section base as
                    # self-relative. memory_mod() and disp8 use its section
                    # offset, while a word displacement goes through flat
                    # relocation. Preserve that distinction, including zero
                    # displacement and explicit BYTE/WORD, only in nasm3.
                    selection_displacement = expr.number + self._section.base
            self._require(displacement_width in (None, 8, 16) or
                          (displacement_width == 32 and not bases),
                          "invalid 8086 displacement size")
            self._require(address_width is None or displacement_width in (None, 8, address_width),
                          "conflicting address and displacement sizes")
            self._require(address_width != 32 or not bases,
                          "invalid 8086 effective address")
            return Operand("mem", width, expr=expr, segment=segment, base=tuple(bases),
                           qualifier=qualifier, strict=strict,
                           distance_flags=frozenset(distance_flags),
                           displacement_width=displacement_width,
                           direct_byte_form=direct_byte_form,
                           address_width=address_width,
                           selection_displacement=selection_displacement)
        if segment: raise self._error("segment override requires memory operand")
        if ":" in text:
            far = _split(text, ":")
            if len(far) == 2:
                return Operand("far", width, expr=self._eval(far[1]),
                               far_segment=self._eval(far[0]), qualifier=qualifier,
                               strict=strict, distance_flags=frozenset(distance_flags))
        return Operand("imm", width, expr=self._eval(text), qualifier=qualifier,
                       strict=strict, distance_flags=frozenset(distance_flags))

    def _prefix(self, *ops: Operand) -> bytes:
        segments = {o.segment for o in ops if o.segment}
        if len(segments) > 1: raise self._error("conflicting segment overrides")
        segment_prefix = bytes((SEG_PREFIX[next(iter(segments))],)) if segments else b""
        address_prefix = b"\x67" if any(o.address_width == 32 or o.displacement_width == 32
                                        for o in ops) else b""
        return segment_prefix + address_prefix

    def _rm(self, opcode: int, field: int, operand: Operand, width: int) -> bytes:
        site = (self._line.filename, self._line.number)
        if self._pass == 0 and self.optimize <= 1 and operand.kind == "mem" and operand.expr.unresolved:
            self._wide_displacements.add(site)
        conservative = (self.optimize <= 1 and site in self._wide_displacements and
                        (self.compatibility != "nasm3" or operand.expr.unresolved or
                         (operand.expr.relocation != 0 and
                          operand.selection_displacement is None)))
        return self._prefix(operand) + bytes((opcode,)) + _modrm(field, operand, width, conservative)

    def _require(self, condition: bool, message: str = "invalid operand combination") -> None:
        if not condition: raise self._error(message)

    def _forward_short_delta(self, delta: int, target: Value, short_size: int,
                             prefix_size: int) -> int:
        """Predict movement of an affine target when this branch shrinks.

        Numeric address equality cannot identify a target's defining label.
        Follow source-position dependencies instead, including EQU aliases and
        addends. ALIGN may absorb the saving before a dependent label is reached.
        """
        saving = max(0, self._old_size - prefix_size - short_size)
        if (not saving or self._pass == 0 or self._in_times or not target.forward or
                not target.layout or
                self._line_index >= len(self._previous_line_positions)):
            return delta
        section = self._section.name
        if (self._previous_line_positions[self._line_index][1] != section or
                any(name != section for name, _, _ in target.layout)):
            return delta
        dependencies = {line: coefficient for _, line, coefficient in target.layout
                        if line > self._line_index}
        if not dependencies:
            return delta
        last = max(dependencies)
        if last >= len(self._previous_line_positions):
            return delta
        movement = 0
        position_savings = {}
        for index in range(self._line_index + 1, last + 1):
            position_savings[index] = saving
            # Labels bind to the start of their line, before its own ALIGN.
            movement += dependencies.get(index, 0) * saving
            if index == last:
                break
            _, line_section = self._previous_line_positions[index]
            if line_section != section:
                continue
            if (index >= len(self._older_line_sizes) or
                    self._previous_line_sizes[index] != self._older_line_sizes[index]):
                self._deferred_branch_relax = True
                return delta
            size_layout = self._previous_line_size_layouts.get(index, ())
            if size_layout is None:
                return delta  # No affine prediction for this directive's size.
            size_saving = 0
            for name, position, coefficient in size_layout:
                if name != section or position > index:
                    return delta  # Depends on a position not yet simulated.
                size_saving += coefficient * position_savings.get(position, 0)
            if self._previous_line_sizes[index] - size_saving < 0:
                return delta
            saving += size_saving
            alignment = self._previous_line_alignments.get(index)
            if alignment is not None:
                old_padding = self._previous_line_sizes[index]
                new_padding = (old_padding + saving) % alignment
                saving += old_padding - new_padding
        return delta - movement

    def _encode(self, mnemonic: str, ops: list[Operand], prefix_size: int = 0,
                repne_prefix: bool = False,
                forced_operand_width: int | None = None) -> bytes:
        count = len(ops)
        if mnemonic not in ("jmp", "call"):
            self._require(all(op.kind == "mem" or "far" not in op.distance_flags for op in ops))
        self._require(all(op.width in (None, 8, 16) or
                          (mnemonic == "lea" and op.kind == "mem") or
                          (mnemonic in SHIFT and op.kind == "shift_count") or
                          (self.compatibility == "nasm3" and
                           (mnemonic in JCC or mnemonic in ("jmp", "call")) and
                           op.kind == "imm" and op.width == 32)
                          for op in ops),
                      "invalid operand sizes")
        if mnemonic in MODERN_ONLY_MNEMONICS:
            self._require(self.compatibility == "nasm3")
        if mnemonic in FIXED:
            self._require(count == 0)
            opcode = FIXED[mnemonic]
            return opcode if isinstance(opcode, bytes) else bytes((opcode,))
        if mnemonic in PREFIX:
            self._require(count == 0)
            return bytes((PREFIX[mnemonic],))
        if mnemonic in ADDRESS_PREFIX:
            self._require(self.compatibility == "nasm3" and count == 0)
            return b"\x67" if mnemonic == "a32" else b""
        if mnemonic in OPERAND_PREFIX:
            self._require(self.compatibility == "nasm3" and count == 0)
            return b"\x66" if mnemonic == "o32" else b""
        if mnemonic in ("aam", "aad"):
            self._require(count <= 1 and (not ops or
                          (ops[0].kind == "imm" and ops[0].width != 16 and
                           "far" not in ops[0].distance_flags)))
            return bytes((0xD4 if mnemonic == "aam" else 0xD5,
                          (ops[0].expr.number if ops else 10) & 0xFF))
        if mnemonic == "bswap":
            self._require(self.compatibility == "nasm3" and self.optimize > 1 and
                          count == 1 and ops[0].kind == "reg" and ops[0].width == 16 and
                          ops[0].reg in (0, 1, 2, 3))
            return bytes((0x86, 0xC4 + 9 * ops[0].reg))
        if mnemonic in ("movsx", "movsxb"):
            self._require(self.compatibility == "nasm3" and self.optimize > 1 and
                          count == 2 and ops[0].kind == "reg" and ops[0].width == 16 and
                          ops[0].reg == 0 and ops[1].kind == "reg" and ops[1].width == 8 and
                          ops[1].reg == 0)
            return b"\x98"
        if mnemonic == "int":
            self._require(count == 1 and ops[0].kind == "imm" and
                          ops[0].width != 16 and "far" not in ops[0].distance_flags)
            return b"\xCD" + _word(ops[0].expr.number, 1)
        if mnemonic in ("ret", "retw", "retn", "retnw", "retf", "retfw"):
            self._require(count <= 1 and (not ops or
                          (ops[0].kind == "imm" and ops[0].width != 8 and
                           "far" not in ops[0].distance_flags)))
            far = mnemonic in ("retf", "retfw")
            return (bytes((0xCA if far else 0xC2,)) + _word(ops[0].expr.number, 2)) if ops else bytes((0xCB if far else 0xC3,))
        if mnemonic in JCC:
            loop_base = mnemonic in ("jcxz", "loop", "loope", "loopne", "loopz", "loopnz")
            loop_family = JCC[mnemonic] >= 0xE0
            self._require(count in (1, 2) and ops[0].kind == "imm" and
                          (count == 1 or (self.compatibility == "nasm3" and loop_base and ops[1].kind == "reg" and
                           ops[1].width == 16 and ops[1].reg == 1)))
            op = ops[0]
            if op.qualifier is None and op.width == 8:
                op.qualifier = "short"
            self._require("far" not in op.distance_flags and
                          (op.qualifier != "near" or self.compatibility == "nasm3"))
            long_target = op.width == 32
            branch_prefix = b"\x66" if long_target and forced_operand_width is None else b""
            short_size = 2 + len(branch_prefix)
            instruction_address = self._address + prefix_size
            delta = op.expr.number - (instruction_address + short_size)
            if op.expr.symbolic and op.expr.number > self._address:
                delta = self._forward_short_delta(delta, op.expr,
                                                  short_size, prefix_size)
            conditional = 0x70 <= JCC[mnemonic] <= 0x7F
            cross_section = op.expr.section is not None and op.expr.section != self._section.name
            # A scalar EQU still has a name. It is an absolute target, not a
            # same-section label; default 8086 Jcc uses NASM's near expansion.
            modern_absolute = self.compatibility == "nasm3" and op.expr.relocation == 0
            site = (self._line.filename, self._line.number)
            if self.compatibility == "nasm3" and self.optimize == 1 and conditional and op.qualifier != "short":
                self._wide_jcc.add(site)
            # An EQU defined earlier in this pass can still be unresolved.
            # Start it wide; unlike a direct forward label it cannot use the
            # current instruction's forward-reference relaxation prediction.
            unresolved_equ = (self.compatibility == "nasm3" and op.expr.unresolved and
                              not op.expr.forward and op.qualifier != "short")
            if (conditional and (unresolved_equ or repne_prefix or (op.strict and op.qualifier != "short") or
                    (not op.expr.unresolved and op.qualifier != "short" and
                     (op.qualifier == "near" or cross_section or site in self._wide_jcc or
                      modern_absolute or (not _signed8(delta) and
                                          (op.expr.symbolic or self.compatibility == "nasm3")))))):
                wide_size = 7 if long_target else 5
                return bytes((JCC[mnemonic] ^ 1, 3, 0xE9)) + _word(
                    op.expr.number - (instruction_address + wide_size), 4 if long_target else 2)
            # Keep NASM's linear layout-based encoding choice above, but
            # validate a selected rel8 using the CPU's wrapping 16-bit IP.
            fits_rel8 = _signed8 if long_target or forced_operand_width == 32 else _signed8_word
            if (op.expr.symbolic or op.expr.relocation) and not op.expr.unresolved and not fits_rel8(delta):
                self._range_errors.append((self._line.filename, self._line.number))
            return branch_prefix + bytes((JCC[mnemonic], delta & 0xFF))
        if mnemonic in ("jmp", "call"):
            self._require(count == 1)
            op = ops[0]
            if op.kind == "imm" and op.qualifier is None and op.width == 8:
                op.qualifier = "short"
            elif (op.kind == "imm" and op.qualifier is None and op.width == 16 and
                  self.compatibility == "nasm09839"):
                op.qualifier = "near"
            if op.kind == "far":
                return bytes((0xEA if mnemonic == "jmp" else 0x9A,)) + _word(op.expr.number, 2) + _word(op.far_segment.number, 2)
            if op.kind in ("reg", "mem"):
                self._require(op.width in (None, 16))
                far_memory = op.kind == "mem" and op.qualifier == "far"
                return self._rm(0xFF, (5 if mnemonic == "jmp" else 3) if far_memory else (4 if mnemonic == "jmp" else 2), op, 16)
            self._require(op.kind == "imm" and op.qualifier != "far")
            long_target = op.width == 32 or (forced_operand_width == 32 and op.width is None)
            prefix = b"\x66" if long_target and forced_operand_width is None else b""
            short_size = 2 + len(prefix)
            near_size = (5 if long_target else 3) + len(prefix)
            instruction_address = self._address + prefix_size
            delta8 = op.expr.number - (instruction_address + short_size)
            if mnemonic == "jmp" and op.expr.symbolic and op.expr.number > self._address:
                delta8 = self._forward_short_delta(delta8, op.expr, short_size, prefix_size)
            site = (self._line.filename, self._line.number)
            cross_section = op.expr.section is not None and op.expr.section != self._section.name
            if mnemonic == "jmp" and self.optimize <= 1 and self._pass == 0 and op.expr.unresolved and op.qualifier is None:
                self._wide_jumps.add(site)
            modern_unqualified_near = (self.compatibility == "nasm3" and op.qualifier != "short" and
                                       (self.optimize <= 1 or op.expr.relocation != 1))
            if mnemonic == "jmp" and op.qualifier != "near" and (op.qualifier == "short" or
                    (not op.strict and not modern_unqualified_near and not cross_section and site not in self._wide_jumps and
                     not op.expr.unresolved and _signed8(delta8))):
                fits_rel8 = _signed8 if long_target else _signed8_word
                if (op.expr.symbolic or op.expr.relocation) and not op.expr.unresolved and not fits_rel8(delta8):
                    self._range_errors.append((self._line.filename, self._line.number))
                return prefix + bytes((0xEB, delta8 & 0xFF))
            self._require(op.qualifier != "short")
            return (prefix + bytes((0xE9 if mnemonic == "jmp" else 0xE8,)) +
                    _word(op.expr.number - (instruction_address + near_size), 4 if long_target else 2))
        if mnemonic in ("push", "pop"):
            self._require(count == 1)
            op = ops[0]
            if op.kind == "seg":
                return bytes(((0x06 if mnemonic == "push" else 0x07) + (op.reg << 3),))
            if op.kind == "reg" and op.width == 16:
                return bytes(((0x50 if mnemonic == "push" else 0x58) + op.reg,))
            self._require(op.kind == "mem" and op.width in (None, 16))
            return self._rm(0xFF if mnemonic == "push" else 0x8F, 6 if mnemonic == "push" else 0, op, 16)
        if mnemonic in ("inc", "dec"):
            self._require(count == 1)
            op = ops[0]
            if op.kind == "reg" and op.width == 16:
                return bytes(((0x40 if mnemonic == "inc" else 0x48) + op.reg,))
            self._require(op.kind in ("reg", "mem"))
            width = op.width or 8
            return self._rm((0xFE if width == 8 else 0xFF), 0 if mnemonic == "inc" else 1, op, width)
        if mnemonic in UNARY_GROUP:
            self._require(count == 1 and ops[0].kind in ("reg", "mem"))
            op = ops[0]
            width = op.width or 8
            return self._rm(0xF6 if width == 8 else 0xF7, UNARY_GROUP[mnemonic], op, width)
        if mnemonic in SHIFT:
            self._require(count == 2)
            dst, amount = ops
            self._require(dst.kind in ("reg", "mem"))
            width = dst.width or 8
            if ((amount.kind == "reg" and amount.width in (8, 16) or
                 amount.kind == "shift_count") and amount.reg == 1):
                return self._rm(0xD2 if width == 8 else 0xD3, SHIFT[mnemonic], dst, width)
            unsized_unity = amount.width is None and amount.qualifier is None
            relaxed_unity = self.optimize > 0 and not amount.strict
            self._require(amount.kind == "imm" and amount.expr.number == 1 and
                          (unsized_unity or relaxed_unity),
                          "8086 shift count must be 1 or CL")
            return self._rm(0xD0 if width == 8 else 0xD1, SHIFT[mnemonic], dst, width)
        if mnemonic in ALU or mnemonic in ("test", "mov", "movabs", "xchg", "lea", "lds", "les", "in", "out"):
            self._require(count == 2)
            return self._encode_pair(mnemonic, ops[0], ops[1])
        raise self._error(f"unknown or non-8086 instruction: {mnemonic}")

    def _encode_pair(self, mnemonic: str, dst: Operand, src: Operand) -> bytes:
        self._require(("far" not in dst.distance_flags or dst.kind == "mem") and
                      ("far" not in src.distance_flags or src.kind == "mem"))
        if mnemonic == "movabs":
            self._require(self.compatibility == "nasm3")
            absolute_load = dst.kind == "reg" and dst.reg == 0 and src.kind == "mem" and not src.base
            absolute_store = dst.kind == "mem" and not dst.base and src.kind == "reg" and src.reg == 0
            register_immediate = dst.kind == "reg" and src.kind == "imm"
            self._require(absolute_load or absolute_store or register_immediate)
            mnemonic = "mov"
        if (self.compatibility == "nasm09839" and self.optimize == 0 and self._pass == 0 and
                dst.kind == "mem" and src.kind == "imm" and src.expr.unresolved):
            self._wide_displacements.add((self._line.filename, self._line.number))
        if self._pass == 0 and self.optimize <= 1 and mnemonic in ALU and src.kind == "imm" and src.expr.unresolved:
            self._wide_immediates.add((self._line.filename, self._line.number))
        if mnemonic == "mov":
            if dst.kind == "seg" and src.kind in ("reg", "mem"):
                return self._rm(0x8E, dst.reg, src, 16)
            if src.kind == "seg" and dst.kind in ("reg", "mem"):
                return self._rm(0x8C, src.reg, dst, 16)
            if dst.kind == "reg" and src.kind == "imm":
                self._require(src.width in (None, dst.width), "invalid operand sizes")
                return bytes(((0xB0 if dst.width == 8 else 0xB8) + dst.reg,)) + _word(src.expr.number, dst.width // 8)
            if dst.kind == "mem" and src.kind == "imm":
                width = dst.width or src.width or 8
                self._require(src.width in (None, width), "invalid operand sizes")
                return self._rm(0xC6 if width == 8 else 0xC7, 0, dst, width) + _word(src.expr.number, width // 8)
            if dst.kind == "reg" and src.kind == "mem":
                self._require(src.width in (None, dst.width))
                if dst.reg == 0 and not src.base and not src.direct_byte_form:
                    address_bytes = 4 if src.address_width == 32 or src.displacement_width == 32 else 2
                    return self._prefix(src) + bytes((0xA0 if dst.width == 8 else 0xA1,)) + _word(src.expr.number, address_bytes)
                return self._rm(0x8A if dst.width == 8 else 0x8B, dst.reg, src, dst.width)
            if dst.kind == "mem" and src.kind == "reg":
                self._require(dst.width in (None, src.width))
                if src.reg == 0 and not dst.base and not dst.direct_byte_form:
                    address_bytes = 4 if dst.address_width == 32 or dst.displacement_width == 32 else 2
                    return self._prefix(dst) + bytes((0xA2 if src.width == 8 else 0xA3,)) + _word(dst.expr.number, address_bytes)
                return self._rm(0x88 if src.width == 8 else 0x89, src.reg, dst, src.width)
            if dst.kind == "reg" and src.kind == "reg" and dst.width == src.width:
                return self._rm(0x88 if dst.width == 8 else 0x89, src.reg, dst, dst.width)
        elif mnemonic in ALU:
            base, field = ALU[mnemonic]
            if dst.kind in ("reg", "mem") and src.kind == "imm" and dst.width == 8:
                self._require(src.width in (None, 8), "invalid operand sizes")
            accumulator_fit = (_signed8_word(src.expr.number) if self.compatibility == "nasm3"
                               else ((src.expr.number + 0x80) & 0xFFFFFFFF) <= 0xFF)
            relocatable = self.compatibility == "nasm3" and src.expr.relocation != 0
            accumulator_short = dst.width == 16 and (src.width == 8 or
                                 (self.optimize > (0 if self.compatibility == "nasm3" else 1) and
                                  not src.strict and not src.expr.unresolved and not relocatable and accumulator_fit))
            if dst.kind == "reg" and src.kind == "imm" and dst.reg == 0 and not accumulator_short:
                return bytes((base + (4 if dst.width == 8 else 5),)) + _word(src.expr.number, dst.width // 8)
            if dst.kind in ("reg", "mem") and src.kind == "imm":
                width = dst.width or src.width or 8
                if width == 8:
                    return self._rm(0x80, field, dst, 8) + _word(src.expr.number, 1)
                preserve_word = self.compatibility == "nasm09839" and self.optimize <= 1 and src.width == 16
                preserve_forward = self.compatibility == "nasm09839" and self.optimize <= 1 and (
                    self._line.filename, self._line.number) in self._wide_immediates
                short = src.width == 8 or (self.optimize > 0 and not preserve_word and not src.strict and
                                           not preserve_forward and not src.expr.unresolved and not relocatable and
                                           _signed8_word(src.expr.number))
                return self._rm(0x83 if short else 0x81, field, dst, 16) + _word(src.expr.number, 1 if short else 2)
            if src.kind == "reg" and dst.kind in ("reg", "mem"):
                return self._rm(base if src.width == 8 else base + 1, src.reg, dst, src.width)
            if dst.kind == "reg" and src.kind == "mem":
                return self._rm(base + (2 if dst.width == 8 else 3), dst.reg, src, dst.width)
        elif mnemonic == "test":
            if dst.kind == "reg" and dst.reg == 0 and src.kind == "imm":
                self._require(src.width in (None, dst.width), "invalid operand sizes")
                return bytes((0xA8 if dst.width == 8 else 0xA9,)) + _word(src.expr.number, dst.width // 8)
            if dst.kind in ("reg", "mem") and src.kind == "imm":
                width = dst.width or src.width or 8
                self._require(src.width in (None, width), "invalid operand sizes")
                return self._rm(0xF6 if width == 8 else 0xF7, 0, dst, width) + _word(src.expr.number, width // 8)
            if src.kind == "reg" and dst.kind in ("reg", "mem"):
                return self._rm(0x84 if src.width == 8 else 0x85, src.reg, dst, src.width)
            if dst.kind == "reg" and src.kind == "mem":
                return self._rm(0x84 if dst.width == 8 else 0x85, dst.reg, src, dst.width)
        elif mnemonic == "xchg":
            if dst.kind == "reg" and src.kind == "reg" and dst.width == src.width == 16 and (dst.reg == 0 or src.reg == 0):
                return bytes((0x90 + (src.reg if dst.reg == 0 else dst.reg),))
            if src.kind == "reg" and dst.kind == "reg" and dst.width == src.width:
                if self.compatibility == "nasm09839":
                    return self._rm(0x86 if dst.width == 8 else 0x87, src.reg, dst, dst.width)
                return self._rm(0x86 if dst.width == 8 else 0x87, dst.reg, src, dst.width)
            if src.kind == "reg" and dst.kind in ("reg", "mem"):
                return self._rm(0x86 if src.width == 8 else 0x87, src.reg, dst, src.width)
            if dst.kind == "reg" and src.kind == "mem":
                return self._rm(0x86 if dst.width == 8 else 0x87, dst.reg, src, dst.width)
        elif mnemonic in ("lea", "lds", "les"):
            if mnemonic == "lea" and src.kind == "imm":
                self._require(self.compatibility == "nasm3")
                self._require(src.width in (None, 16))
                src = Operand("mem", width=16, expr=src.expr)
            self._require(dst.kind == "reg" and dst.width == 16 and src.kind == "mem")
            if mnemonic == "lea":
                # LEA reads the effective address, so NASM ignores an explicit
                # data width on the memory operand.
                src = replace(src, width=None)
            else:
                self._require(src.width in (None, 16))
            opcode = {"lea": 0x8D, "lds": 0xC5, "les": 0xC4}[mnemonic]
            return self._rm(opcode, dst.reg, src, 16)
        elif mnemonic == "in":
            self._require(dst.kind == "reg" and dst.reg == 0 and src.kind in ("reg", "imm"))
            if src.kind == "reg":
                self._require(src.width == 16 and src.reg == 2)
                return bytes((0xEC if dst.width == 8 else 0xED,))
            self._require(src.width != 16)
            return bytes((0xE4 if dst.width == 8 else 0xE5,)) + _word(src.expr.number, 1)
        elif mnemonic == "out":
            self._require(src.kind == "reg" and src.reg == 0 and dst.kind in ("reg", "imm"))
            if dst.kind == "reg":
                self._require(dst.width == 16 and dst.reg == 2)
                return bytes((0xEE if src.width == 8 else 0xEF,))
            self._require(dst.width != 16)
            return bytes((0xE6 if src.width == 8 else 0xE7,)) + _word(dst.expr.number, 1)
        raise self._error("invalid operand combination")

    def _data(self, directive: str, arguments: str, width: int | None = None) -> bytes:
        if width is None:
            width = {"db": 1, "dw": 2, "dd": 4, "dq": 8, "dt": 10, "do": 16,
                     "dy": 32, "dz": 64,
                     "bf16": 2}[directive]
        output = bytearray()
        size_layout = ()
        items = _split(arguments)
        if items and items[-1] == "": items.pop()
        for arg in items:
            if not arg: raise self._error("empty data item")
            item_width = width
            if self.compatibility == "nasm3":
                size = re.match(r"(?is)^(byte|word|dword|qword|tword|oword|yword|zword)\b\s+(.+)$", arg)
                if size:
                    item_width = {"byte": 1, "word": 2, "dword": 4,
                                  "qword": 8, "tword": 10,
                                  "oword": 16, "yword": 32,
                                  "zword": 64}[size.group(1).lower()]
                    arg = size.group(2).strip()
                if arg.startswith("%(") and arg.endswith(")"):
                    output.extend(self._data(directive, arg[2:-1], item_width))
                    size_layout = combine_layout("+", size_layout, self._size_layout, 0, 0)
                    continue
                if size and arg.startswith("(") and arg.endswith(")"):
                    output.extend(self._data(directive, arg[1:-1], item_width))
                    size_layout = combine_layout("+", size_layout, self._size_layout, 0, 0)
                    continue
            if arg == "?":
                output.extend(bytes(item_width))
                continue
            match = re.match(r"(?is)^(.*?)\s+dup\s*\((.*)\)$", arg)
            if match:
                amount = self._eval(match.group(1))
                self._require(not amount.unresolved and amount.number >= 0, "invalid dup count")
                if self.compatibility == "nasm3":
                    self._require(amount.relocation == 0 and not _bases(amount),
                                  "DUP count must be scalar")
                    final_item = _split(match.group(2))[-1]
                    self._require(not re.match(r"(?is)^.+?\s+dup\s*\(.*\)$", final_item),
                                  "nested DUP cannot end a data list in this NASM profile")
                element = self._data(directive, match.group(2), item_width)
                repeated = combine_layout("*", amount.layout, self._size_layout,
                                          amount.number, len(element))
                size_layout = combine_layout("+", size_layout, repeated, 0, 0)
                output.extend(element * amount.number)
                continue
            if arg[0] in "'\"`" and arg[-1:] == arg[0]:
                content = string_bytes(arg)
                if item_width == 1: output.extend(content)
                else:
                    output.extend(content)
                    output.extend(bytes((-len(content)) % item_width))
            else:
                if directive == "dt" and item_width == 10:
                    packed_bcd = encode_bcd(arg)
                    if packed_bcd is not None:
                        output.extend(packed_bcd)
                        continue
                try: floating = encode_float(arg, item_width, bfloat=directive == "bf16",
                                             rounding=self._float_rounding,
                                             daz=self._float_daz)
                except ValueError as exc: raise self._error(str(exc)) from exc
                if floating is not None:
                    output.extend(floating)
                    continue
                self._require(item_width <= 8 and directive != "bf16",
                              f"{directive.upper()} requires a floating-point constant")
                output.extend(_word(self._eval(arg).number, item_width))
        self._size_layout = size_layout
        return bytes(output)

    @staticmethod
    def _fpu_register_index(text: str) -> int | None:
        match = re.fullmatch(r"(?i)st([0-7])", text.strip())
        if match is None:
            return None
        return int(match.group(1))

    def _encode_fpu(self, mnemonic: str, arguments: str,
                    explicit_segment: bool = False,
                    forced_address_width: int | None = None) -> bytes:
        operands = _split(arguments) if arguments else []
        if not operands:
            encoding = FPU_FIXED.get(mnemonic)
            self._require(encoding is not None, "FPU instruction requires an operand")
            return encoding
        forms = FPU_REGISTER.get(mnemonic, {})
        if len(operands) == 1:
            operand = operands[0]
            to = re.fullmatch(r"(?i)to\s+(.+)", operand)
            index = self._fpu_register_index(to.group(1) if to else operand)
            if index is not None:
                form = "fpureg|to" if to else "fpureg"
                self._require(form in forms, "invalid FPU register operand")
                opcode, base = forms[form]
                return bytes((opcode, base + index))
            self._require(to is None, "TO requires an FPU register")
            memory = self._operand(operand, forced_address_width)
            self._require(memory.kind == "mem", "FPU instruction requires memory or ST register")
            self._require(not explicit_segment or not memory.segment,
                          "instruction has conflicting segment overrides")
            variants = FPU_MEMORY.get(mnemonic, {})
            width = memory.width
            if width is None and None not in variants:
                width = 32 if 32 in variants else next(iter(variants), None)
            if width not in variants and None in variants:
                width = None
            self._require(width in variants, "FPU memory operand size is missing or invalid")
            prefix, opcode, field = variants[width]
            return prefix + self._rm(opcode, field, memory, memory.width or width or 16)
        if len(operands) == 2:
            left = self._fpu_register_index(operands[0])
            right = self._fpu_register_index(operands[1])
            self._require(left is not None and right is not None, "FPU register operands expected")
            if right == 0 and "fpureg,fpu0" in forms:
                opcode, base = forms["fpureg,fpu0"]
                return bytes((opcode, base + left))
            if left == 0 and "fpu0,fpureg" in forms:
                opcode, base = forms["fpu0,fpureg"]
                return bytes((opcode, base + right))
        raise self._error("invalid FPU operand combination")

    def _instruction(self, text: str) -> bytes:
        self._size_layout = ()
        text = text.strip()
        bracketed = text.startswith("[") and text.endswith("]")
        if bracketed:
            text = text[1:-1].strip()
        match = re.match(r"(?is)^([a-z_][\w]*)\b\s*(.*)$", text.strip())
        if not match: raise self._error("expected instruction or directive")
        mnemonic, arguments = match.group(1).lower(), match.group(2).strip()
        if mnemonic == "dollarhex":
            self._require(bracketed, "DOLLARHEX requires brackets")
            self._set_dollarhex(arguments)
            return b""
        if mnemonic == "float":
            self._require(bool(arguments), "FLOAT requires an option")
            options = [arguments] if bracketed else _split(arguments)
            for option in options:
                self._set_float_option(option)
            return b""
        if mnemonic == "default":
            if not arguments:
                return b""
            for option in re.split(r"[\s,]+", arguments.lower()):
                if not option:
                    continue
                if option == "bnd":
                    self._default_bnd = True
                elif option == "nobnd":
                    self._default_bnd = False
                elif option in ("rel", "abs", "fs:rel", "fs:abs", "gs:rel", "gs:abs"):
                    continue  # Relative defaults have no 16-bit address form.
                else:
                    raise self._error(f"invalid DEFAULT option: {option}")
            return b""
        if mnemonic in ("bnd", "nobnd") and not arguments:
            raise self._error("instruction expected after prefix")
        if mnemonic == "list":
            self._require(bracketed and arguments[:1] in ("+", "-"),
                          "invalid LIST option")
            return b""
        if mnemonic == "debug":
            self._require(bracketed and re.match(r"^[A-Za-z_.$?@][\w.$?@~#]*", arguments)
                          is not None, "DEBUG needs an identifier")
            return b""
        if mnemonic in ("prefix", "suffix", "postfix", "gprefix", "gsuffix",
                        "gpostfix", "lprefix", "lsuffix", "lpostfix"):
            self._require(bracketed, "label-mangling directive requires brackets")
            return b""
        if mnemonic in ("static", "required"):
            self._require(bool(arguments), f"{mnemonic.upper()} needs a symbol")
            return b""
        if mnemonic == "bits":
            self._require(arguments == "16", "only BITS 16 is supported")
            return b""
        if mnemonic == "use16":
            self._require(not arguments)
            return b""
        if mnemonic == "cpu":
            self._require(arguments.lower() in ("8086", "8088"), "only CPU 8086/8088 is supported")
            return b""
        if mnemonic == "org":
            value = self._eval(arguments)
            self._require(not value.unresolved, "ORG needs a known address")
            if self._org_this_pass is None:
                self._org_this_pass = value.number
                self._program_origin = value.number
            else:
                self._require(value.number == self._org_this_pass, "conflicting ORG")
            return b""
        if mnemonic == "absolute":
            value = self._eval(arguments)
            self._require(not value.unresolved, "ABSOLUTE needs a known address")
            self._absolute_context = value
            self._section = None
            self._origin = 0
            self._address = value.number
            return b""
        if mnemonic in ("section", "segment"):
            self._select_section(arguments)
            return b""
        if mnemonic == "sectalign":
            if arguments.lower() in ("on", "off"):
                self._sectalign_auto = arguments.lower() == "on"
                return b""
            alignment = self._eval(arguments)
            self._require(not alignment.unresolved and alignment.number > 0 and
                          alignment.number & (alignment.number - 1) == 0,
                          "SECTALIGN needs a power of two")
            if self._section is not None:
                self._record_section_attribute(self._section, "align")
            if self._section is not None and alignment.number > self._section.align:
                self._section.align = alignment.number
                self._layout_sections()
            return b""
        if mnemonic == "global":
            self._require(bool(arguments), "GLOBAL needs a symbol")
            return b""
        if mnemonic == "extern":
            self._require(bool(arguments), "EXTERN needs a symbol")
            return b""
        if mnemonic in ("db", "dw", "dd", "dq", "dt", "do", "dy", "dz", "bf16"):
            if mnemonic == "bf16": self._require(self._use_fp, "BF16 requires %use fp")
            return self._data(mnemonic, arguments)
        if mnemonic in ("resb", "resw", "resd", "resq", "rest", "reso", "resy", "resz"):
            count = self._eval(arguments)
            # NASM3 permits forward reservation counts. Use their provisional
            # size until the normal symbol/layout convergence checks finish;
            # unresolved names and self-growing layouts still fail there.
            self._require((not count.unresolved or self.compatibility == "nasm3") and
                          (count.number >= 0 or self.compatibility == "nasm3"),
                          "invalid reserve count")
            self._require(self.compatibility != "nasm3" or count.unresolved or
                          (count.relocation == 0 and not _bases(count)),
                          "reserve count must be scalar")
            unit = {"resb": 1, "resw": 2, "resd": 4, "resq": 8,
                    "rest": 10, "reso": 16, "resy": 32, "resz": 64}[mnemonic]
            self._size_layout = scale_layout(count.layout, unit) if count.number >= 0 else None
            return bytes(max(0, count.number) * unit)
        if mnemonic == "alignmode":
            self._require(self._smartalign_active, "ALIGNMODE requires %use smartalign")
            parts = _split(arguments)
            self._require(1 <= len(parts) <= 2, "ALIGNMODE needs a mode")
            mode = parts[0].lower()
            self._require(mode in _SMARTALIGN_16, f"unknown alignment mode: {mode}")
            threshold = _SMARTALIGN_DEFAULT_THRESHOLD[mode]
            if len(parts) == 2 and parts[1]:
                if parts[1].lower() == "nojmp":
                    threshold = -1
                else:
                    value = self._eval(parts[1])
                    self._require(not value.unresolved, "ALIGNMODE needs a known threshold")
                    threshold = value.number
            self._smartalign_mode = mode
            self._smartalign_threshold = threshold
            if mode == "k7":
                # NASM's k7 macro replaces 1-4 byte patterns but leaves the
                # 16-bit group size (and longer patterns) from the prior mode.
                self._smartalign_patterns[1:5] = _SMARTALIGN_16[mode][1:5]
            else:
                self._smartalign_patterns[:len(_SMARTALIGN_16[mode])] = _SMARTALIGN_16[mode]
                self._smartalign_group = len(_SMARTALIGN_16[mode]) - 1
            return b""
        if mnemonic in ("align", "alignb"):
            parts = _split(arguments)
            alignment = self._eval(parts[0])
            self._require(not alignment.unresolved and alignment.number > 0, "invalid alignment")
            updates_section = self._sectalign_auto or (mnemonic == "align" and self._smartalign_active)
            if updates_section:
                self._require(alignment.number & (alignment.number - 1) == 0,
                              "section alignment needs a power of two")
            if updates_section and self._section is not None:
                self._record_section_attribute(self._section, "align")
            if (updates_section and
                    self._section is not None and alignment.number > self._section.align):
                self._section.align = alignment.number
                self._layout_sections()
            relative_address = (self._address - self._section.base if self._section is not None
                                else self._address)
            padding = (-relative_address) % alignment.number
            self._line_alignments[self._line_index] = alignment.number
            if len(parts) == 1:
                if mnemonic == "align" and self._smartalign_active:
                    if (self._smartalign_threshold >= 0 and
                            padding > self._smartalign_threshold):
                        short_filler = (-(relative_address + 2)) % alignment.number
                        if self.optimize > 1 and short_filler <= 127:
                            return bytes((0xEB, short_filler)) + b"\x90" * short_filler
                        near_filler = (-(relative_address + 3)) % alignment.number
                        return b"\xE9" + _word(near_filler, 2) + b"\x90" * near_filler
                    patterns = self._smartalign_patterns
                    group = self._smartalign_group
                    groups, remainder = divmod(padding, group)
                    return patterns[group] * groups + patterns[remainder]
                return bytes((0 if mnemonic == "alignb" else 0x90,)) * padding
            fill_source = ",".join(parts[1:])
            head = fill_source.split(None, 1)[0].lower()
            if head not in KNOWN_MNEMONICS:
                fill = self._eval(fill_source)
                if not fill.unresolved: return _word(fill.number, 1) * padding
            saved_address = self._address
            result = bytearray()
            for _ in range(padding):
                chunk = self._instruction(fill_source)
                result.extend(chunk)
                self._address += len(chunk)
            self._address = saved_address
            return bytes(result)
        if mnemonic == "incbin":
            parts = _split(arguments)
            if parts and parts[-1] == "":
                parts.pop()
            self._require(1 <= len(parts) <= 3 and len(parts[0]) >= 2 and
                          parts[0][0] in "'\"`" and parts[0][-1] == parts[0][0],
                          "INCBIN needs a quoted path and at most two ranges")
            filename = string_bytes(parts[0]).decode("latin-1").replace("\\", "/")
            if self.compatibility == "nasm3":
                candidates = [Path(filename)] + [p / filename for p in self.include_paths]
            else:
                candidates = [Path(self._line.filename).parent / filename] + [
                    p / filename for p in self.include_paths]
            path = next((p for p in candidates if p.is_file()), None)
            if path is None: raise self._error(f"binary include not found: {filename}")
            data = path.read_bytes()
            for item in parts[1:]:
                self._require(bool(item) and item[0] not in "'\"`",
                              "INCBIN range needs a numeric expression")
            start_value = self._eval(parts[1]) if len(parts) > 1 else Value(0)
            length_value = self._eval(parts[2]) if len(parts) > 2 else None
            self._require(not start_value.unresolved and
                          (length_value is None or not length_value.unresolved),
                          "INCBIN range needs a known address")
            start = start_value.number
            length = length_value.number if length_value is not None else len(data) - start
            if start >= len(data) or length == 0:
                return b""
            self._require(start >= 0 and length >= 0, "invalid INCBIN range")
            return data[start:start + length]
        prefix_slots: dict[int, tuple[str, int]] = {}
        prefix_in_order = bytearray()
        explicit_address_width = None
        explicit_operand_width = None
        while (mnemonic in PREFIX or mnemonic in ADDRESS_PREFIX or
               mnemonic in OPERAND_PREFIX) and arguments:
            if mnemonic in ADDRESS_PREFIX:
                self._require(self.compatibility == "nasm3")
                selected_width = ADDRESS_PREFIX[mnemonic]
                self._require(explicit_address_width in (None, selected_width),
                              "instruction has conflicting prefixes")
                explicit_address_width = selected_width
            elif mnemonic in OPERAND_PREFIX:
                self._require(self.compatibility == "nasm3")
                selected_width = OPERAND_PREFIX[mnemonic]
                self._require(explicit_operand_width in (None, selected_width),
                              "instruction has conflicting prefixes")
                explicit_operand_width = selected_width
            elif self.compatibility == "nasm3":
                slot = (0 if mnemonic == "wait" else 1 if mnemonic in SEG_PREFIX else
                        2 if mnemonic == "lock" else 3)
                previous = prefix_slots.get(slot)
                self._require(previous is None or previous[0] == mnemonic,
                              "instruction has conflicting prefixes")
                prefix_slots[slot] = (mnemonic, PREFIX[mnemonic])
            else:
                self._require(mnemonic not in ("bnd", "nobnd"))
                prefix_in_order.append(PREFIX[mnemonic])
            match = re.match(r"(?i)^([a-z_][\w]*)\b\s*(.*)$", arguments)
            if not match: raise self._error("instruction expected after prefix")
            mnemonic, arguments = match.group(1).lower(), match.group(2).strip()
        def slot_bytes(slot: int) -> bytes:
            return (bytes((prefix_slots[slot][1],))
                    if slot in prefix_slots and prefix_slots[slot][1] else b"")

        if self.compatibility == "nasm3":
            prefix = slot_bytes(0)
            prefix += slot_bytes(1)
            prefix += b"\x67" if explicit_address_width == 32 else b""
            prefix += slot_bytes(2)
            prefix += b"\x66" if explicit_operand_width == 32 else b""
            prefix += slot_bytes(3)
        else:
            prefix = bytes(prefix_in_order)
        def with_prefixes(core: bytes) -> bytes:
            if self.compatibility != "nasm3":
                return prefix + core
            if mnemonic in FPU_MNEMONICS and core.startswith(b"\x9b"):
                core = core[1:]
                prefix_slots.setdefault(0, ("wait", 0x9B))
            generated_segment = None
            if core and core[0] in SEG_PREFIX.values():
                generated_segment, core = core[0], core[1:]
            address_prefix = b""
            if core.startswith(b"\x67"):
                address_prefix, core = b"\x67", core[1:]
            self._require(not address_prefix or explicit_address_width != 16,
                          "conflicting address size specifications")
            if explicit_address_width == 32:
                address_prefix = b"\x67"
            operand_prefix = b""
            if core.startswith(b"\x66"):
                operand_prefix, core = b"\x66", core[1:]
            self._require(not operand_prefix or explicit_operand_width != 16,
                          "conflicting operand size specifications")
            if explicit_operand_width == 32:
                operand_prefix = b"\x66"
            if generated_segment is not None:
                self._require(1 not in prefix_slots, "conflicting segment overrides")
                prefix_slots[1] = ("segment", generated_segment)
            ordered = slot_bytes(0)
            ordered += slot_bytes(1)
            ordered += address_prefix
            ordered += slot_bytes(2)
            ordered += operand_prefix
            ordered += slot_bytes(3)
            return ordered + core
        if mnemonic in FPU_MNEMONICS:
            return with_prefixes(self._encode_fpu(mnemonic, arguments, 1 in prefix_slots,
                                                   explicit_address_width))
        operands = [self._operand(item, explicit_address_width)
                    for item in _split(arguments)] if arguments else []
        self._require(1 not in prefix_slots or all(op.segment is None for op in operands),
                      "instruction has conflicting segment overrides")
        if (self.compatibility == "nasm3" and explicit_address_width == 32 and
                operands and operands[0].kind == "imm" and
                ((mnemonic in ("jcxz", "loopw", "loopew", "loopzw", "loopnew", "loopnzw") and
                  len(operands) == 1) or
                 (mnemonic in ("jcxz", "loop", "loope", "loopz", "loopne", "loopnz") and
                  len(operands) == 2 and operands[1].kind == "reg" and
                  operands[1].width == 16 and operands[1].reg == 1))):
            return b""
        repne_prefix = (self.compatibility == "nasm3" and 3 in prefix_slots and
                        prefix_slots[3][0] in ("repne", "repnz"))
        explicit_bnd = prefix_slots[3][0] if 3 in prefix_slots and prefix_slots[3][0] in ("bnd", "nobnd") else None
        if explicit_bnd and mnemonic == "jmp" and len(operands) == 1 and operands[0].kind == "imm" and operands[0].qualifier is None:
            operands[0].qualifier = "near"
        default_jcc_bnd = (self.compatibility == "nasm3" and self._default_bnd and
                           3 not in prefix_slots and mnemonic in JCC and
                           0x70 <= JCC[mnemonic] <= 0x7F)
        if default_jcc_bnd:
            prefix_slots[3] = ("bnd", 0xF2)
        core = self._encode(mnemonic, operands, len(prefix) + int(default_jcc_bnd), repne_prefix,
                            explicit_operand_width)
        def bnd_eligible(encoded: bytes) -> bool:
            if mnemonic in ("ret", "retw", "retn", "retnw"):
                return True
            if mnemonic in ("call", "jmp") and len(operands) == 1:
                operand = operands[0]
                if operand.kind == "far" or (operand.kind == "mem" and operand.qualifier == "far"):
                    return False
                return mnemonic == "call" or not encoded.lstrip(b"\x66").startswith(b"\xeb")
            if mnemonic in JCC and 0x70 <= JCC[mnemonic] <= 0x7F:
                short = encoded.lstrip(b"\x66")
                return len(short) == 2 and 0x70 <= short[0] <= 0x7F
            return False
        if default_jcc_bnd and not bnd_eligible(core):
            prefix_slots.pop(3)
            core = self._encode(mnemonic, operands, len(prefix), repne_prefix,
                                explicit_operand_width)
        if explicit_bnd:
            self._require(bnd_eligible(core), "bnd prefix is not allowed")
        elif (self.compatibility == "nasm3" and self._default_bnd and
              not default_jcc_bnd and not repne_prefix and bnd_eligible(core)):
            previous_slot = prefix_slots.get(3)
            prefix_slots[3] = ("bnd", 0xF2)
            trial = self._encode(mnemonic, operands,
                                 len(prefix) + (0 if previous_slot and previous_slot[1] else 1),
                                 False, explicit_operand_width)
            if bnd_eligible(trial):
                core = trial
            else:
                if previous_slot is None:
                    prefix_slots.pop(3)
                else:
                    prefix_slots[3] = previous_slot
        if repne_prefix and mnemonic in ("ret", "retw", "retn", "retnw"):
            raise self._error("invalid REPNE prefix for near return")
        if repne_prefix and mnemonic in ("jmp", "call"):
            op = operands[0]
            far_transfer = op.kind == "far" or (op.kind == "mem" and op.qualifier == "far")
            short_jump = mnemonic == "jmp" and core.lstrip(b"\x66").startswith(b"\xeb")
            self._require(far_transfer or short_jump, "invalid REPNE prefix for near branch")
        return with_prefixes(core)
