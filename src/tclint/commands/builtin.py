"""Parse-time handling of Tcl's builtin commands.

Note that the following commands are not currently supported. If support for any of
these would be helpful for your use case, please file an issue.

- Anything related to TclOO:
  - https://www.tcl.tk/man/tcl/TclCmd/my.html
  - https://www.tcl.tk/man/tcl/TclCmd/next.html
  - https://www.tcl.tk/man/tcl/TclCmd/class.html
  - https://www.tcl.tk/man/tcl/TclCmd/copy.html
  - https://www.tcl.tk/man/tcl/TclCmd/define.html
  - https://www.tcl.tk/man/tcl/TclCmd/object.html
  - https://www.tcl.tk/man/tcl/TclCmd/self.html

- Things that are imported via `package require`
  - https://www.tcl.tk/man/tcl/TclCmd/dde.html
  - https://www.tcl.tk/man/tcl/TclCmd/http.html
  - https://www.tcl.tk/man/tcl/TclCmd/msgcat.html
  - https://www.tcl.tk/man/tcl/TclCmd/platform.html
  - https://www.tcl.tk/man/tcl/TclCmd/platform_shell.html
  - https://www.tcl.tk/man/tcl/TclCmd/transchan.html
  - https://www.tcl.tk/man/tcl/TclCmd/tcltest.html

- Tcl library commands: https://www.tcl.tk/man/tcl/TclCmd/library.html

- The "unknown" command: https://www.tcl.tk/man/tcl/TclCmd/unknown.html

- Math ops:
  - https://www.tcl.tk/man/tcl/TclCmd/mathfunc.html
  - https://www.tcl.tk/man/tcl/TclCmd/mathop.html
"""

from tclint.commands.utils import (
    CommandArgError,
    check_count,
    subcommands,
    eval,
)


def _check_code(arg):
    """Check 'code' argument used by return and try."""

    val = arg.contents
    if val is None:
        return

    try:
        int(val)
    except ValueError:
        pass
    else:
        return

    if val in {"ok", "error", "return", "break", "continue"}:
        return

    raise CommandArgError(
        f"got {val}, expected one of ok, error, return, break, continue, or an integer"
    )


def _after(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/after.html

    script_arg = []
    if len(args) > 1:
        script_arg = eval(args[1:], parser, "after")

    return args[0:1] + script_arg


def _after_cancel(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/after.html
    check_count("after cancel", 1, None)

    # TODO: raise warning about not checking code

    return None


def _after_idle(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/after.html
    return eval(args, parser, "after idle")


def _apply(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/apply.html
    if len(args) < 1:
        raise CommandArgError(
            f"not enough args to apply: got {len(args)}, expected at least 1"
        )

    func_list = parser.parse_list(args[0])
    list_len = len(func_list.children)
    if list_len < 2 or list_len > 3:
        raise CommandArgError(
            f"Invalid first argument to apply: got list of {list_len} elements,"
            " expected 2 or 3"
        )

    body = parser.parse_script(func_list.children[1])
    func_list.children[1] = body

    return [func_list] + args[1:]


def _catch(args, parser):
    if len(args) < 1:
        raise CommandArgError(
            f"not enough args to catch: got {len(args)}, expected at least 1"
        )
    if len(args) > 3:
        raise CommandArgError(
            f"too many args to catch: got {len(args)}, expected no more than 3"
        )

    return [parser.parse_script(args[0])] + args[1:]


def _dict_filter(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/dict.html#M8

    if len(args) < 2:
        raise CommandArgError(
            f"not enough args to 'dict filter': got {len(args)}, expected at least 2"
        )

    if args[1].contents not in {"key", "script", "value"}:
        raise CommandArgError(
            "invalid argument to 'dict filter': expected filter type to be one of key,"
            " script, or value"
        )

    if args[1].contents == "script":
        kv_pair = parser.parse_list(args[2])
        list_len = len(kv_pair.children)
        if len(kv_pair.children) != 2:
            raise CommandArgError(
                "invalid argument to 'dict filter': expected list of 2 elements in"
                f" second-to-last argument, got {list_len}"
            )
        return args[0:2] + [kv_pair, parser.parse_script(args[3])]

    return None


def _dict_map_for(cmd):
    def check(args, parser):
        if len(args) != 3:
            raise CommandArgError(
                f"wrong # of args to '{cmd}': got {len(args)}, expected 3"
            )

        # TODO: might be worth checking that arg[0] is a pair?

        return args[0:2] + [parser.parse_script(args[2])]

    return check


def _dict_update(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/dict.html#M25

    if len(args) < 4:
        raise CommandArgError(
            f"not enough args to 'dict update': got {len(args)}, expected at least 4"
        )

    if len(args) % 2 != 0:
        raise CommandArgError(
            "invalid # of args to 'dict update': expected an even number"
        )

    return args[0:-1] + [parser.parse_script(args[-1])]


def _dict_with(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/dict.html#M27

    if len(args) < 2:
        raise CommandArgError(
            f"not enough args to 'dict with': got {len(args)}, expected at least 2"
        )

    return args[0:-1] + [parser.parse_script(args[-1])]


def _eval(args, parser):
    return eval(args, parser, "eval")


def _expr(args, parser):
    if len(args) == 0:
        raise CommandArgError("not enough args to 'expr': got 0, expected at least 1")

    if len(args) == 1 and args[0].contents is not None:
        # this method will handle the `node.contents is None` case fine, but
        # will throw an error. We'll instead pass thru silently, since that error
        # will be caught by a separate lint check.
        return [parser.parse_expression(args[0])]

    # TODO: handle multiple args
    return None


def _fileevent(args, parser):
    # ref: https://www.tcl.tk/man/tcl8.4/TclCmd/fileevent.html
    # TODO: implement
    raise CommandArgError(
        "argument parsing for 'fileevent' not implemented, script argument will not be"
        " checked for violations"
    )


def _for(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/for.html
    if len(args) != 4:
        raise CommandArgError(f"wrong # of args to for: got {len(args)}, expected 4")

    return [
        parser.parse_script(args[0]),
        parser.parse_expression(args[1]),
        parser.parse_script(args[2]),
        parser.parse_script(args[3]),
    ]


def _foreach(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/foreach.html
    if len(args) < 3:
        raise CommandArgError(
            f"insufficient args to foreach: got {len(args)}, expected at least 3"
        )

    # last argument is script body
    return args[0:-1] + [parser.parse_script(args[-1])]


def _if(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/if.html
    # TODO: make arg checking strict

    new_args = []

    new_args.append(parser.parse_expression(args[0]))

    while len(new_args) < len(args):
        arg = args[len(new_args)]

        if arg.contents == "then" or arg.contents == "else":
            new_args.append(arg)
            continue
        if arg.contents == "elseif":
            new_args.append(arg)
            new_args.append(parser.parse_expression(args[len(new_args)]))
            continue

        arg = parser.parse_script(arg)
        new_args.append(arg)

    return new_args


def _interp_eval(args, parser):
    if len(args) < 2:
        raise CommandArgError(
            f"not enough args to 'interp eval': got {len(args)}, expected at least 2"
        )
    return args[0:1] + eval(args[1:], parser, "interp eval")


def _lmap(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/lmap.html
    if len(args) < 3:
        raise CommandArgError(
            f"not enough args to lmap: got {len(args)}, expected at least 3"
        )

    return args[:-1] + [parser.parse_script(args[-1])]


def _namespace_code(args, parser):
    # ref: https://www.tcl.tk/man/tcl8.4/TclCmd/namespace.html#M6
    # TODO: seems like a possible pattern is to execute things in these scripts
    # with additional args provided, so command-args checks within this might
    # actually be false positive. will keep as-is for now though.
    return [parser.parse_script(args[0])]


def _namespace_eval(args, parser):
    if len(args) < 2:
        raise CommandArgError(
            f"not enough args to 'namespace eval': got {len(args)}, expected at least 2"
        )
    return args[0:1] + eval(args[1:], parser, "namespace eval")


def _namespace_inscope(args, parser):
    # ref: https://www.tcl.tk/man/tcl8.4/TclCmd/namespace.html#M14
    raise CommandArgError(
        "'namespace inscope' is not meant to be called directly, consider using"
        " 'namespace code' or 'namespace eval' instead"
    )


def _package_ifneeded(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/package.html

    # TODO: implement

    # one issue with this one - it seems like calls to package ifneeded are
    # often generated by pkg_MkIndex and these calls won't lint clean. Probably
    # need a special case to ensure that these don't generate violations

    raise CommandArgError(
        "argument parsing for 'package ifneeded' not implemented, any script argument"
        " will not be checked for violations"
    )


def _proc(args, parser):
    if len(args) != 3:
        raise CommandArgError(f"wrong # of args to proc: got {len(args)}, expected 3")

    return args[0:2] + [parser.parse_script(args[2])]


def _return(args, parser):
    args = list(args)
    while len(args) > 0:
        option = args.pop(0).contents

        try:
            if option == "-code":
                arg = args.pop(0)
                try:
                    _check_code(arg)
                except CommandArgError as e:
                    raise CommandArgError(f"invalid value for return -code: {e}")
            elif option == "-level":
                val = args.pop(0).contents

                if val is None:
                    continue

                try:
                    if int(val) >= 0:
                        continue
                except ValueError:
                    pass

                raise CommandArgError(
                    f"invalid value for return -level: got {val}, expected a"
                    " non-negative integer"
                )
            elif option in {"-errorcode", "-errorinfo", "-errorstack", "-options"}:
                args.pop(0)
            else:
                break
        except IndexError:
            raise CommandArgError(
                f"insufficient args to return: expected value after {option}"
            )

    if len(args) > 0:
        raise CommandArgError(
            "too many arguments to return: expected no more than 1 argument after"
            " explicit options. Provide -options argument if you intend to specify"
            " additional return options."
        )

    return None


def _switch(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/switch.html
    # This one's complicated...

    # TODO: better checking of malformed switch command

    arg_contents = [arg.contents for arg in args]
    arg_i = 0

    try:
        arg_i = arg_contents.index("--") + 1
    except ValueError:
        while True:
            contents = args[arg_i].contents
            if contents in {"-exact", "-glob", "-regexp", "-nocase"}:
                arg_i += 1
            elif contents in {"-matchvar", "-indexvar"}:
                arg_i += 2
            else:
                break

    # accounts for string to be matched
    arg_i += 1

    new_args = args[0:arg_i]

    # one argument left => form where patterns and bodies are in list
    last_arg_is_list = arg_i == len(args) - 1

    if last_arg_is_list:
        pattern_and_commands_list = parser.parse_list(args[arg_i])
        new_args.append(pattern_and_commands_list)
        pattern_and_commands = pattern_and_commands_list.children
    else:
        pattern_and_commands = args[arg_i:]

    if len(pattern_and_commands) % 2 != 0:
        raise CommandArgError("Expected even number of patterns and commands")

    parsed_patterns_and_commands = []
    for i, node in enumerate(pattern_and_commands):
        if i % 2 == 0:
            parsed_patterns_and_commands.append(node)
        else:
            parsed_patterns_and_commands.append(parser.parse_script(node))

    if last_arg_is_list:
        pattern_and_commands_list.children = parsed_patterns_and_commands
    else:
        new_args.extend(parsed_patterns_and_commands)

    return new_args


def _time(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/time.html
    if len(args) < 1:
        raise CommandArgError(
            f"not enough args to time: got {len(args)}, expected at least 1"
        )

    if len(args) > 2:
        raise CommandArgError(
            f"too many args to time: got {len(args)}, expected no more than 2"
        )

    if len(args) == 2:
        time = args[1].contents
        if time is not None:
            try:
                int(time)
            except ValueError:
                raise CommandArgError(
                    "invalid argument to time: expected integer for last argument"
                )

    return [parser.parse_script(args[0])] + args[1:]


def _timerate(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/timerate.html
    # timerate doesn't seem to be implemented in tclsh 8.6 for me - why?

    args = list(args)
    new_args = []

    while True:
        try:
            arg = args.pop(0)
        except IndexError:
            raise CommandArgError("invalid arguments to timerate: expected script body")

        if arg.contents in {"-direct", "-calibrate"}:
            new_args.append(arg)
        elif arg.contents in {"-overhead"}:
            new_args.append(arg)
            try:
                val = args.pop(0)
                if val.contents is not None:
                    float(val.contents)
            except (ValueError, IndexError, TypeError):
                raise CommandArgError(
                    "invalid argument to timerate: -overhead must be followed by a"
                    " double"
                )
            new_args.append(val)
        else:
            break

    new_args.append(parser.parse_script(arg))

    if len(args) > 2:
        raise CommandArgError(
            "too many arguments to timerate: expected no more than 2 arguments"
            " following script body"
        )

    try:
        [int(arg.contents) for arg in args]
    except ValueError:
        raise CommandArgError(
            "invalid argument to timerate: expected one or two integers following"
            " script body"
        )

    return new_args + args


def _try(args, parser):
    # ref: https://www.tcl.tk/man/tcl/TclCmd/try.html
    args = list(args)
    new_args = []

    while True:
        try:
            arg = args.pop(0)
        except IndexError:
            raise CommandArgError("invalid arguments to try: missing script body")
        new_args.append(parser.parse_script(arg))

        try:
            arg = args.pop(0)
        except IndexError:
            break

        new_args.append(arg)

        if arg.contents == "on":
            try:
                code = args.pop(0)
                try:
                    _check_code(code)
                except CommandArgError as e:
                    raise CommandArgError(
                        f"invalid code argument to 'on' handler in try: {e}"
                    )
                new_args.append(code)
                new_args.append(args.pop(0))
            except IndexError:
                raise CommandArgError(
                    "invalid arguments to try: expected 3 arguments after 'on' handler"
                )
        elif arg.contents == "trap":
            try:
                new_args.append(args.pop(0))
                new_args.append(args.pop(0))
            except IndexError:
                raise CommandArgError(
                    "invalid arguments to try: expected 3 arguments after 'trap'"
                    " handler"
                )
        elif arg.contents == "finally":
            continue
        else:
            raise CommandArgError(
                "invalid handler argument to try: expected one of 'on', 'trap', or"
                " 'finally'"
            )

    return new_args


def _while(args, parser):
    if len(args) != 2:
        raise CommandArgError(f"wrong # of args to while: got {len(args)}, expected 2")

    return [
        parser.parse_expression(args[0]),
        parser.parse_script(args[1]),
    ]


commands = {
    "after": subcommands(
        "after",
        {
            "cancel": _after_cancel,
            "idle": _after_idle,
            "info": check_count("after info", 0, 1),
        },
        default=_after,
    ),
    "append": check_count("append", 1, None),
    "apply": _apply,
    # TODO: check subcommands
    "array": check_count("array", None, None),
    "binary": subcommands(
        "binary",
        {
            "decode": check_count("binary decode", 2, None),
            "encode": check_count("binary encode", 2, None),
            "format": check_count("binary format", 1, None),
            "scan": check_count("binary scan", 2, None),
        },
    ),
    "break": check_count("break", 0, 0),
    "catch": _catch,
    "cd": check_count("cd", 0, 1),
    # TODO: check subcommands
    "chan": check_count("chan"),
    # TODO: check subcommands
    "clock": check_count("clock"),
    "close": check_count("close", 1, 2),
    "concat": check_count("concat"),
    "continue": check_count("continue", 0, 0),
    "coroutine": check_count("coroutine", 2, None),
    "dict": subcommands(
        "dict",
        {
            "append": check_count("dict append", 2, None),
            "create": check_count("dict create"),
            "exists": check_count("dict exists", 2, None),
            "filter": _dict_filter,
            "for": _dict_map_for("dict for"),
            "get": check_count("dict get", 1, None),
            "incr": check_count("dict incr", 2, 3),
            "info": check_count("dict info", 1, 1),
            "keys": check_count("dict keys", 1, 2),
            "lappend": check_count("dict lappend", 2, None),
            "map": _dict_map_for("dict map"),
            "merge": check_count("dict merge"),
            "remove": check_count("dict remove", 1, None),
            "replace": check_count("dict replace", 1, None),
            "set": check_count("dict set", 3, None),
            "size": check_count("dict size", 1, 1),
            "unset": check_count("dict unset", 2, None),
            "update": _dict_update,
            "values": check_count("dict values", 1, 2),
            "with": _dict_with,
        },
    ),
    "encoding": subcommands(
        "encoding",
        {
            "convertfrom": check_count("encoding convertfrom", 1, 2),
            "convertto": check_count("encoding convertto", 1, 2),
            "dirs": check_count("encoding dirs", 0, 1),
            "names": check_count("encoding names", 0, 0),
            "system": check_count("encoding system", 0, 1),
        },
    ),
    "eof": check_count("eof", 1, 1),
    "error": check_count("error", 1, 3),
    "eval": _eval,
    "exec": check_count("exec", 1, None),
    "exit": check_count("exit", 0, 1),
    "expr": _expr,
    "fblocked": check_count("fblocked", 1, 1),
    "fconfigure": check_count("fconfigure", 1, None),
    "fcopy": check_count("fcopy", 2, 6),
    # TODO: check subcommands
    "file": check_count("file", 1, None),
    "fileevent": _fileevent,
    "flush": check_count("flush", 1, 1),
    "for": _for,
    "foreach": _foreach,
    "format": check_count("format", 1, None),
    "gets": check_count("gets", 1, 2),
    "glob": check_count("glob"),
    "global": check_count("global"),
    "history": check_count("history"),
    "if": _if,
    "incr": check_count("incr", 1, 2),
    # TODO: check subcommands
    "info": check_count("info", 1, None),
    # TODO: check other subcommands
    "interp": subcommands(
        "interp",
        {
            "eval": _interp_eval,
        },
        default=check_count("interp", 1, None),
    ),
    "join": check_count("join", 1, 2),
    "lappend": check_count("lappend", 1, None),
    "lassign": check_count("lassign", 1, None),
    "lindex": check_count("lindex", 1, None),
    "linsert": check_count("linsert", 2, None),
    "list": check_count("list", 0, None),
    "llength": check_count("llength", 1, 1),
    "lrepeat": check_count("lrepeat", 1, None),
    "lreplace": check_count("lreplace", 3, None),
    "lreverse": check_count("lreverse", 1, 1),
    "lset": check_count("lset", 2, None),
    "lsort": check_count("lsort", 1, None),
    "lmap": _lmap,
    "load": check_count("load", 1, 6),
    "lrange": check_count("lrange", 3, 3),
    "lsearch": check_count("lsearch", 2, None),
    "memory": subcommands(
        "memory",
        {
            "active": check_count("memory active", 1, 1),
            "break_on_malloc": check_count("memory break_on_malloc", 1, 1),
            "info": check_count("memory info", 0, 0),
            # just on or off
            "init": check_count("memory init", 1, 1),
            "objs": check_count("memory objs", 1, 1),
            "onexit": check_count("memory onexit", 1, 1),
            "tag": check_count("memory tag", 1, 1),
            # just on or off
            "trace": check_count("memory trace", 1, 1),
            "trace_on_at_malloc": check_count("memory trace_on_at_malloc", 1, 1),
            # just on or off
            "validate": check_count("memory validate", 1, 1),
        },
    ),
    "namespace": subcommands(
        "namespace",
        {
            "children": check_count("namespace children", 0, 2),
            "code": _namespace_code,
            "current": check_count("namespace current", 0, 0),
            "delete": None,
            "eval": _namespace_eval,
            "exists": check_count("namespace exists", 1, 1),
            "export": None,
            "forget": None,
            "import": None,
            "inscope": _namespace_inscope,
            "origin": check_count("namespace origin", 1, 1),
            "parent": check_count("namespace parent", 0, 1),
            "qualifiers": check_count("namespace qualifiers", 1, 1),
            "tail": check_count("namespace tail", 1, 1),
            "which": check_count("namespace which", 1, 2),
            "ensemble": subcommands(
                "namespace ensemble",
                {
                    "create": None,
                    "configure": check_count("namespace ensemble configure", 1, None),
                    "exists": check_count("namespace ensemble exists", 1, 1),
                },
            ),
        },
    ),
    "open": check_count("open", 1, 3),
    "package": subcommands(
        "package",
        {
            "forget": None,
            "ifneeded": _package_ifneeded,
            "names": check_count("package names", 0, 0),
            "present": check_count("package present", 0, None),
            "provide": check_count("package provide", 1, 2),
            "require": check_count("package require", 1, None),
            "unknown": check_count("package unknown", 1, None),
            "vcompare": check_count("package vcompare", 2, 2),
            "versions": check_count("package versions", 1, 1),
            "vsatisfies": check_count("package vsatisfies", 2, None),
            "prefer": check_count("package prefer", 1, 1),
        },
    ),
    "pid": check_count("pid", 0, 1),
    "pkg::create": check_count("pkg::create", 2, None),
    "pkg_mkIndex": check_count("pkg_mkIndex", 1, None),
    "proc": _proc,
    "puts": check_count("puts", 1, 3),
    "pwd": check_count("pwd", 0, 0),
    "read": check_count("read", 1, 2),
    "regexp": check_count("regexp", 2, None),
    "regsub": check_count("regsub", 3, None),
    "rename": check_count("rename", 2, 2),
    "return": _return,
    # TODO: check subcommands
    "safe": check_count("safe", 1, None),
    "scan": check_count("scan", 2, None),
    "seek": check_count("seek", 2, 3),
    "set": check_count("set", 1, 2),
    "socket": check_count("socket", 2, None),
    "source": check_count("source", 1, 3),
    "split": check_count("split", 1, 2),
    # TODO: check subcommands
    "string": check_count("string", 2, None),
    "subst": check_count("subst", 1, 4),
    "switch": _switch,
    "tailcall": check_count("tailcall", 1, None),
    "tcl::prefix": subcommands(
        "tcl::prefix",
        {
            "all": check_count("tcl::prefix all", 2, 2),
            "longest": check_count("tcl::prefix longest", 2, 2),
            "match": check_count("tcl::prefix match", 2, None),
        },
    ),
    "tell": check_count("tell", 1, 1),
    "throw": check_count("throw", 2, 2),
    "time": _time,
    "timerate": _timerate,
    "tcl::tm::path": subcommands(
        "tcl::tm::path",
        {
            "add": check_count("tcl::tm::path add"),
            "remove": check_count("tcl::tm::path remove"),
            "list": check_count("tcl::tm::path list", 0, 0),
        },
    ),
    "tcl::tm::roots": check_count("tcl::tm::roots"),
    # TODO: check subcommands
    "trace": check_count("trace", 2, None),
    "try": _try,
    "unload": check_count("unload", 1, 6),
    "unset": check_count("unset"),
    "update": check_count("update", 0, 1),
    "uplevel": check_count("uplevel", 1, None),
    "upvar": check_count("upvar", 2, None),
    "variable": check_count("variable", 1, None),
    "vwait": check_count("vwait", 1, 1),
    "while": _while,
    "yield": check_count("yield", 0, 1),
    "yieldto": check_count("yieldto", 2, None),
    # TODO: check subcommands
    "zlib": check_count("zlib", 3, None),
}
