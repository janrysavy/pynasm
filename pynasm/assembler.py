"""Multipass NASM-style flat binary assembler for 8086/8088."""

from __future__ import annotations

from ._assembler_syntax import *
from ._preprocessor_macros import MacroExpansionMixin
from ._preprocessor_directives import PreprocessorDirectiveMixin
from ._preprocessor_source import SourceReaderMixin
from ._instruction_encoding import InstructionEncodingMixin
from .listing import ListingLine
from ._layout import Layout, combine_layout


class Assembler(SourceReaderMixin, MacroExpansionMixin, PreprocessorDirectiveMixin, InstructionEncodingMixin):
    def __init__(self, *, optimize: int = 0, include_paths: list[str | Path] | None = None,
                 defines: dict[str, str] | None = None, compatibility: str = "nasm09839",
                 timestamp: int | None = None, preincludes: list[str | Path] | None = None):
        if compatibility not in ("nasm09839", "nasm3"):
            raise ValueError("compatibility must be 'nasm09839' or 'nasm3'")
        self.optimize = optimize
        self.compatibility = compatibility
        self.include_paths = [Path(p) for p in (include_paths or [])]
        self.preincludes = [Path(p) for p in (preincludes or [])]
        self.defines = dict(defines or {})
        self.timestamp = timestamp
        self.symbols: dict[str, int] = {}
        self._previous: dict[str, int] = {}
        self._symbol_sections: dict[str, str | None] = {}
        self._previous_symbol_sections: dict[str, str | None] = {}
        self._symbol_relocations: dict[str, int] = {}
        self._previous_symbol_relocations: dict[str, int] = {}
        self._symbol_layouts: dict[str, Layout] = {}
        self._previous_symbol_layouts: dict[str, Layout] = {}
        self._symbol_unresolved: dict[str, bool] = {}
        self._previous_symbol_unresolved: dict[str, bool] = {}
        self._global = ""
        self._line = SourceLine("", "<string>", 0)
        self._address = 0
        self._line_address = 0
        self._origin = 0
        self._pass = 0
        self._lines: list[SourceLine] = []
        self._missing: set[str] = set()
        self._invalid_times = False
        self._wide_jumps: set[tuple[str, int]] = set()
        self._wide_jcc: set[tuple[str, int]] = set()
        self._wide_displacements: set[tuple[str, int]] = set()
        self._wide_immediates: set[tuple[str, int]] = set()
        self._old_size = 0
        self._line_index = 0
        self._previous_line_positions: list[tuple[int, str | None]] = []
        self._previous_line_sizes: list[int] = []
        self._older_line_sizes: list[int] = []
        self._macro_serial = 0
        self._macro_definition_serial = 0
        self._rep_serial = 0
        self._sections: dict[str, Section] = {}
        self._previous_sections: dict[str, Section] = {}
        self._section: Section | None = None
        self._program_origin = 0
        self._section_overlap = False
        self._pp_symbols: dict[str, int] = {}
        self._pp_known_labels: dict[str, int] = {}
        self._pp_origin = 0
        self._pp_code_seen = False
        self._dollarhex = True
        self._float_rounding = "near"
        self._float_daz = False
        self._default_bnd = False
        self._function_definitions: dict[str, list[SmacroDefinition]] = {}
        self._case_insensitive_definitions: dict[str, str] = {}
        self._plain_definition_orders: dict[str, int] = {}
        self._case_insensitive_plain_orders: dict[str, int] = {}
        self._case_insensitive_functions: dict[str, list[SmacroDefinition]] = {}
        self._smacro_definition_serial = 0
        self._case_insensitive_definition_names: dict[str, str] = {}
        self._context_stack: list[tuple[str, int]] = []
        self._context_serial = 0
        self._use_fp = False
        self._use_ifunc = False
        self._loaded_packages: set[str] = set()
        self._sane_empty_expansion = False
        self._smartalign_active = False
        self._smartalign_mode = "generic"
        self._smartalign_threshold = 8
        self._smartalign_patterns = list(_SMARTALIGN_16["generic"])
        self._smartalign_group = 8
        self._integer_warning_sites: set[tuple[str, int, str]] = set()
        self._warning_user_enabled = True
        self._warning_stack: list[bool] = []
        self._other_warning_sites: set[tuple[str, int, str]] = set()
        self._sectalign_auto = True
        self._location_macros_enabled = {"__?FILE?__", "__?LINE?__"}
        self._included_paths: set[Path] = set()
        self._stack_slot_size = 4
        self._stack_pointer = "ebp"
        self._arg_offset = 8
        self._local_offset = 0
        self._stacksize_explicit = False
        self._deferred_args: list[tuple[str, int]] = []
        self._last_sizes: list[int] = []
        self.listing: tuple[ListingLine, ...] = ()

    def _error(self, message: str) -> AssemblyError:
        return AssemblyError(message, self._line.filename, self._line.number)

    def _key(self, name: str) -> str:
        if name.startswith("$"): name = name[1:]
        if name.startswith("..@"): return name
        return self._global + name if name.startswith(".") else name

    def _lookup(self, name: str) -> Value:
        if name == "$$":
            return Value(self._origin, relocation=0 if self._section is None else 1,
                         layout=() if self._section is None else ((self._section.name, -1, 1),))
        if name.startswith("section.") and name.endswith(".start"):
            section_name = name[len("section."):-len(".start")]
            section = self._sections.get(section_name) or self._previous_sections.get(section_name)
            if section is not None:
                return Value(section.base, symbolic=True, section=section_name, relocation=1,
                             layout=((section_name, -1, 1),))
        name = self._key(name)
        if name in self.symbols:
            # An EQU evaluated earlier in this pass is not a forward reference,
            # even when its expression ultimately depends on a later label.
            return Value(self.symbols[name], unresolved=self._symbol_unresolved.get(name, False),
                         symbolic=True, section=self._symbol_sections.get(name),
                         relocation=self._symbol_relocations.get(name, 0),
                         layout=self._symbol_layouts.get(name))
        if name in self._previous:
            return Value(self._previous[name],
                         self._pass == 0 or self._previous_symbol_unresolved.get(name, False), True,
                         self._previous_symbol_sections.get(name),
                         self._previous_symbol_relocations.get(name, 0),
                         self._previous_symbol_layouts.get(name), forward=True)
        self._missing.add(name)
        return Value(0, True, True, layout=None, forward=True)

    def _eval(self, expression: str) -> Value:
        location = Value(self._line_address, relocation=1,
                         layout=() if self._section is None else
                         ((self._section.name, self._line_index, 1),))
        try: return evaluate(expression, self._lookup, location,
                             self._integer_function, dollarhex=self._dollarhex)
        except ExpressionError as exc: raise self._error(str(exc)) from exc

    def _pp_eval(self, expression: str, definitions: dict[str, str], *,
                 allow_trailing: bool = False) -> Value:
        expanded = self._expand_define(expression, definitions)
        def lookup(name: str) -> Value:
            if name in self._pp_symbols: return Value(self._pp_symbols[name])
            if name == "$$": return Value(self._pp_origin)
            if name in self._pp_known_labels: return Value(self._pp_known_labels[name])
            return Value(0, True)
        try: return evaluate(expanded, lookup, functions=self._integer_function,
                             allow_trailing=allow_trailing, dollarhex=self._dollarhex)
        except ExpressionError as exc: raise self._error(str(exc)) from exc

    def _set_dollarhex(self, arguments: str, definitions: dict[str, str] | None = None) -> None:
        option = arguments.strip().lower()
        if option in ("", "on", "yes", "true"):
            self._dollarhex = True
        elif option in ("off", "no", "false"):
            self._dollarhex = False
        else:
            value = (self._pp_eval(arguments, definitions) if definitions is not None
                     else self._eval(arguments))
            self._require(not value.unresolved, "DOLLARHEX needs a constant option")
            self._dollarhex = bool(value.number)

    def _set_float_option(self, option: str) -> None:
        option = option.strip().lower()
        if option in ("near", "down", "up", "zero"):
            self._float_rounding = option
        elif option == "daz":
            self._float_daz = True
        elif option == "nodaz":
            self._float_daz = False
        elif option == "default":
            self._float_rounding = "near"
            self._float_daz = False
        else:
            raise self._error(f"unknown FLOAT option: {option}")

    def _integer_function(self, name: str, argument: Value) -> Value | None:
        kinds = {
            "__?ilog2e?__": "e", "__?ilog2f?__": "f", "__?ilog2c?__": "c",
            "__?ilog2w?__": "fw", "__?ilog2fw?__": "fw", "__?ilog2cw?__": "cw",
        }
        kind = kinds.get(name)
        if kind is None: return None
        if argument.unresolved: return Value(0, unresolved=True)
        number = argument.number & 0xFFFFFFFFFFFFFFFF
        exact = number != 0 and number & (number - 1) == 0
        if kind == "e" and not exact:
            raise ExpressionError("ilog2 argument is not a power of two")
        if kind in ("fw", "cw") and not exact:
            site = (self._line.filename, self._line.number, name)
            if site not in self._integer_warning_sites:
                self._integer_warning_sites.add(site)
                warnings.warn(f"{site[0]}:{site[1]}: ilog2 argument is not a power of two", stacklevel=2)
        if number == 0: return Value(0)
        result = (number - 1).bit_length() if kind in ("c", "cw") else number.bit_length() - 1
        return Value(result)

    def _section_names(self) -> list[str]:
        names = list(self._sections)
        pending = [n for n in names if n != ".text" and not self._sections[n].nobits]
        ordered = [".text"]
        while pending:
            ready = next((n for n in pending if self._sections[n].follows is None or
                          self._sections[n].follows in ordered), None)
            if ready is None: raise self._error("cyclic SECTION follows dependency")
            ordered.append(ready)
            pending.remove(ready)
        return ordered + [n for n in names if n != ".text" and self._sections[n].nobits]

    def _layout_sections(self) -> None:
        def aligned_file_offset(offset: int, alignment: int) -> int:
            absolute = self._program_origin + offset
            return ((absolute + alignment - 1) // alignment) * alignment - self._program_origin

        file_end = 0
        for name in self._section_names():
            section = self._sections[name]
            old = self._previous_sections.get(name)
            estimated_size = old.size if old is not None else section.size
            # Earlier labels must see requirements discovered later in the
            # preceding pass. Otherwise a late ALIGN moves bytes but leaves
            # their already-bound symbols at the old, weaker alignment.
            alignment = max(section.align, old.align if old is not None else 1)
            if name == ".text":
                start = (section.start if section.start is not None else
                         aligned_file_offset(0, alignment))
            elif section.start is not None:
                start = section.start
            elif section.follows:
                predecessor = self._sections.get(section.follows) or self._previous_sections.get(section.follows)
                self._require(predecessor is not None, f"unknown SECTION in follows={section.follows}")
                predecessor_old = self._previous_sections.get(section.follows)
                predecessor_size = predecessor_old.size if predecessor_old is not None else predecessor.size
                start = aligned_file_offset(predecessor.file_start + predecessor_size,
                                            alignment)
            else:
                start = aligned_file_offset(file_end, alignment)
            section.file_start = start
            if section.vstart is not None:
                section.base = section.vstart
            elif section.vfollows:
                predecessor = self._sections.get(section.vfollows) or self._previous_sections.get(section.vfollows)
                self._require(predecessor is not None, f"unknown SECTION in vfollows={section.vfollows}")
                predecessor_old = self._previous_sections.get(section.vfollows)
                predecessor_size = predecessor_old.size if predecessor_old is not None else predecessor.size
                section.base = ((predecessor.base + predecessor_size + alignment - 1) // alignment) * alignment
            else:
                section.base = self._program_origin + start
            if not section.nobits:
                file_end = max(file_end, start + estimated_size)
        if self._section is not None:
            self._origin = self._section.base
            self._address = self._origin + self._section.size

    def _record_section_attribute(self, section: Section, attribute: str) -> None:
        # Defaults are not explicit attributes. NASM distinguishes an implicit
        # alignment from ALIGNB/SECTALIGN even when its numeric value is equal.
        self._section_attributes.setdefault(section.name, set()).add(attribute)
        self._section_attribute_lines[section.name] = self._line

    def _validate_section_attributes(self) -> None:
        if self.compatibility != "nasm3":
            return
        real = {"start", "align", "follows"}
        virtual = {"vstart", "valign", "vfollows"}
        for name, attributes in self._section_attributes.items():
            if self._sections[name].nobits and attributes & real and attributes & virtual:
                line = self._section_attribute_lines[name]
                raise AssemblyError(f"cannot mix real and virtual attributes in nobits section ({name})",
                                    line.filename, line.number)

    def _select_section(self, arguments: str) -> None:
        parts = arguments.split()
        self._require(bool(parts), "SECTION needs a name")
        name = parts[0]
        if name not in self._sections:
            self._sections[name] = Section(name, align=1 if name == ".text" else 4,
                                           nobits=name == ".bss")
        section = self._sections[name]
        for item in parts[1:]:
            lower = item.lower()
            attribute = lower.split("=", 1)[0]
            already_aligned = "align" in self._section_attributes.get(name, set())
            if "=" in lower and attribute in ("start", "align", "follows", "vstart", "valign", "vfollows"):
                self._record_section_attribute(section, attribute)
            if lower == "nobits": section.nobits = True
            elif lower == "progbits": section.nobits = False
            elif lower.startswith(("align=", "start=", "vstart=")):
                key, value = item.split("=", 1)
                key = key.lower()
                evaluated = self._eval(value)
                self._require(not evaluated.unresolved, f"SECTION {key} needs a known value")
                value = evaluated.number
                if key == "align":
                    self._require(value > 0 and value & (value - 1) == 0,
                                  "SECTION alignment must be a power of two")
                    if already_aligned:
                        value = max(section.align, value)
                setattr(section, key, value)
            elif lower.startswith(("follows=", "vfollows=")):
                key, value = item.split("=", 1)
                setattr(section, key.lower(), value)
            else:
                site = (self._line.filename, self._line.number, item)
                if site not in self._other_warning_sites:
                    self._other_warning_sites.add(site)
                    warnings.warn(f"{site[0]}:{site[1]}: ignoring unknown section attribute: {item}",
                                  stacklevel=2)
        self._require(section.align > 0 and section.align & (section.align - 1) == 0,
                      "SECTION alignment must be a power of two")
        self._section = section
        self._layout_sections()

    def _run_pass(self, previous_sizes: list[int]) -> tuple[bytes, list[int]]:
        self._deferred_branch_relax = False
        self._previous_line_sizes = previous_sizes
        self._line_positions: list[tuple[int, str | None]] = []
        self._line_alignments: dict[int, int] = {}
        self._line_size_layouts: dict[int, Layout] = {}
        self._section_attributes: dict[str, set[str]] = {}
        self._section_attribute_lines: dict[str, SourceLine] = {}
        self._sectalign_auto = True
        self._dollarhex = True
        self._float_rounding = "near"
        self._float_daz = False
        self._default_bnd = False
        self._location_macros_enabled = {"__?FILE?__", "__?LINE?__"}
        self._included_paths = set()
        self._stack_slot_size = 4
        self._stack_pointer = "ebp"
        self._arg_offset = 8
        self._local_offset = 0
        self._stacksize_explicit = False
        self._deferred_args = []
        self._smartalign_active = False
        self._smartalign_mode = "generic"
        self._smartalign_threshold = 8
        self._smartalign_patterns = list(_SMARTALIGN_16["generic"])
        self._smartalign_group = 8
        self._sections = {
            name: Section(name, old.align, old.nobits, old.start, old.vstart,
                          follows=old.follows, vfollows=old.vfollows)
            for name, old in self._previous_sections.items()
        }
        if ".text" not in self._sections: self._sections[".text"] = Section(".text", align=1)
        for line in self._lines:
            candidate = _comment(line.text).strip()
            if candidate.startswith("[") and candidate.endswith("]"):
                candidate = candidate[1:-1].strip()
            declaration = re.match(r"(?i)^(?:section|segment)\s+(\S+)", candidate)
            if declaration and declaration.group(1) not in self._sections:
                name = declaration.group(1)
                self._sections[name] = Section(name, align=1 if name == ".text" else 4,
                                               nobits=name == ".bss")
        self._section = self._sections[".text"]
        self._layout_sections()
        self._org_this_pass = None
        self._global = ""
        self.symbols = {}
        self._symbol_layouts = {}
        self._symbol_unresolved = {}
        self._symbol_sections = {}
        self._symbol_relocations = {}
        self._missing = set()
        self._invalid_times = False
        self._section_overlap = False
        self._range_errors = []
        self._in_times = False
        sizes: list[int] = []
        for line_index, line in enumerate(self._lines):
            self._line_index = line_index
            self._line_positions.append((self._address, self._section.name if self._section else None))
            self._line = line
            self._line_address = self._address
            self._old_size = previous_sizes[line_index] if line_index < len(previous_sizes) else 0
            text = _comment(line.text).strip()
            if text == "\x00smartalign_on":
                self._smartalign_active = True
                sizes.append(0)
                continue
            colon_equ = re.match(r"(?i)^([A-Za-z_.$?@][\w.$?@~#]*)\s*:\s*equ\b\s*(.+)$", text)
            if colon_equ:
                name = colon_equ.group(1)
                key = self._key(name)
                if key in self.symbols: raise self._error(f"duplicate symbol {name}")
                value = self._eval(colon_equ.group(2))
                self.symbols[key] = value.number
                self._symbol_sections[key] = value.section
                self._symbol_relocations[key] = value.relocation
                self._symbol_layouts[key] = value.layout
                self._symbol_unresolved[key] = value.unresolved
                sizes.append(0)
                continue
            while text:
                label = re.match(r"^([A-Za-z_.$?@][\w.$?@~#]*)\s*:\s*(.*)$", text)
                if not label: break
                name = label.group(1)
                if not name.startswith((".", "$.")):
                    self._global = name[1:] if name.startswith("$") else name
                key = self._key(name)
                if key in self.symbols: raise self._error(f"duplicate label {name}")
                self.symbols[key] = self._address
                self._symbol_sections[key] = self._section.name if self._section is not None else None
                self._symbol_relocations[key] = 1 if self._section is not None else 0
                self._symbol_layouts[key] = (() if self._section is None else
                                             ((self._section.name, line_index, 1),))
                text = label.group(2).strip()
            if not text:
                sizes.append(0)
                continue
            equ = re.match(r"(?i)^([A-Za-z_.$?@][\w.$?@~#]*)\s+equ\b\s*(.+)$", text)
            if equ:
                key = self._key(equ.group(1))
                if key in self.symbols: raise self._error(f"duplicate symbol {key}")
                value = self._eval(equ.group(2))
                self.symbols[key] = value.number
                self._symbol_sections[key] = value.section
                self._symbol_relocations[key] = value.relocation
                self._symbol_layouts[key] = value.layout
                self._symbol_unresolved[key] = value.unresolved
                sizes.append(0)
                continue
            orphan = re.match(r"^([A-Za-z_.$?@][\w.$?@~#]*)\s+(.+)$", text)
            if orphan and orphan.group(1).lower() not in KNOWN_MNEMONICS:
                next_word = orphan.group(2).split(None, 1)[0].lower()
                if next_word in KNOWN_MNEMONICS:
                    name = orphan.group(1)
                    if not name.startswith((".", "$.")):
                        self._global = name[1:] if name.startswith("$") else name
                    key = self._key(name)
                    if key in self.symbols: raise self._error(f"duplicate label {name}")
                    self.symbols[key] = self._address
                    self._symbol_sections[key] = self._section.name if self._section is not None else None
                    self._symbol_relocations[key] = 1 if self._section is not None else 0
                    self._symbol_layouts[key] = (() if self._section is None else
                                                 ((self._section.name, line_index, 1),))
                    text = orphan.group(2)
            times = re.match(r"(?is)^times\s+(.+?)\s+(db|dw|dd|dq|resb|resw|resd|resq|[a-z]+)\b(.*)$", text)
            count_text = times.group(1) if times else None
            instruction = times.group(2) + times.group(3) if times else None
            if count_text is None and re.match(r"(?i)^times\s*\(", text):
                start = text.index("(")
                depth = 0
                for position in range(start, len(text)):
                    if text[position] == "(": depth += 1
                    elif text[position] == ")":
                        depth -= 1
                        if depth == 0: break
                if depth: raise self._error("unterminated TIMES count")
                count_text = text[start:position + 1]
                instruction = text[position + 1:].strip()
            if count_text is not None:
                count = self._eval(count_text)
                if count.unresolved or count.number < 0:
                    self._invalid_times = True
                    count = Value(0)
                encoded = bytearray()
                repeated_layout = ()
                first_shape = None
                uniform_shape = True
                self._in_times = True
                for _ in range(count.number):
                    chunk = self._instruction(instruction)
                    shape = len(chunk), self._size_layout
                    if first_shape is None:
                        first_shape = shape
                    elif shape != first_shape:
                        uniform_shape = False
                    repeated_layout = combine_layout("+", repeated_layout,
                                                     self._size_layout, 0, 0)
                    encoded.extend(chunk)
                    if self._section is None:
                        self._require(not chunk or re.match(r"(?i)^(?:resb|resw|resd|resq|rest|reso|resy|resz|alignb)\b",
                                                            instruction) is not None,
                                      "attempt to assemble code in ABSOLUTE space")
                    else:
                        if not self._section.nobits: self._section.data.extend(chunk)
                        self._section.size += len(chunk)
                    self._address += len(chunk)
                self._in_times = False
                data = bytes(encoded)
                if count.layout != ():
                    repeated_layout = (combine_layout("*", count.layout, first_shape[1],
                                                      count.number, first_shape[0])
                                       if uniform_shape and first_shape else None)
                if repeated_layout != ():
                    self._line_size_layouts[line_index] = repeated_layout
                sizes.append(len(data))
                continue
            data = self._instruction(text)
            if self._size_layout != ():
                self._line_size_layouts[line_index] = self._size_layout
            if self._section is None:
                self._require(not data or re.match(r"(?i)^(?:resb|resw|resd|resq|rest|reso|resy|resz|alignb)\b",
                                                   text) is not None,
                              "attempt to assemble code in ABSOLUTE space")
            else:
                if not self._section.nobits: self._section.data.extend(data)
                self._section.size += len(data)
            self._address += len(data)
            sizes.append(len(data))
        self._validate_section_attributes()
        output = bytearray()
        for name in sorted(self._section_names(), key=lambda n: (self._sections[n].file_start, n != ".text")):
            section = self._sections[name]
            if section.nobits or not section.data: continue
            if section.file_start < len(output): self._section_overlap = True
            else: output.extend(bytes(section.file_start - len(output)))
            output.extend(section.data)
        return bytes(output), sizes

    def assemble(self, source: str, *, filename: str = "<string>") -> bytes:
        self.listing = ()
        self._previous = {}
        self._previous_symbol_layouts = {}
        self._previous_symbol_unresolved = {}
        self._previous_symbol_sections = {}
        self._previous_symbol_relocations = {}
        self._pass = 0
        self._wide_jumps = set()
        self._wide_jcc = set()
        self._wide_displacements = set()
        self._wide_immediates = set()
        self._macro_serial = 0
        self._macro_definition_serial = 0
        self._rep_serial = 0
        self._program_origin = 0
        self._previous_sections = {}
        self._pp_symbols = {}
        self._pp_known_labels = {}
        self._pp_origin = 0
        self._pp_code_seen = False
        self._dollarhex = True
        self._float_rounding = "near"
        self._float_daz = False
        self._default_bnd = False
        self._function_definitions = {}
        self._case_insensitive_definitions = {}
        self._case_insensitive_functions = {}
        self._plain_definition_orders = {}
        self._case_insensitive_plain_orders = {}
        self._smacro_definition_serial = 0
        self._case_insensitive_definition_names = {}
        self._context_stack = []
        self._context_serial = 0
        self._use_fp = False
        self._use_ifunc = False
        self._loaded_packages = set()
        self._sane_empty_expansion = False
        self._aliases = {}
        self._case_insensitive_aliases = {}
        self._aliases_enabled = True
        self._structure_definitions = []
        self._structure_instances = []
        self._structure_serial = 0
        self._disabled_standard_macros = set()
        self._integer_warning_sites = set()
        self._warning_user_enabled = True
        self._warning_stack = []
        self._other_warning_sites = set()
        self._sectalign_auto = True
        builtins = {"__?OUTPUT_FORMAT?__": "bin", "__?BITS?__": "16"}
        builtins.update({
            "__?SECT?__": "",
            "__?SECTALIGN_ALIGN_UPDATES_SECTION?__": "1",
            "__?FLOAT_DAZ?__": "nodaz",
            "__?FLOAT_ROUND?__": "near",
            "__?FLOAT?__": "__?FLOAT_DAZ?__,__?FLOAT_ROUND?__",
        })
        for name in ("OUTPUT_FORMAT", "BITS", "SECT", "SECTALIGN_ALIGN_UPDATES_SECTION",
                     "FLOAT_DAZ", "FLOAT_ROUND", "FLOAT",
                     "FILE", "LINE", "POSIX_TIME", "NASM_MAJOR", "NASM_MINOR",
                     "NASM_SUBMINOR"):
            self._aliases[f"__{name}__"] = f"__?{name}?__"
        now = int(time.time()) if self.timestamp is None else self.timestamp
        for prefix, value in (("", time.localtime(now)), ("UTC_", time.gmtime(now))):
            date = time.strftime("%Y-%m-%d", value)
            clock = time.strftime("%H:%M:%S", value)
            date_number = str(value.tm_year * 10000 + value.tm_mon * 100 + value.tm_mday)
            clock_number = str(value.tm_hour * 10000 + value.tm_min * 100 + value.tm_sec)
            for name, replacement in (("DATE", f'"{date}"'),
                                      ("DATE_NUM", date_number),
                                      ("TIME", f'"{clock}"'),
                                      ("TIME_NUM", clock_number)):
                builtins[f"__?{prefix}{name}?__"] = replacement
                self._aliases[f"__{prefix}{name}__"] = f"__?{prefix}{name}?__"
        builtins["__?POSIX_TIME?__"] = str(now)
        if self.compatibility == "nasm3":
            builtins.update({"__?NASM_MAJOR?__": "3", "__?NASM_MINOR?__": "2",
                             "__?NASM_SUBMINOR?__": "0"})
        for name, value in self.defines.items():
            builtins[self._resolve_alias(name)] = value
        macros: dict[str, list[MacroDefinition]] = {}
        self._lines = []
        for preinclude in self.preincludes:
            candidates = [preinclude]
            if self.compatibility != "nasm3":
                candidates.append(Path(filename).parent / preinclude)
            candidates.extend(path / preinclude for path in self.include_paths)
            path = next((candidate for candidate in candidates if candidate.is_file()), None)
            if path is None:
                raise AssemblyError(f"preinclude file not found: {preinclude}")
            self._included_paths.add(path.resolve())
            self._lines.extend(self._read_source(path.read_text(encoding="latin-1"),
                                                 str(path.resolve()), builtins, macros=macros))
        self._lines.extend(self._read_source(source, filename, builtins, macros=macros))
        if self._deferred_args:
            # NASM carries stack mode/offset across passes; a later %stacksize
            # can make an earlier %arg resolve to a 16-bit BP expression.
            pointer = self._stack_pointer if self._stacksize_explicit else "ebp"
            initial_offset = self._arg_offset if self._stacksize_explicit else 8
            replacements = {marker: f"({pointer}+{initial_offset + relative})"
                            for marker, relative in self._deferred_args}
            for at, line in enumerate(self._lines):
                text = line.text
                for marker, replacement in replacements.items():
                    text = text.replace(marker, replacement)
                self._lines[at] = SourceLine(text, line.filename, line.number)
        self.symbols = {}
        self._symbol_layouts = {}
        self._symbol_unresolved = {}
        self._symbol_sections = {}
        self._symbol_relocations = {}
        self._address = self._origin = 0
        self._line_address = 0
        self._global = ""
        for line in self._lines:
            self._line = line
            candidate = _comment(line.text).strip()
            if candidate.startswith("[") and candidate.endswith("]"):
                candidate = candidate[1:-1].strip()
            equ = re.match(r"(?i)^([A-Za-z_.$?@][\w.$?@~#]*)\s*:?\s+equ\b\s*(.+)$", candidate)
            if equ:
                value = self._eval(equ.group(2))
                if not value.unresolved:
                    key = self._key(equ.group(1))
                    self.symbols[key] = value.number
                    self._symbol_sections[key] = value.section
                    self._symbol_relocations[key] = value.relocation
                    self._symbol_layouts[key] = value.layout
                    self._symbol_unresolved[key] = value.unresolved
        previous_sizes: list[int] = []
        older_sizes: list[int] = []
        self._previous_line_positions = []
        self._previous_line_alignments: dict[int, int] = {}
        self._previous_line_size_layouts: dict[int, Layout] = {}
        # A chain of boundary branches can relax one instruction per pass:
        # each newly widened forward branch shifts the following symbols.
        # Allow the pass budget to scale with source length while retaining a
        # minimum for short programs with ALIGN/TIMES dependencies.
        for pass_number in range(max(20, len(self._lines) + 2)):
            self._pass = pass_number
            self._older_line_sizes = older_sizes
            previous_origin = self._program_origin
            previous_symbols = self._previous
            previous_relocations = self._previous_symbol_relocations
            previous_sections = self._previous_sections
            output, sizes = self._run_pass(previous_sizes)
            current_line_positions = self._line_positions
            self._last_sizes = sizes
            section_state = [(n, s.size, s.file_start, s.base, s.nobits, s.follows, s.vfollows, s.align)
                             for n, s in self._sections.items()]
            old_section_state = [(n, s.size, s.file_start, s.base, s.nobits, s.follows, s.vfollows, s.align)
                                 for n, s in previous_sections.items()]
            if (pass_number > 0 and not self._deferred_branch_relax and
                    previous_origin == self._program_origin and sizes == previous_sizes and
                    self.symbols == previous_symbols and
                    self._symbol_relocations == previous_relocations and
                    self._symbol_layouts == self._previous_symbol_layouts and
                    self._line_size_layouts == self._previous_line_size_layouts and
                    self._symbol_unresolved == self._previous_symbol_unresolved and
                    section_state == old_section_state):
                if self._missing: raise self._error("undefined symbol: " + sorted(self._missing)[0])
                if self._invalid_times: raise self._error("TIMES needs a known nonnegative count")
                if self._range_errors:
                    filename, line = self._range_errors[0]
                    raise AssemblyError("short jump is out of range", filename, line)
                if self._section_overlap: raise self._error("binary sections overlap")
                records = []
                for line, (address, name), size in zip(self._lines, self._line_positions, sizes):
                    section = self._sections.get(name)
                    offset = address - section.base if section is not None else address
                    file_offset = (section.file_start + offset
                                   if section is not None and not section.nobits and size else None)
                    data = output[file_offset:file_offset + size] if file_offset is not None else b""
                    if file_offset is not None and (file_offset < 0 or len(data) != size):
                        raise self._error("listing extent outside assembled output")
                    records.append(ListingLine(line.filename, line.number, line.text, name,
                                               offset, address, file_offset, size, data))
                self.listing = tuple(records)
                return output
            self._previous = dict(self.symbols)
            self._previous_symbol_layouts = dict(self._symbol_layouts)
            self._previous_symbol_unresolved = dict(self._symbol_unresolved)
            self._previous_symbol_sections = dict(self._symbol_sections)
            self._previous_symbol_relocations = dict(self._symbol_relocations)
            self._previous_sections = self._sections
            self._previous_line_positions = current_line_positions
            self._previous_line_alignments = self._line_alignments
            self._previous_line_size_layouts = self._line_size_layouts
            older_sizes = previous_sizes
            previous_sizes = sizes
        raise self._error("assembly did not converge")


def assemble(source: str, *, filename: str = "<string>", optimize: int = 0,
             compatibility: str = "nasm09839") -> bytes:
    return Assembler(optimize=optimize, compatibility=compatibility).assemble(source, filename=filename)
