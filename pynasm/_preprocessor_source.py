"""Source reader and preprocessor directive dispatch."""

from __future__ import annotations

from ._assembler_syntax import *


class SourceReaderMixin:
    def _read_source(self, source: str, filename: str, definitions: dict[str, str],
                     stack: tuple[str, ...] = (),
                     macros: dict[str, list[MacroDefinition]] | None = None) -> list[SourceLine]:
        if filename in stack: raise AssemblyError("recursive %include", filename)
        source_filename = filename
        stack += (filename,)
        if macros is None: macros = {}
        lines: list[SourceLine] = []
        active: list[tuple[bool, bool]] = []
        rep_stack: list[tuple[int, int]] = []
        raw_lines: list[tuple[int, str, MacroInvocation | None, SourceLine | None]] = [
            (number, line, None, None) for number, line in enumerate(source.splitlines(), 1)
        ]
        physical_anchor = 0
        logical_anchor = 0
        line_increment = 1
        logical_filename = filename

        def apply_line_directive(argument: str, physical_number: int,
                                 cpp: bool = False) -> None:
            nonlocal physical_anchor, logical_anchor, line_increment, logical_filename
            line_match = re.match(r"([0-9][\w]*)(?:([+-])([0-9][\w]*))?(.*)$", argument)
            self._require(line_match is not None, "%line expects a line number")
            new_line = _number(line_match.group(1))
            self._require(new_line is not None, "%line expects a line number")
            self._require(not line_match.group(4).startswith(("+", "-")),
                          "%line expects a line increment")
            increment = _number(line_match.group(3)) if line_match.group(3) else 1
            self._require(increment is not None, "%line expects a line increment")
            if line_match.group(2) == "-":
                increment = -increment
            remainder = line_match.group(4).strip()
            if remainder:
                tokens = _pp_tokens(remainder)
                if tokens and tokens[0][0] in "'\"`" and tokens[0][-1] == tokens[0][0]:
                    if cpp and tokens[0][0] in "'\"":
                        try:
                            logical_filename = ast.literal_eval(tokens[0])
                        except (SyntaxError, ValueError):
                            logical_filename = string_bytes(tokens[0]).decode("latin-1")
                    else:
                        logical_filename = string_bytes(tokens[0]).decode("latin-1")
                else:
                    logical_filename = remainder
            physical_anchor = physical_number
            logical_anchor = new_line
            line_increment = increment

        index = 0
        while index < len(raw_lines):
            physical_number, raw, invocation_frame, location_override = raw_lines[index]
            number = logical_anchor + (physical_number - physical_anchor) * line_increment
            filename = logical_filename
            if location_override is not None:
                filename = location_override.filename
                number = location_override.number
            index += 1
            if "__?FILE?__" in self._location_macros_enabled:
                definitions["__?FILE?__"] = _quote_string(filename)
            if "__?LINE?__" in self._location_macros_enabled:
                definitions["__?LINE?__"] = str(number)
            if raw.startswith("\x00rep_start:"):
                rep_stack.append((int(raw.split(":", 1)[1]), len(active)))
                continue
            if raw.startswith("\x00rep_end:"):
                self._require(bool(rep_stack) and rep_stack[-1][0] == int(raw.split(":", 1)[1]),
                              "invalid %rep expansion")
                rep_stack.pop()
                continue
            raw = _unbrace_pp_tokens(raw)
            if invocation_frame is not None:
                reported_count = (invocation_frame.reported_count
                                  if invocation_frame.reported_count is not None else
                                  len(invocation_frame.arguments))
                def expand_range(match: re.Match[str]) -> str:
                    count = len(invocation_frame.arguments)
                    first, last = int(match.group(1)), int(match.group(2))
                    self._require(first != 0 and last != 0 and
                                  abs(first) <= count and abs(last) <= count,
                                  "macro parameters out of range")
                    first = first + count + 1 if first < 0 else first
                    last = last + count + 1 if last < 0 else last
                    step = 1 if first <= last else -1
                    return ",".join(invocation_frame.arguments[index - 1]
                                    for index in range(first, last + step, step))
                def expand_macro_piece(piece: str) -> str:
                    def expand_condition(match: re.Match[str]) -> str:
                        index = int(match.group(2))
                        self._require(1 <= index <= len(invocation_frame.arguments),
                                      f"macro parameter `{match.group(0)}' is not a condition code")
                        argument = invocation_frame.arguments[index - 1].strip()
                        code = argument.lower()
                        self._require(len(_pp_tokens(argument)) == 1 and
                                      code in _PP_INVERSE_CONDITIONS,
                                      f"macro parameter `{match.group(0)}' is not a condition code")
                        if match.group(1) == "-":
                            inverse = _PP_INVERSE_CONDITIONS[code]
                            self._require(inverse is not None,
                                          f"condition code `{code}' is not invertible")
                            return inverse
                        return code

                    piece = re.sub(r"%%([A-Za-z_.$?@][\w.$?@~#]*)",
                                   lambda match: invocation_frame.prefix + match.group(1), piece)
                    piece = re.sub(r"%00(?![0-9])", invocation_frame.invocation_label or "", piece)
                    piece = re.sub(r"%\{(-?[0-9]+):(-?[0-9]+)\}", expand_range, piece)
                    piece = re.sub(r"%([+-])([0-9]+)", expand_condition, piece)
                    piece = re.sub(r"%\{([0-9]+)\}",
                                   lambda match: str(reported_count) if match.group(1) == "0" else
                                   (invocation_frame.arguments[int(match.group(1)) - 1]
                                    if int(match.group(1)) <= len(invocation_frame.arguments) else ""), piece)
                    piece = re.sub(r"%([0-9]+)",
                                   lambda match: str(reported_count) if match.group(1) == "0" else
                                   (invocation_frame.arguments[int(match.group(1)) - 1]
                                    if int(match.group(1)) <= len(invocation_frame.arguments) else ""), piece)
                    return piece.replace("%??", invocation_frame.declared_name or "").replace(
                        "%?", invocation_frame.invoked_name or "")

                pieces = re.split(r"('[^']*'|\"[^\"]*\"|`(?:[^`\\]|\\.)*`)", raw)
                for piece_index in range(0, len(pieces), 2):
                    pieces[piece_index] = expand_macro_piece(pieces[piece_index])
                raw = "".join(pieces)
            if all(state[0] for state in active):
                raw = self._expand_context_locals(raw)
            self._line = SourceLine(raw, filename, number)
            stripped = _comment(raw).strip()
            if stripped.startswith("%") or re.match(r"^#\s+", stripped):
                stripped = re.sub(r"(?i)^%(if|elif)(?=[0-9+\-~(!])", r"%\1 ", stripped)
                parts = stripped.split(None, 2)
                directive = "%line" if parts[0] == "#" else parts[0].lower()
                enabled = all(state[0] for state in active)
                if directive == "%line" and invocation_frame is None:
                    apply_line_directive(stripped[len(parts[0]):].lstrip(), physical_number,
                                         parts[0] == "#")
                elif directive == "%line":
                    pass
                elif directive in ("%macro", "%imacro", "%rmacro", "%irmacro"):
                    if len(parts) < 3: raise self._error("%macro requires a name and parameter count")
                    name = (self._expand_indirection(parts[1], definitions)
                            if enabled else parts[1])
                    count_match = re.fullmatch(r"(\d+)(?:-(\d+|\*))?(\+)?(?:\.nolist)?(?:\s+(.*))?", parts[2])
                    if not count_match: raise self._error("invalid %macro parameter count")
                    minimum = int(count_match.group(1))
                    maximum = (1_000_000 if count_match.group(2) == "*" else int(count_match.group(2))) if count_match.group(2) else minimum
                    greedy = bool(count_match.group(3))
                    defaults = ([_unbrace_macro_argument(self._expand_define(item, definitions))
                                 for item in _split(count_match.group(4), macro=True)]
                                if count_match.group(4) else [])
                    if (defaults and defaults[-1] == "" and not self._sane_empty_expansion and
                            count_match.group(4).rstrip().endswith(",")):
                        defaults.pop()
                    body = []
                    body_locations = []
                    depth = 1
                    while index < len(raw_lines):
                        body_physical, body_line, body_frame, body_location = raw_lines[index]
                        index += 1
                        marker = _comment(body_line).strip().split(None, 1)[0].lower() if _comment(body_line).strip() else ""
                        if marker == "%line" and body_frame is None:
                            apply_line_directive(_comment(body_line).strip()[5:].lstrip(), body_physical)
                            continue
                        if marker in ("%macro", "%imacro", "%rmacro", "%irmacro"): depth += 1
                        elif marker in ("%endmacro", "%endm"):
                            depth -= 1
                            if depth == 0: break
                        body.append(body_line)
                        body_locations.append(body_location or SourceLine(
                            body_line, logical_filename,
                            logical_anchor + (body_physical - physical_anchor) * line_increment))
                    if depth: raise self._error("unterminated %macro")
                    if enabled:
                        insensitive = directive in ("%imacro", "%irmacro")
                        self._macro_definition_serial += 1
                        macros.setdefault(name.lower() if insensitive else name, []).insert(0, MacroDefinition(
                            minimum, maximum, body, insensitive, defaults, greedy,
                            body_locations, name, self._macro_definition_serial))
                elif directive == "%rep":
                    repetitions = self._pp_eval(" ".join(parts[1:]), definitions) if enabled else Value(0)
                    self._require(not repetitions.unresolved and repetitions.number >= 0, "invalid %rep count")
                    body = []
                    depth = 1
                    while index < len(raw_lines):
                        body_physical, body_line, body_frame, body_location = raw_lines[index]
                        index += 1
                        marker = _comment(body_line).strip().split(None, 1)[0].lower() if _comment(body_line).strip() else ""
                        if marker == "%line" and body_frame is None:
                            apply_line_directive(_comment(body_line).strip()[5:].lstrip(), body_physical)
                            continue
                        if marker == "%rep": depth += 1
                        elif marker == "%endrep":
                            depth -= 1
                            if depth == 0: break
                        body.append((body_physical, body_line, body_location or SourceLine(
                            body_line, logical_filename,
                            logical_anchor + (body_physical - physical_anchor) * line_increment)))
                    if depth: raise self._error("unterminated %rep")
                    self._require(repetitions.number * len(body) <= 1000000, "%rep expansion limit exceeded")
                    self._rep_serial += 1
                    serial = self._rep_serial
                    expansion = [
                        (body_physical, line, invocation_frame, location)
                        for _ in range(repetitions.number)
                        for body_physical, line, location in body
                    ]
                    if expansion:
                        expansion.insert(0, (physical_number, f"\x00rep_start:{serial}", invocation_frame, None))
                        expansion.append((physical_number, f"\x00rep_end:{serial}", invocation_frame, None))
                    raw_lines[index:index] = expansion
                elif directive == "%exitrep":
                    if enabled:
                        self._require(bool(rep_stack), "%exitrep outside %rep")
                        serial, conditional_depth = rep_stack.pop()
                        marker = f"\x00rep_end:{serial}"
                        ending = next((at for at in range(index, len(raw_lines))
                                       if raw_lines[at][1] == marker), None)
                        self._require(ending is not None, "invalid %rep expansion")
                        index = ending + 1
                        del active[conditional_depth:]
                elif directive == "%exitmacro":
                    if enabled:
                        self._require(invocation_frame is not None, "%exitmacro outside a macro")
                        while index < len(raw_lines) and raw_lines[index][2] is invocation_frame:
                            index += 1
                        del active[invocation_frame.conditional_depth:]
                        del rep_stack[invocation_frame.repetition_depth:]
                elif directive == "%rotate":
                    if enabled:
                        self._require(invocation_frame is not None, "%rotate requires a macro invocation")
                        rotation = self._pp_eval(" ".join(parts[1:]), definitions)
                        self._require(not rotation.unresolved, "%rotate needs a defined count")
                        arguments = invocation_frame.arguments
                        self._require(bool(arguments), "%rotate needs macro arguments")
                        offset = rotation.number % len(arguments)
                        invocation_frame.arguments = arguments[offset:] + arguments[:offset]
                elif enabled and directive == "%push":
                    self._require(len(parts) <= 2, "%push takes at most one context name")
                    self._context_serial += 1
                    self._context_stack.append((parts[1] if len(parts) == 2 else "", self._context_serial))
                elif enabled and directive == "%pop":
                    self._require(bool(self._context_stack), "%pop without %push")
                    self._require(len(parts) <= 2, "%pop takes at most one context name")
                    if len(parts) == 2:
                        self._require(parts[1] == self._context_stack[-1][0], "%pop context mismatch")
                    self._context_stack.pop()
                elif enabled and directive == "%repl":
                    self._require(bool(self._context_stack), "%repl without %push")
                    self._require(len(parts) == 2, "%repl requires a context name")
                    self._context_stack[-1] = (parts[1], self._context_stack[-1][1])
                elif directive in _PP_CONDITIONS:
                    if directive in ("%ifdifi", "%ifndifi"):
                        # NASM reserves this TASM spelling as COND_NEVER: it
                        # suppresses every branch, including an eventual %else.
                        active.append((False, True))
                    else:
                        condition = self._pp_condition(directive, " ".join(parts[1:]), definitions, macros) if enabled else False
                        active.append((enabled and condition, enabled and condition))
                elif directive.startswith("%elif") and "%if" + directive[5:] in _PP_CONDITIONS:
                    if not active: raise self._error("%elif without %if")
                    _, seen = active.pop()
                    parent = all(state[0] for state in active)
                    condition = False
                    invalid_condition = False
                    if parent and not seen:
                        if directive in ("%elifdifi", "%elifndifi"):
                            invalid_condition = True
                        else:
                            try:
                                condition = self._pp_condition(
                                    "%if" + directive[5:],
                                    self._expand_context_locals(" ".join(parts[1:])),
                                    definitions, macros)
                            except AssemblyError:
                                if directive not in ("%eliffile", "%elifnfile",
                                                     "%elifusable", "%elifnusable",
                                                     "%elifusing", "%elifnusing"):
                                    raise
                                invalid_condition = True
                    active.append((condition, seen or condition or invalid_condition))
                elif directive == "%else":
                    if not active: raise self._error("%else without %if")
                    _, seen = active.pop()
                    parent = all(state[0] for state in active)
                    active.append((parent and not seen, True))
                elif directive == "%endif":
                    if not active: raise self._error("%endif without %if")
                    active.pop()
                elif enabled and directive in ("%define", "%idefine", "%xdefine", "%ixdefine", "%assign", "%iassign"):
                    if len(parts) < 2: raise self._error(f"{directive} requires a name")
                    if len(parts) < 3 and directive in ("%assign", "%iassign"):
                        raise self._error(f"{directive} requires a value")
                    body_text = parts[2] if len(parts) >= 3 else ""
                    definition_name = self._expand_indirection(parts[1], definitions)
                    function = re.fullmatch(r"([A-Za-z_.$?@][\w.$?@~#]*)\(([^()]*)\)",
                                            definition_name)
                    if function:
                        self._require(directive in ("%define", "%idefine", "%xdefine", "%ixdefine"),
                                      "function macro requires %define")
                        parameters = self._parse_smacro_parameters(function.group(2))
                        protected = frozenset(parameter.name for parameter in parameters
                                              if parameter.name)
                        body = (self._expand_define(body_text, definitions, protected)
                                if directive in ("%xdefine", "%ixdefine") else
                                self._expand_indirection(body_text, definitions,
                                                         protected))
                        macro_name = self._resolve_alias(function.group(1))
                        self._location_macros_enabled.discard(macro_name)
                        insensitive = directive in ("%idefine", "%ixdefine")
                        same_plain = (macro_name.lower() in self._case_insensitive_definitions
                                      if insensitive else macro_name in definitions)
                        self._require(not same_plain,
                                      f"macro `{macro_name}' defined both with and without parameters")
                        self._store_smacro_definition(macro_name, parameters, body,
                                                      insensitive=insensitive)
                        continue
                    if directive in ("%define", "%idefine"):
                        value = self._expand_indirection(body_text, definitions)
                    elif directive in ("%xdefine", "%ixdefine"): value = self._expand_define(body_text, definitions)
                    else:
                        evaluated = self._pp_eval(body_text, definitions)
                        self._require(not evaluated.unresolved, f"{directive} needs a defined expression")
                        value = str(evaluated.number)
                    macro_name = self._resolve_alias(definition_name)
                    self._location_macros_enabled.discard(macro_name)
                    insensitive = directive in ("%idefine", "%ixdefine", "%iassign")
                    same_function = (macro_name.lower() in self._case_insensitive_functions
                                     if insensitive else macro_name in self._function_definitions)
                    self._require(not same_function,
                                  f"macro `{macro_name}' defined both with and without parameters")
                    if directive in ("%idefine", "%ixdefine"):
                        self._case_insensitive_definitions[macro_name.lower()] = value
                        self._case_insensitive_definition_names[macro_name.lower()] = macro_name
                        self._smacro_definition_serial += 1
                        self._case_insensitive_plain_orders[macro_name.lower()] = self._smacro_definition_serial
                    else:
                        definitions[macro_name] = value
                        self._smacro_definition_serial += 1
                        self._plain_definition_orders[macro_name] = self._smacro_definition_serial
                elif enabled and directive in ("%defalias", "%idefalias"):
                    alias_name = (self._expand_indirection(parts[1], definitions)
                                  if len(parts) >= 2 else "")
                    target_name = (self._expand_indirection(parts[2], definitions)
                                   if len(parts) >= 3 else "")
                    self._require(len(parts) == 3 and
                                  re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", target_name) is not None,
                                  f"{directive} needs an alias and macro identifier")
                    if directive == "%idefalias":
                        self._case_insensitive_aliases[alias_name.lower()] = target_name
                    else:
                        self._aliases[alias_name] = target_name
                elif enabled and directive == "%aliases":
                    self._require(len(parts) <= 2, "%aliases takes one option")
                    if len(parts) == 2:
                        option = parts[1].lower()
                        self._require(option in ("on", "off", "1", "0"), "invalid %aliases option")
                        self._aliases_enabled = option in ("on", "1")
                elif enabled and directive in ("%defstr", "%idefstr", "%deftok", "%ideftok",
                                                "%strcat", "%istrcat", "%strlen", "%istrlen",
                                                "%substr", "%isubstr", "%pathsearch", "%ipathsearch"):
                    self._require(len(parts) >= 2, f"{directive} requires a name")
                    raw_value = self._expand_define(parts[2] if len(parts) >= 3 else "", definitions)
                    tokens = _pp_tokens(raw_value)
                    if directive in ("%pathsearch", "%ipathsearch"):
                        self._require(bool(tokens) and len(tokens[0]) >= 2 and
                                      tokens[0][0] in "'\"`" and tokens[0][-1] == tokens[0][0],
                                      f"{directive} requires a quoted path")
                        path_name = string_bytes(tokens[0]).decode("latin-1")
                        candidates = [Path(path_name)] + [p / path_name for p in self.include_paths]
                        path = next((candidate for candidate in candidates if candidate.is_file()), None)
                        value = _quote_string(str(path)) if path is not None else tokens[0]
                    elif directive in ("%defstr", "%idefstr"):
                        value = _quote_string(raw_value)
                    elif directive in ("%strcat", "%istrcat"):
                        self._require(all(token == "," or
                                          (len(token) >= 2 and token[0] in "'\"`" and token[-1] == token[0])
                                          for token in tokens), f"{directive} requires strings")
                        content = b"".join(string_bytes(token) for token in tokens if token != ",")
                        value = _quote_string(content.decode("latin-1"))
                    else:
                        self._require(bool(tokens) and len(tokens[0]) >= 2 and
                                      tokens[0][0] in "'\"`" and tokens[0][-1] == tokens[0][0],
                                      f"{directive} requires a string")
                        content = string_bytes(tokens[0])
                        if directive in ("%deftok", "%ideftok"):
                            value = content.decode("latin-1")
                        elif directive in ("%strlen", "%istrlen"):
                            value = str(len(content))
                        else:
                            trailing = raw_value[raw_value.find(tokens[0]) + len(tokens[0]):].strip()
                            if trailing.startswith(","):
                                trailing = trailing[1:].strip()
                            operands = _split(trailing) if trailing else []
                            self._require(bool(operands) and bool(operands[0]),
                                          f"{directive} requires a starting index")
                            def first_expression(expression: str) -> Value:
                                try:
                                    return self._pp_eval(expression, definitions)
                                except AssemblyError:
                                    # NASM evaluates one expression and ignores any later
                                    # tokens on the same side of a comma.
                                    boundaries = [match.start() for match in re.finditer(r"\s+", expression)]
                                    for boundary in reversed(boundaries):
                                        try:
                                            return self._pp_eval(expression[:boundary], definitions)
                                        except AssemblyError:
                                            pass
                                    raise

                            start = first_expression(operands[0])
                            self._require(not start.unresolved, f"{directive} needs a known index")
                            count = (first_expression(operands[1]) if len(operands) > 1 and operands[1]
                                     else Value(1))
                            self._require(not count.unresolved, f"{directive} needs a known count")
                            offset = max(0, start.number - 1)
                            length = count.number
                            if length < 0:
                                length = len(content) + length + 1 - offset
                            value = _quote_string(content[offset:offset + max(0, length)].decode("latin-1"))
                    name = self._resolve_alias(
                        self._expand_indirection(parts[1], definitions))
                    self._location_macros_enabled.discard(name)
                    if directive.startswith("%i"):
                        self._case_insensitive_definitions[name.lower()] = value
                    else:
                        definitions[name] = value
                elif enabled and directive == "%use":
                    self._load_macro_package(parts, definitions, macros, lines, filename, number)
                elif enabled and directive in ("%error", "%fatal", "%warning", "%note"):
                    message = self._expand_define(" ".join(parts[1:]), definitions).strip()
                    if len(message) >= 2 and message[0] == message[-1] and message[0] in "'\"`":
                        message = string_bytes(message).decode("latin-1")
                    message = message or directive
                    if directive in ("%error", "%fatal"):
                        raise self._error(message)
                    if directive == "%note" or self._warning_user_enabled:
                        warnings.warn(f"{filename}:{number}: {message}", stacklevel=2)
                elif enabled and directive == "%null":
                    pass
                elif enabled and directive == "%pragma":
                    # NASM forwards non-preproc namespaces to the assembler.
                    # For flat binary output, unknown pragma namespaces and
                    # options have no emitted bytes.
                    pragma = self._expand_define(" ".join(parts[1:]), definitions).split()
                    if (len(pragma) >= 2 and pragma[0].lower() == "preproc" and
                            pragma[1].lower() == "sane_empty_expansion"):
                        setting = pragma[2].lower() if len(pragma) >= 3 else "yes"
                        if setting in ("yes", "true", "on"):
                            self._sane_empty_expansion = True
                        elif setting in ("no", "false", "off"):
                            self._sane_empty_expansion = False
                        else:
                            try:
                                value = self._pp_eval(" ".join(pragma[2:]), definitions)
                            except AssemblyError:
                                pass
                            else:
                                if not value.unresolved:
                                    self._sane_empty_expansion = bool(value.number)
                elif enabled and directive == "%stacksize":
                    self._require(len(parts) >= 2, "%stacksize missing size parameter")
                    mode = parts[1].lower()
                    stack_modes = {
                        "flat": (4, "ebp", 8), "flat64": (8, "rbp", 16),
                        "large": (2, "bp", 4), "small": (2, "bp", 6),
                    }
                    self._require(mode in stack_modes, "%stacksize invalid size type")
                    self._stack_slot_size, self._stack_pointer, self._arg_offset = stack_modes[mode]
                    self._local_offset = 0
                    self._stacksize_explicit = True
                elif enabled and directive in ("%arg", "%local"):
                    self._define_stack_arguments(directive, parts, definitions)
                elif enabled and directive == "%clear":
                    self._clear_macros(parts, definitions, macros)
                elif enabled and directive == "%undef":
                    if len(parts) < 2: raise self._error("%undef requires a name")
                    name = self._resolve_alias(
                        self._expand_indirection(parts[1], definitions))
                    definitions.pop(name, None)
                    self._plain_definition_orders.pop(name, None)
                    self._location_macros_enabled.discard(name)
                    self._case_insensitive_definitions.pop(name.lower(), None)
                    self._case_insensitive_plain_orders.pop(name.lower(), None)
                    self._case_insensitive_definition_names.pop(name.lower(), None)
                    self._function_definitions.pop(name, None)
                    self._case_insensitive_functions.pop(name.lower(), None)
                elif enabled and directive == "%undefalias":
                    self._require(len(parts) >= 2, "%undefalias requires a name")
                    name = self._expand_indirection(parts[1], definitions)
                    removed = self._aliases.pop(name, None)
                    removed = self._case_insensitive_aliases.pop(name.lower(), None) or removed
                    if removed is None:
                        definitions.pop(name, None)
                        self._plain_definition_orders.pop(name, None)
                        self._case_insensitive_definitions.pop(name.lower(), None)
                        self._case_insensitive_plain_orders.pop(name.lower(), None)
                        self._case_insensitive_definition_names.pop(name.lower(), None)
                        self._function_definitions.pop(name, None)
                        self._case_insensitive_functions.pop(name.lower(), None)
                elif enabled and directive in ("%unmacro", "%unimacro"):
                    self._require(len(parts) >= 3, f"{directive} requires a name and parameter count")
                    expanded_name = self._expand_indirection(parts[1], definitions)
                    self._require(re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", expanded_name) is not None,
                                  f"{directive} expects a macro name")
                    name = expanded_name.lower() if directive == "%unimacro" else expanded_name
                    count_match = re.fullmatch(
                        r"(\d+)(?:-(\d+|\*))?(\+)?(?:\.nolist)?(?:\s+.*)?",
                        parts[2].strip())
                    self._require(count_match is not None, "invalid %unmacro parameter count")
                    minimum = int(count_match.group(1))
                    maximum = (1_000_000 if count_match.group(2) == "*" else int(count_match.group(2))) if count_match.group(2) else minimum
                    self._require(minimum <= maximum,
                                  "minimum parameter count exceeds maximum")
                    greedy = bool(count_match.group(3))
                    definitions_for_name = macros.get(name, [])
                    macros[name] = [definition for definition in definitions_for_name
                                    if not (definition.minimum == minimum and
                                            definition.maximum == maximum and
                                            definition.greedy == greedy and
                                            definition.case_insensitive == (directive == "%unimacro") and
                                            (definition.name is None or definition.name == expanded_name or
                                             directive == "%unimacro"))]
                    if not macros[name]:
                        macros.pop(name, None)
                    if directive == "%unimacro" and name in {
                            "struc", "endstruc", "istruc", "at", "iend"}:
                        standard_bounds = {"struc": (1, 2), "endstruc": (0, 0),
                                           "istruc": (1, 1), "at": (1, 2), "iend": (0, 0)}[name]
                        if (minimum, maximum) == standard_bounds:
                            self._disabled_standard_macros.add(name)
                elif enabled and directive == "%depend":
                    expanded = self._expand_define(" ".join(parts[1:]), definitions).strip()
                    tokens = _pp_tokens(expanded)
                    self._require(bool(tokens) and len(tokens[0]) >= 2 and
                                  tokens[0][0] in "'\"`" and tokens[0][-1] == tokens[0][0],
                                  "%depend requires a quoted path")
                elif enabled and directive in ("%include", "%require"):
                    if len(parts) < 2: raise self._error(f"{directive} requires a path")
                    expanded = self._expand_define(" ".join(parts[1:]), definitions).strip()
                    if self.compatibility == "nasm3":
                        tokens = _pp_tokens(expanded)
                        self._require(bool(tokens) and len(tokens[0]) >= 2 and
                                      tokens[0][0] in "'\"`" and tokens[0][-1] == tokens[0][0],
                                      "%include requires a quoted path")
                        path_name = string_bytes(tokens[0]).decode("latin-1").replace("\\", "/")
                        candidates = [Path(path_name)] + [p / path_name for p in self.include_paths]
                    else:
                        path_name = expanded.strip("'\"").replace("\\", "/")
                        candidates = [Path(source_filename).parent / path_name] + [
                            p / path_name for p in self.include_paths]
                        if source_filename != "<string>":
                            candidates.append(Path(source_filename).parent.parent / path_name)
                    path = next((p for p in candidates if p.is_file()), None)
                    if path is None:
                        if directive == "%require":
                            continue
                        raise self._error(f"include file not found: {path_name}")
                    canonical_path = path.resolve()
                    if directive == "%include" or canonical_path not in self._included_paths:
                        self._included_paths.add(canonical_path)
                        lines.extend(self._read_source(path.read_text(encoding="latin-1"), str(canonical_path), definitions, stack, macros))
                elif directive in ("%endmacro", "%endm"):
                    raise self._error(f"{directive} without %macro")
                elif directive == "%endrep":
                    raise self._error("%endrep without %rep")
                elif enabled: raise self._error(f"unsupported preprocessor directive {directive}")
            elif all(state[0] for state in active):
                original_raw = raw
                expanded = self._expand_define(raw, definitions)
                rest = _comment(expanded).strip()
                dollarhex_directive = re.fullmatch(
                    r"(?is)\[\s*dollarhex(?:\s+(.*?))?\s*\]", rest)
                if dollarhex_directive:
                    self._set_dollarhex(dollarhex_directive.group(1) or "", definitions)
                float_directive = re.fullmatch(r"(?is)\[\s*float(?:\s+(.*?))?\s*\]", rest)
                if float_directive:
                    self._set_float_option(float_directive.group(1) or "")
                float_macro = re.fullmatch(r"(?is)float\s+(.+)", rest)
                if float_macro:
                    for option in _split(float_macro.group(1)):
                        self._set_float_option(option)
                    definitions["__?FLOAT_DAZ?__"] = "daz" if self._float_daz else "nodaz"
                    definitions["__?FLOAT_ROUND?__"] = self._float_rounding
                warning_directive = re.fullmatch(r"(?i)\[warning\s+([^\]]+)\]", rest)
                if warning_directive:
                    setting = warning_directive.group(1).strip().lower()
                    if setting == "push":
                        self._warning_stack.append(self._warning_user_enabled)
                    elif setting == "pop":
                        if self._warning_stack:
                            self._warning_user_enabled = self._warning_stack.pop()
                        else:
                            warnings.warn(f"{filename}:{number}: warning stack empty", stacklevel=2)
                            self._warning_user_enabled = True
                    elif setting in ("-user", "+user", "*user"):
                        self._warning_user_enabled = setting != "-user"
                    else:
                        raise self._error(f"unsupported warning setting {setting}")
                    continue
                leading_labels = []
                while True:
                    label = re.match(r"^([A-Za-z_.$?@][\w.$?@~#]*)\s*:\s*(.*)$", rest)
                    if not label: break
                    leading_labels.append(label.group(1) + ":")
                    rest = label.group(2).strip()
                uncolonized = re.match(r"^([A-Za-z_.$?@][\w.$?@~#]*)\s+([A-Za-z_.$?@][\w.$?@~#]*)(?:\s+(.*))?$", rest)
                if uncolonized and uncolonized.group(1).lower() not in KNOWN_MNEMONICS:
                    possible_macro = uncolonized.group(2)
                    if self._macro_candidates(possible_macro, macros):
                        leading_labels.append(uncolonized.group(1) + ":")
                        rest = possible_macro + (" " + uncolonized.group(3) if uncolonized.group(3) else "")
                invocation = re.match(r"^([A-Za-z_.$?@][\w.$?@~#]*)\s*(.*)$", rest)
                candidates = []
                if invocation:
                    key = invocation.group(1)
                    candidates = self._macro_candidates(key, macros)
                if candidates:
                    argument_text = invocation.group(2)
                    arguments = ([_unbrace_macro_argument(item) for item in _split(argument_text, macro=True)]
                                 if argument_text.strip() else [])
                    reported_count = None
                    macro = next((definition for definition in candidates
                                  if definition.minimum <= len(arguments) and
                                  (definition.greedy or len(arguments) <= definition.maximum)), None)
                    trailing_empty = bool(arguments) and argument_text.rstrip().endswith(",")
                    if trailing_empty and not self._sane_empty_expansion:
                        if macro is None:
                            macro = next((definition for definition in candidates
                                          if definition.minimum <= len(arguments) - 1 and
                                          (definition.greedy or len(arguments) - 1 <= definition.maximum)), None)
                            if macro is not None:
                                arguments.pop()
                        elif (len(arguments) > macro.minimum and
                              len(arguments) <= macro.minimum + len(macro.defaults)):
                            arguments[-1] = macro.defaults[len(arguments) - macro.minimum - 1]
                        elif not (macro.greedy and len(arguments) > macro.maximum):
                            arguments.pop()
                    if macro is None and not arguments:
                        original_call = re.match(
                            r"^([A-Za-z_.$?@][\w.$?@~#]*)\s+(.+)$",
                            _comment(original_raw).strip())
                        if (not self._sane_empty_expansion and original_call and
                                original_call.group(1) == key):
                            macro = next((definition for definition in candidates
                                          if definition.minimum <= 1 and
                                          (definition.greedy or 1 <= definition.maximum)), None)
                            if macro is not None:
                                arguments = [""]
                                reported_count = 0
                    if macro is None and not arguments:
                        if not invocation.group(2).strip():
                            lines.append(SourceLine(" ".join(leading_labels + [f"{key}:"]),
                                                    filename, number))
                            continue
                    self._require(macro is not None, "wrong macro argument count")
                    if macro.greedy and len(arguments) > macro.maximum:
                        arguments = arguments[:macro.maximum - 1] + [
                            ",".join(arguments[macro.maximum - 1:])]
                    self._require(len(arguments) <= macro.maximum, "wrong macro argument count")
                    if macro.defaults and len(arguments) < macro.maximum:
                        offset = max(0, len(arguments) - macro.minimum)
                        arguments.extend(macro.defaults[offset:offset + macro.maximum - len(arguments)])
                    self._macro_serial += 1
                    self._require(self._macro_serial <= 10000, "macro expansion limit exceeded")
                    invocation_label = leading_labels[-1][:-1] if leading_labels else None
                    if key.lower() == "segment" and "masm" in self._loaded_packages:
                        definitions["__?SECT?__"] = (
                            f"[segment {invocation_label or ''} {invocation.group(2).strip()}]")
                    frame = MacroInvocation(arguments, f"..@{self._macro_serial}.",
                                            len(active), len(rep_stack), invocation_label,
                                            reported_count, key, macro.name or key)
                    consumes_label = any(re.search(r"%00(?![0-9])", body_line)
                                         for body_line in macro.body)
                    if leading_labels and not consumes_label:
                        lines.append(SourceLine(" ".join(leading_labels), filename, number))
                    raw_lines[index:index] = [
                        (physical_number, body_line, frame,
                         macro.locations[at] if macro.locations is not None else None)
                        for at, body_line in enumerate(macro.body)
                    ]
                else:
                    standard = invocation.group(1).lower() if invocation else ""
                    if (standard in ("struc", "endstruc", "istruc", "at", "iend") and
                            standard not in self._disabled_standard_macros):
                        arguments = _split(invocation.group(2)) if invocation.group(2).strip() else []
                        if leading_labels:
                            lines.append(SourceLine(" ".join(leading_labels), filename, number))
                        if standard == "struc":
                            self._require(1 <= len(arguments) <= 2, "STRUC needs a name")
                            name = arguments[0]
                            self._structure_definitions.append(name)
                            lines.append(SourceLine(f"[absolute {arguments[1] if len(arguments) == 2 else '0'}]",
                                                    filename, number))
                            lines.append(SourceLine(f"{name}:", filename, number))
                        elif standard == "endstruc":
                            self._require(not arguments and bool(self._structure_definitions),
                                          "ENDSTRUC without STRUC")
                            name = self._structure_definitions.pop()
                            lines.append(SourceLine(f"{name}_size equ ($-{name})", filename, number))
                            lines.append(SourceLine(definitions.get("__?SECT?__") or "[section .text]",
                                                    filename, number))
                        elif standard == "istruc":
                            self._require(len(arguments) == 1, "ISTRUC needs a structure name")
                            self._structure_serial += 1
                            start = f"..@struct{self._structure_serial}"
                            self._structure_instances.append((arguments[0], start))
                            lines.append(SourceLine(f"{start}:", filename, number))
                        elif standard == "at":
                            self._require(bool(arguments) and bool(self._structure_instances),
                                          "AT requires ISTRUC")
                            name, start = self._structure_instances[-1]
                            member = arguments[0]
                            target = name + member if member.startswith(".") else member
                            lines.append(SourceLine(f"times ({target}-{name})-($-{start}) db 0",
                                                    filename, number))
                            if len(arguments) > 1:
                                lines.append(SourceLine(",".join(arguments[1:]), filename, number))
                        else:
                            self._require(not arguments and bool(self._structure_instances),
                                          "IEND without ISTRUC")
                            name, start = self._structure_instances.pop()
                            lines.append(SourceLine(f"times {name}_size-($-{start}) db 0",
                                                    filename, number))
                        continue
                    align_mode = re.match(r"(?i)^alignmode\s+(.+)$", rest)
                    if (align_mode and "smartalign" in self._loaded_packages and
                            "alignmode" not in self._disabled_standard_macros):
                        parameters = _split(align_mode.group(1))
                        mode_name = parameters[0].lower()
                        if mode_name in _SMARTALIGN_16 and len(parameters) <= 2:
                            threshold = (parameters[1] if len(parameters) == 2 and parameters[1]
                                         else str(_SMARTALIGN_DEFAULT_THRESHOLD[mode_name]))
                            if threshold.lower() == "nojmp":
                                threshold = "-1"
                            definitions["__?ALIGN_JMP_THRESHOLD?__"] = threshold
                            definitions["__?ALIGNMODE?__"] = f"{parameters[0]},{threshold}"
                            if mode_name != "k7":
                                definitions["__?ALIGN_16BIT_GROUP?__"] = str(len(_SMARTALIGN_16[mode_name]) - 1)
                    user_section = re.match(r"(?i)^(section|segment)\s+(.+)$", rest)
                    if user_section:
                        definitions["__?SECT?__"] = f"[{user_section.group(1)} {user_section.group(2)}]"
                    user_absolute = re.match(r"(?i)^absolute\s+(.+)$", rest)
                    if user_absolute:
                        definitions["__?SECT?__"] = f"[absolute {user_absolute.group(1)}]"
                    section_alignment = re.match(r"(?i)^sectalign\s+(on|off)\s*$", rest)
                    if section_alignment:
                        definitions["__?SECTALIGN_ALIGN_UPDATES_SECTION?__"] = (
                            "1" if section_alignment.group(1).lower() == "on" else "0")
                    lines.append(SourceLine(expanded, filename, number))
                    candidate = _comment(expanded).strip()
                    label = re.match(r"^([A-Za-z_.$?@][\w.$?@~#]*)\s*:\s*(.*)$", candidate)
                    if label and not self._pp_code_seen:
                        self._pp_known_labels[label.group(1)] = self._pp_origin
                    remaining = label.group(2).strip() if label else candidate
                    org = re.match(r"(?i)^org\s+(.+)$", remaining)
                    if org:
                        origin = self._pp_eval(org.group(1), definitions)
                        if not origin.unresolved: self._pp_origin = origin.number
                    equ = re.match(r"(?i)^\s*([A-Za-z_.$?@][\w.$?@~#]*)\s*:?\s+equ\b\s*(.+)$", candidate)
                    if equ:
                        value = self._pp_eval(equ.group(2), definitions,
                                              defer_location=self.compatibility == 'nasm3')
                        if not value.unresolved: self._pp_symbols[equ.group(1)] = value.number
                    elif (remaining and not org and not dollarhex_directive and
                          not float_directive and not float_macro and
                          not re.match(r"(?i)^(?:bits|cpu|use16|section|segment|global)\b", remaining)):
                        self._pp_code_seen = True
        if active: raise AssemblyError("unterminated %if", filename)
        return lines
