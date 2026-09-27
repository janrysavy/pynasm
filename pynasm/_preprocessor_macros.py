"""Macro expansion and conditional preprocessor expressions."""

from __future__ import annotations

from ._assembler_syntax import *


class MacroExpansionMixin:
    @staticmethod
    def _macro_candidates(name: str, macros: dict[str, list[MacroDefinition]]) -> list[MacroDefinition]:
        keys = (name,) if name == name.lower() else (name, name.lower())
        candidates = (definition for key in keys for definition in macros.get(key, ())
                      if definition.case_insensitive or definition.name is None or
                      definition.name == name)
        return sorted(candidates, key=lambda definition: definition.order, reverse=True)

    def _pp_condition(self, directive: str, arguments: str,
                      definitions: dict[str, str], macros: dict[str, list[MacroDefinition]]) -> bool:
        if directive in ("%ifusable", "%ifnusable", "%ifusing", "%ifnusing"):
            tokens = _pp_tokens(self._expand_define(arguments, definitions))
            self._require(bool(tokens) and
                          (tokens[0][0] in "'\"`" or
                           re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", tokens[0]) is not None),
                          f"{directive} requires a package name")
            package = (string_bytes(tokens[0]).decode("latin-1")
                       if tokens[0][0] in "'\"`" else tokens[0]).lower()
            found = (package in _NASM_USE_PACKAGES if "usable" in directive else
                     package in self._loaded_packages)
            return not found if directive in ("%ifnusable", "%ifnusing") else found
        if directive in ("%ifdirective", "%ifndirective"):
            tokens = _pp_tokens(self._expand_define(arguments, definitions))
            candidate = tokens[0] if tokens else ""
            if candidate and candidate[0] in "'\"`":
                candidate = string_bytes(candidate).decode("latin-1")
            elif candidate == "%" and len(tokens) > 1:
                candidate += tokens[1]
            if candidate.startswith("["):
                candidate = candidate[1:].lstrip()
            if candidate.startswith("%"):
                found = candidate.lower() in _NASM_PP_DIRECTIVES
            else:
                found = candidate.split(None, 1)[0].lower() in _NASM_DIRECTIVES if candidate else False
            return found if directive == "%ifdirective" else not found
        if directive in ("%ifctx", "%ifnctx"):
            names = _pp_tokens(arguments)
            self._require(all(re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", name)
                              for name in names), f"{directive} expects context identifiers")
            current = self._context_stack[-1][0].lower() if self._context_stack else None
            matches = current is not None and any(name.lower() == current for name in names)
            return matches if directive == "%ifctx" else not matches
        if directive in ("%ifenv", "%ifnenv"):
            tokens = _pp_tokens(self._expand_define(arguments, definitions,
                                                    expand_environment=False))
            names = []
            index = 0
            while index < len(tokens):
                if tokens[index:index + 2] == ["%", "!"]:
                    index += 2
                self._require(index < len(tokens), f"{directive} expects environment variable names")
                token = tokens[index]
                if token and token[0] in "'\"`" and token[-1] == token[0]:
                    names.append(string_bytes(token).decode("latin-1"))
                else:
                    self._require(re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", token) is not None,
                                  f"{directive} expects environment variable names")
                    names.append(token)
                index += 1
            exists = any(name in os.environ for name in names)
            return exists if directive == "%ifenv" else not exists
        if directive in ("%iffile", "%ifnfile"):
            tokens = _pp_tokens(self._expand_define(arguments, definitions))
            self._require(bool(tokens) and len(tokens[0]) >= 2 and
                          tokens[0][0] in "'\"`" and tokens[0][-1] == tokens[0][0],
                          f"{directive} requires a quoted path")
            filename = string_bytes(tokens[0]).decode("latin-1")
            exists = Path(filename).is_file()
            return exists if directive == "%iffile" else not exists
        if directive in ("%ifdef", "%ifndef"):
            names = _pp_tokens(self._expand_indirection(arguments, definitions))
            self._require(all(re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", name)
                              for name in names), f"{directive} expects macro identifiers")
            exists = False
            for name in names:
                name = self._resolve_alias(name)
                if (name in definitions or name.lower() in self._case_insensitive_definitions or
                    name in self._function_definitions or
                        name.lower() in self._case_insensitive_functions):
                    exists = True
                    break
            return exists if directive == "%ifdef" else not exists
        if directive in ("%ifdefalias", "%ifndefalias"):
            names = _pp_tokens(self._expand_indirection(arguments, definitions))
            self._require(all(re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", name)
                              for name in names), f"{directive} expects macro identifiers")
            exists = any(name in self._aliases or name.lower() in self._case_insensitive_aliases
                         for name in names)
            return exists if directive == "%ifdefalias" else not exists
        if directive in ("%ifidn", "%ifnidn", "%ifidni", "%ifnidni"):
            tokens = _pp_tokens(self._expand_define(arguments, definitions))
            self._require("," in tokens, f"{directive} requires two arguments")
            separator = tokens.index(",")
            left, right = tokens[:separator], tokens[separator + 1:]
            equal = bool(left and right)
            if equal:
                for first, second in zip(left, right):
                    self._require(second != ",", f"{directive} has more than one comma")
                    first_string = first[0] in "'\"`"
                    second_string = second[0] in "'\"`"
                    if first_string != second_string:
                        equal = False
                        break
                    first_text = string_bytes(first) if first_string else first.encode("latin-1")
                    second_text = string_bytes(second) if second_string else second.encode("latin-1")
                    if directive.endswith("i"):
                        first_text, second_text = first_text.lower(), second_text.lower()
                    if first_text != second_text:
                        equal = False
                        break
                else:
                    equal = len(left) == len(right)
            return equal if directive in ("%ifidn", "%ifidni") else not equal
        if directive in ("%ifmacro", "%ifnmacro"):
            name, _, count = arguments.partition(" ")
            name = self._expand_indirection(name, definitions)
            self._require(re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", name) is not None,
                          f"{directive} expects a macro name")
            minimum = 0
            maximum = 1_000_000
            if count.strip():
                count = self._expand_define(count, definitions).lstrip()
                first = re.match(r"[0-9][\w]*", count)
                self._require(first is not None, f"{directive} expects a parameter count or nothing")
                try:
                    minimum = maximum = _number(first.group())
                except ExpressionError:
                    raise self._error(f"{directive} expects a parameter count or nothing") from None
                self._require(minimum is not None, f"{directive} expects a parameter count or nothing")
                remaining = count[first.end():]
                if remaining.startswith("-"):
                    remaining = remaining[1:]
                    if remaining.startswith("*"):
                        maximum = 1_000_000
                        remaining = remaining[1:]
                    else:
                        last = re.match(r"[0-9][\w]*", remaining)
                        self._require(last is not None,
                                      f"{directive} expects a parameter count after '-'")
                        try:
                            maximum = _number(last.group())
                        except ExpressionError:
                            raise self._error(f"{directive} expects a parameter count after '-'") from None
                        self._require(maximum is not None,
                                      f"{directive} expects a parameter count after '-'")
                        self._require(minimum <= maximum,
                                      "minimum parameter count exceeds maximum")
                        remaining = remaining[last.end():]
                if remaining.startswith("+"):
                    maximum = 1_000_000
            declarations = [definition for definition in self._macro_candidates(name, macros)
                            if definition.name is None or definition.name == name]
            if not declarations:
                standard_counts = {"struc": (1, 2), "endstruc": (0, 0),
                                   "istruc": (1, 1), "at": (1, 2), "iend": (0, 0)}
                bounds = (standard_counts.get(name.lower())
                          if name.lower() not in self._disabled_standard_macros else None)
                if bounds is not None:
                    declarations = [MacroDefinition(*bounds, [], True, [],
                                                    name.lower() == "at")]
            exists = any((minimum <= definition.maximum or definition.greedy) and
                         maximum >= definition.minimum
                         for definition in declarations)
            return exists if directive == "%ifmacro" else not exists
        if directive in ("%ifid", "%ifnid", "%ifnum", "%ifnnum", "%ifstr", "%ifnstr",
                         "%iftoken", "%ifntoken", "%ifempty", "%ifnempty"):
            tokens = _pp_tokens(self._expand_define(arguments, definitions))
            kind = directive[3:]
            negate = directive in ("%ifnid", "%ifnnum", "%ifnstr", "%ifntoken", "%ifnempty")
            if negate: kind = kind[1:]
            if kind == "empty": result = not tokens
            elif kind == "token": result = len(tokens) == 1
            elif kind == "str": result = bool(tokens) and tokens[0][0] in "'\"`"
            elif kind == "id":
                result = (bool(tokens) and tokens[0] not in ("$", "$$") and
                          bool(re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", tokens[0])))
                if result:
                    try: result = _number(tokens[0]) is None
                    except ExpressionError: result = False
            else:
                at = 0
                while at < len(tokens) and tokens[at] in ("+", "-"):
                    at += 1
                try: result = at < len(tokens) and _number(tokens[at]) is not None
                except ExpressionError: result = False
            return not result if negate else result
        evaluated = self._pp_eval(arguments, definitions, allow_trailing=True)
        self._require(not evaluated.unresolved, f"{directive} needs a defined expression")
        result = bool(evaluated.number & 0xFFFFFFFFFFFFFFFF)
        return not result if directive == "%ifn" else result
    def _expand_indirection(self, text: str, definitions: dict[str, str],
                            protected: frozenset[str] = frozenset(),
                            depth: int = 0,
                            active: frozenset[tuple[object, ...]] = frozenset()) -> str:
        if "%[" not in text:
            return text
        self._require(depth < 32, "recursive macro indirection")
        output: list[str] = []
        index = 0
        while index < len(text):
            if text[index] == ";":
                output.append(text[index:])
                break
            if text[index] in "'\"`":
                quote = text[index]
                end = index + 1
                while end < len(text):
                    if text[end] == quote and (quote != "`" or text[end - 1] != "\\"):
                        end += 1
                        break
                    end += 1
                output.append(text[index:end])
                index = end
                continue
            if not text.startswith("%[", index):
                output.append(text[index])
                index += 1
                continue
            level = 1
            end = index + 2
            while end < len(text) and level:
                if text[end] in "'\"`":
                    quote = text[end]
                    end += 1
                    while end < len(text):
                        if text[end] == quote and (quote != "`" or text[end - 1] != "\\"):
                            end += 1
                            break
                        end += 1
                    continue
                if text[end] == "[":
                    level += 1
                elif text[end] == "]":
                    level -= 1
                end += 1
            self._require(level == 0, "unterminated %[...] macro indirection")
            inner = text[index + 2:end - 1]
            output.append(self._expand_define(inner, definitions, protected,
                                              _indirection_depth=depth + 1,
                                              _active=active))
            index = end
        return "".join(output)

    def _expand_define(self, text: str, definitions: dict[str, str],
                       protected: frozenset[str] = frozenset(), *,
                       expand_environment: bool = True,
                       _indirection_depth: int = 0,
                       _active: frozenset[tuple[object, ...]] = frozenset(),
                       _depth: int = 0) -> str:
        if re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", text):
            current = text
            active = set(_active)
            for _ in range(10000):
                if current in protected:
                    return current
                target = self._resolve_alias(current)
                plain = self._plain_smacro_replacement(current, target, definitions)
                if plain is None:
                    return target
                replacement, macro_id = plain
                if macro_id in active:
                    return current
                active.add(macro_id)
                if re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", replacement):
                    current = replacement
                    continue
                return self._expand_define(
                    replacement, definitions, protected,
                    expand_environment=expand_environment,
                    _indirection_depth=_indirection_depth,
                    _active=frozenset(active), _depth=_depth + 1)
            raise self._error("macro expansion depth exceeded")
        self._require(_depth < 512, "macro expansion depth exceeded")
        text = self._expand_indirection(text, definitions, protected,
                                        _indirection_depth, _active)
        if expand_environment:
            text, _ = _expand_environment(text)
        output: list[str] = []
        index = 0
        while index < len(text):
            char = text[index]
            if char in "'\"`":
                end = index + 1
                while end < len(text):
                    if text[end] == char and (char != "`" or text[end - 1] != "\\"):
                        end += 1
                        break
                    end += 1
                output.append(text[index:end])
                index = end
                continue
            if char == ";":
                output.append(text[index:])
                break
            match = re.match(r"[A-Za-z_.$?@][\w.$?@~#]*", text[index:])
            if not match or (index and re.match(r"[\w.$?@~#]", text[index - 1])):
                output.append(char)
                index += 1
                continue
            token = match.group()
            opening = index + len(token)
            if token in protected or text[max(0, index - 2):index] == "%!":
                output.append(token)
                index = opening
                continue
            target = self._resolve_alias(token)
            candidates = (self._function_definitions.get(target, []) +
                          self._case_insensitive_functions.get(target.lower(), []))
            plain_order = max(self._plain_definition_orders.get(target, 0),
                              self._case_insensitive_plain_orders.get(target.lower(), 0))
            if candidates and plain_order > max(item.order for item in candidates):
                candidates = []
            builtin_float = target.lower().replace("?", "").startswith(
                ("__float", "__bfloat"))
            if (candidates or builtin_float) and opening < len(text) and text[opening] == "(":
                depth = 1
                closing = opening + 1
                quote = None
                while closing < len(text) and depth:
                    current = text[closing]
                    if quote:
                        if current == quote and (quote != "`" or text[closing - 1] != "\\"):
                            quote = None
                    elif current in "'\"`":
                        quote = current
                    elif current == "(":
                        depth += 1
                    elif current == ")":
                        depth -= 1
                    closing += 1
                self._require(depth == 0, f"unterminated {token} macro call")
                raw_arguments = text[opening + 1:closing - 1]
                arguments = (_split_smacro_arguments(raw_arguments, strip=False)
                             if raw_arguments else [])
                if builtin_float:
                    float_arguments = [_unbrace_macro_argument(item.strip())
                                       for item in arguments]
                    self._require(len(float_arguments) == 1,
                                  f"{token} requires one argument")
                    try:
                        value = float_operator(target, float_arguments[0],
                                               rounding=self._float_rounding,
                                               daz=self._float_daz)
                    except ValueError as exc:
                        raise self._error(str(exc)) from exc
                    self._require(value is not None,
                                  f"unknown floating-point operator {token}")
                    output.append(str(value))
                else:
                    count = len(arguments) if raw_arguments else 1
                    definition = next((candidate for candidate in sorted(
                        candidates, key=lambda item: item.order, reverse=True)
                        if count == len(candidate.parameters) or
                        (candidate.parameters[-1].greedy and
                         count >= len(candidate.parameters) - 1)), None)
                    self._require(definition is not None,
                                  f"wrong {token} macro argument count")
                    macro_id = ("function", definition.order)
                    if macro_id in _active:
                        output.append(token)
                        index = opening
                        continue
                    body = self._expand_function_call(
                        token, definition, arguments, definitions,
                        _active | {macro_id}, _depth + 1)
                    output.append(self._expand_define(
                        body, definitions, protected,
                        expand_environment=expand_environment,
                        _active=_active | {macro_id}, _depth=_depth + 1))
                index = closing
                continue
            plain = self._plain_smacro_replacement(token, target, definitions)
            if plain is None:
                output.append(target)
                index = opening
                continue
            replacement, macro_id = plain
            if macro_id in _active:
                output.append(token)
            else:
                output.append(self._expand_define(
                    replacement, definitions, protected,
                    expand_environment=expand_environment,
                    _active=_active | {macro_id}, _depth=_depth + 1))
            index = opening
        return "".join(output)

    def _resolve_alias(self, name: str) -> str:
        if not self._aliases_enabled:
            return name
        seen: set[str] = set()
        while name not in seen:
            seen.add(name)
            target = self._aliases.get(name, self._case_insensitive_aliases.get(name.lower()))
            if target is None:
                return name
            name = target
        raise self._error("macro alias loop")

    def _parse_smacro_parameters(self, source: str) -> list[SmacroParameter]:
        parameters: list[SmacroParameter] = []
        items = source.split(",") if source else [""]
        for index, item in enumerate(items):
            name = ""
            greedy = evaluate_arg = no_strip = unsigned = False
            quote = 0
            radix = ""
            after_slash = False
            for token in re.findall(r"&&|[=&!+/]|[A-Za-z_.$?@][\w.$?@~#]*|\s+|.", item):
                if token.isspace():
                    continue
                if after_slash:
                    self._require(re.fullmatch(r"[A-Za-z]+", token) is not None,
                                  "invalid macro parameter radix")
                    for letter in token:
                        if letter.lower() in "bydotqhx":
                            radix = letter
                        elif letter.lower() == "u":
                            unsigned = True
                        elif letter.lower() == "s":
                            unsigned = False
                        else:
                            raise self._error("invalid macro parameter radix")
                    after_slash = False
                elif token == "=":
                    evaluate_arg = True
                elif token == "&":
                    quote = max(quote, 1)
                elif token == "&&":
                    quote = 2
                elif token == "!":
                    no_strip = True
                elif token == "+":
                    greedy = True
                elif token == "/":
                    self._require(evaluate_arg, "radix specifier requires '='")
                    after_slash = True
                elif re.fullmatch(r"[A-Za-z_.$?@][\w.$?@~#]*", token):
                    self._require(not name, "duplicate macro parameter identifier")
                    name = token
                else:
                    raise self._error("invalid macro parameter template")
            self._require(not after_slash, "invalid macro parameter radix")
            self._require(not greedy or index == len(items) - 1,
                          "greedy macro parameter must be last")
            parameters.append(SmacroParameter(name, greedy, evaluate_arg, quote,
                                               no_strip, radix, unsigned))
        named = [parameter.name for parameter in parameters if parameter.name]
        self._require(len(named) == len(set(named)), "duplicate macro parameter")
        return parameters

    def _format_smacro_number(self, value: int, parameter: SmacroParameter) -> str:
        unsigned_value = value & 0xffffffffffffffff
        signed_value = (unsigned_value - 0x10000000000000000
                        if unsigned_value & 0x8000000000000000 else unsigned_value)
        magnitude = (unsigned_value if parameter.unsigned else abs(signed_value))
        sign = "-" if signed_value < 0 and not parameter.unsigned else ""
        if not parameter.radix:
            return sign + str(magnitude)
        base = {"b": 2, "y": 2, "o": 8, "q": 8, "d": 10, "t": 10,
                "h": 16, "x": 16}[parameter.radix.lower()]
        if base == 2:
            digits = format(magnitude, "b")
        elif base == 8:
            digits = format(magnitude, "o")
        elif base == 16:
            digits = format(magnitude, "X" if parameter.radix.isupper() else "x")
        else:
            digits = str(magnitude)
        return sign + "0" + parameter.radix + digits

    def _store_smacro_definition(self, name: str, parameters: list[SmacroParameter],
                                 body: str, *, insensitive: bool = False) -> None:
        self._smacro_definition_serial += 1
        definition = SmacroDefinition(parameters, body, name, insensitive,
                                     self._smacro_definition_serial)
        table = (self._case_insensitive_functions if insensitive else
                 self._function_definitions)
        table.setdefault(name.lower() if insensitive else name, []).insert(0, definition)

    def _plain_smacro_replacement(self, token: str, target: str,
                                  definitions: dict[str, str]) -> tuple[str, tuple[object, ...]] | None:
        if target in definitions:
            return (_expand_smacro_self_reference(definitions[target], token, target),
                    ("plain", self._plain_definition_orders.get(target, 0), target))
        if target.lower() in self._case_insensitive_definitions:
            return (_expand_smacro_self_reference(
                        self._case_insensitive_definitions[target.lower()], token,
                        self._case_insensitive_definition_names.get(target.lower(), target)),
                    ("plain-insensitive",
                     self._case_insensitive_plain_orders.get(target.lower(), 0),
                     target.lower()))
        return None

    def _expand_function_call(self, name: str, definition: SmacroDefinition,
                              raw_arguments: list[str], definitions: dict[str, str],
                              active: frozenset[tuple[object, ...]], depth: int) -> str:
        parameters, body = definition.parameters, definition.body
        greedy = parameters[-1].greedy
        arguments = raw_arguments
        if greedy:
            self._require(len(arguments) >= len(parameters) - 1,
                          f"wrong {name} macro argument count")
            tail = arguments[len(parameters) - 1:]
            if not parameters[-1].no_strip:
                tail = [_unbrace_macro_argument(item.strip()) for item in tail]
            arguments = arguments[:len(parameters) - 1] + [",".join(tail)]
        elif not arguments and len(parameters) == 1:
            arguments = [""]
        self._require(len(arguments) == len(parameters),
                      f"wrong {name} macro argument count")
        replacements: dict[str, str] = {}
        expanded: dict[str, str] = {}
        for parameter, raw_argument in zip(parameters, arguments):
            argument = (_collapse_unquoted_whitespace(raw_argument)
                        if parameter.no_strip else
                        _unbrace_macro_argument(raw_argument.strip()))
            if parameter.evaluate or parameter.quote or "%," in body:
                expanded_argument = self._expand_define(
                    argument, definitions, _active=active, _depth=depth + 1)
            else:
                expanded_argument = argument
            if parameter.evaluate and (argument or not parameter.greedy):
                value = self._pp_eval(expanded_argument, definitions)
                self._require(not value.unresolved,
                              f"non-constant macro parameter {parameter.name}")
                argument = self._format_smacro_number(value.number, parameter)
                expanded_argument = argument
            if parameter.quote:
                quoted = (_pp_tokens(expanded_argument) if parameter.quote == 2 else [])
                if not (len(quoted) == 1 and quoted[0][0] in "'\"`" and
                        quoted[0][-1] == quoted[0][0]):
                    expanded_argument = _quote_string(expanded_argument)
                argument = expanded_argument
            if parameter.name:
                key = (parameter.name.lower() if definition.case_insensitive else
                       parameter.name)
                replacements[key] = argument
                expanded[key] = expanded_argument
        body = _substitute_smacro_arguments(body, replacements, expanded,
                                            definition.case_insensitive)
        body = _expand_smacro_self_reference(body, name, definition.name)
        return re.sub(r"\s*%\+\s*", "", body)

    def _expand_context_locals(self, source: str) -> str:
        code = _comment(source)
        pieces = re.split(r"('[^']*'|\"[^\"]*\"|`(?:[^`\\]|\\.)*`)", code)
        def replace(match: re.Match[str]) -> str:
            depth = len(match.group(1))
            self._require(depth <= len(self._context_stack), "context stack underflow")
            serial = self._context_stack[-depth][1]
            return f"..@{serial}.{match.group(2)}"
        for index in range(0, len(pieces), 2):
            pieces[index] = re.sub(r"(?<!%)%(\$+)([A-Za-z_.$?@][\w.$?@~#]*)", replace, pieces[index])
        return "".join(pieces) + source[len(code):]
