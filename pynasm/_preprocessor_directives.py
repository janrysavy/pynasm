"""Preprocessor package, stack argument, and macro reset directives."""

from __future__ import annotations

from ._assembler_syntax import *


class PreprocessorDirectiveMixin:
    def _load_macro_package(self, parts, definitions, macros, lines, filename, number):
        self._require(len(parts) == 2, "%use requires a macro package")
        package = parts[1].lower()
        if package not in self._loaded_packages:
            if package == "fp":
                definitions.update({"Inf": "__Infinity__", "NaN": "__QNaN__",
                                    "QNaN": "__QNaN__", "SNaN": "__SNaN__"})
                for name in ("float8", "float16", "bfloat16", "float32", "float64",
                             "float80m", "float80e", "float128l", "float128h"):
                    self._store_smacro_definition(
                        name, [SmacroParameter("x")], f"__{name}__(x)")
                self._use_fp = True
            elif package == "ifunc":
                aliases = {"ilog2": "e", "ilog2e": "e", "ilog2f": "f", "ilog2c": "c",
                           "ilog2w": "w", "ilog2fw": "w", "ilog2cw": "cw"}
                for name, kind in aliases.items():
                    self._store_smacro_definition(
                        name, [SmacroParameter("x")], f"(__?ilog2{kind}?__(x))")
                self._use_ifunc = True
            elif package == "altreg":
                registers = zip(
                    ("rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"),
                    ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi"),
                    ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di"),
                    ("al", "cl", "dl", "bl", "spl", "bpl", "sil", "dil"),
                )
                for number, (qword, dword, word, byte) in enumerate(registers):
                    self._case_insensitive_definitions.update({
                        f"r{number}": qword, f"r{number}d": dword,
                        f"r{number}w": word, f"r{number}b": byte,
                        f"r{number}l": byte,
                    })
                for number, byte in enumerate(("ah", "ch", "dh", "bh")):
                    self._case_insensitive_definitions[f"r{number}h"] = byte
                for number in range(8, 32):
                    self._case_insensitive_definitions[f"r{number}l"] = f"r{number}b"
            elif package == "smartalign":
                lines.append(SourceLine("\x00smartalign_on", filename, number))
                definitions["__?ALIGN_JMP_THRESHOLD?__"] = "8"
                definitions["__?ALIGN_16BIT_GROUP?__"] = "8"
                definitions["__?ALIGNMODE?__"] = "generic,8"
                self._aliases["__ALIGNMODE__"] = "__?ALIGNMODE?__"
            elif package == "masm":
                macros["segment"] = [MacroDefinition(0, 1, ["[segment %00 %1]"], True, [], True)]
                macros["ends"] = [MacroDefinition(0, 1_000_000, ["%null ends %00"], True, [], True)]
                macros["proc"] = [MacroDefinition(0, 1_000_000, [
                    "%rep %0", "%ifidni %1,far", "%idefine ret retf",
                    "%else", "%idefine ret retn", "%endif", "%rotate 1", "%endrep",
                ], True, [], False)]
                macros["endp"] = [MacroDefinition(0, 0, ["%null endp %00", "%undef ret"],
                                                   True, [], False)]
                macros["end"] = [MacroDefinition(0, 1_000_000, [], True, [], True)]
                self._case_insensitive_definitions.update({
                    "ptr": "__?masm_ptr?__", "flat": "__?masm_flat?__",
                    "offset": "", "tbyte": "tword",
                })
                if ("st" not in self._case_insensitive_functions and
                        "st" not in self._function_definitions and
                        "st" not in self._case_insensitive_definitions and
                        "st" not in definitions):
                    self._store_smacro_definition(
                        "st", [SmacroParameter("x")], "st %+ x",
                        insensitive=True)
            elif package == "vtern":
                for name in ("vpternlogd", "vpternlogq"):
                    macros[name] = [MacroDefinition(4, 4, ["%? %1,%2,%3,%4"],
                                                    True, [], False)]
            else:
                raise self._error("unsupported macro package")
            marker = package.upper()
            definitions[f"__?USE_{marker}?__"] = ""
            self._loaded_packages.add(package)

    def _define_stack_arguments(self, directive, parts, definitions):
        arguments = _split(" ".join(parts[1:]))
        self._require(bool(arguments) and bool(arguments[0]),
                      f"{directive} missing argument parameter")
        local_size_name = None
        if directive == "%local":
            self._require(bool(self._context_stack),
                          "%$localsize context stack is empty")
            local_size_name = f"..@{self._context_stack[-1][1]}.localsize"
            self._require(local_size_name in definitions,
                          "%$localsize needs an initial value")
        offset = self._arg_offset if directive == "%arg" else self._local_offset
        original_offset = offset
        sizes = {"byte": 1, "word": 2, "dword": 4, "qword": 8,
                 "tword": 10, "oword": 16, "yword": 32, "zword": 64}
        for argument in arguments:
            match = re.match(r"^\s*([A-Za-z_.$?@][\w.$?@~#]*):([A-Za-z_.$?@][\w.$?@~#]*)(.*)$",
                             argument)
            self._require(match is not None, f"invalid {directive} parameter")
            name, size_name, remainder = match.groups()
            expanded_size = _pp_tokens(self._expand_define(size_name, definitions))
            size = sizes.get(expanded_size[0].lower()) if expanded_size else None
            self._require(size is not None, f"invalid {directive} size type")
            size = (size + self._stack_slot_size - 1) // self._stack_slot_size * self._stack_slot_size
            if directive == "%local":
                offset += size
                displacement = -offset
            else:
                displacement = offset
                offset += size
            if directive == "%arg" and not self._stacksize_explicit:
                marker = f"__?PYNASM_DEFERRED_ARG_{len(self._deferred_args)}?__"
                self._deferred_args.append((marker, displacement - 8))
                definitions[name] = marker
            else:
                definitions[name] = f"({self._stack_pointer}+{displacement})"
            if remainder.strip():
                break
        if directive == "%arg":
            self._arg_offset = offset
        else:
            self._local_offset = offset
            previous_size = self._pp_eval(definitions[local_size_name], definitions)
            self._require(not previous_size.unresolved,
                          "%$localsize needs an initial value")
            definitions[local_size_name] = str(previous_size.number + offset - original_offset)

    def _clear_macros(self, parts, definitions, macros):
        option_tokens = _pp_tokens(self._expand_define(
            " ".join(parts[1:]), definitions))
        if not option_tokens:
            option_tokens = ["define", "macro"]
        context = False
        position = 0
        while position < len(option_tokens):
            option = option_tokens[position]
            if not re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", option):
                break
            position += 1
            while position < len(option_tokens) and option_tokens[position] == ",":
                position += 1
            option = option.lower()
            if option in ("context", "ctx"):
                context = True
                continue
            if option == "global":
                context = False
                continue
            if option in ("nothing", "none", "ignore"):
                continue
            if option not in ("all", "define", "def", "smacro",
                              "defalias", "alias", "salias", "alldef",
                              "alldefine", "macro", "mmacro"):
                raise self._error(f"invalid option to %clear: {option}")
            context_prefixes = tuple(f"..@{serial}." for _, serial in self._context_stack)
            def in_scope(name: str) -> bool:
                local = name.startswith(context_prefixes) if context_prefixes else False
                return local if context else not local
            if option in ("all", "define", "def", "smacro", "alldef", "alldefine"):
                for table in (definitions, self._case_insensitive_definitions,
                              self._function_definitions, self._case_insensitive_functions,
                              self._plain_definition_orders,
                              self._case_insensitive_plain_orders,
                              self._case_insensitive_definition_names):
                    for name in list(table):
                        if in_scope(name):
                            del table[name]
                            if table is definitions:
                                self._location_macros_enabled.discard(name)
            if option in ("all", "defalias", "alias", "salias", "alldef", "alldefine"):
                for table in (self._aliases, self._case_insensitive_aliases):
                    for name in list(table):
                        if in_scope(name):
                            del table[name]
            if option in ("all", "macro", "mmacro") and not context:
                macros.clear()
                self._disabled_standard_macros.update(
                    ("struc", "endstruc", "istruc", "at", "iend", "alignmode"))
