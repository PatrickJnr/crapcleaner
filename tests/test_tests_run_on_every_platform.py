"""The suite runs on Windows and on Linux, and CI runs both.

Twice now a test has reached for something that exists only on Windows, passed here,
and failed on the Linux runner - `subprocess.CREATE_NO_WINDOW` and `ctypes.windll`,
both of which are simply absent there. Checking by hand only works when someone
remembers, so this checks instead.

A test may still use these. It has to say so: reach for them through `getattr` with a
default, patch them with `create=True`, or skip the test where they do not exist.
"""

import ast
import pathlib

#: Attributes that exist on Windows only. Touching one directly raises AttributeError
#: on Linux before the assertion it belongs to is ever reached.
_WINDOWS_ONLY = {
    "subprocess": {"CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_CONSOLE", "STARTUPINFO"},
    "ctypes": {"windll", "WinDLL", "WinError"},
    "os": {"startfile"},
}

_TESTS = pathlib.Path(__file__).parent


def _skipped_lines(tree: ast.AST) -> set[int]:
    """Line numbers inside a function that skips itself where the attribute is absent."""
    covered: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any("skipif" in ast.dump(d) for d in node.decorator_list):
            covered.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return covered


def _created_lines(tree: ast.AST) -> set[int]:
    """Lines of a patch that passes create=True, which works whether or not it exists."""
    covered: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "create" and getattr(keyword.value, "value", False) is True:
                covered.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return covered


def _offences(path: pathlib.Path) -> list[str]:
    """Windows-only attributes reached without a guard, checked per use.

    Per use, not per file: a module with a skipif somewhere else in it is not thereby
    safe everywhere, which is exactly how one of these reached the Linux runner.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    excused = _skipped_lines(tree) | _created_lines(tree)

    found = []
    for node in ast.walk(tree):
        # patch.object(ctypes, "windll") names the attribute as a string, so it never
        # appears as an attribute access at all. This is the form that got through.
        if isinstance(node, ast.Call) and node.lineno not in excused:
            target = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if target == "object" and len(node.args) >= 2:
                named = getattr(node.args[1], "value", None)
                if isinstance(named, str) and any(
                    named in names for names in _WINDOWS_ONLY.values()
                ):
                    found.append(f"{path.name}:{node.lineno} patched {named!r} without create")

        if not isinstance(node, ast.Attribute) or node.lineno in excused:
            continue
        # Matches subprocess.X and sp.X alike: the module alias is not what matters,
        # the attribute name is.
        for module, names in _WINDOWS_ONLY.items():
            if node.attr not in names:
                continue
            base = node.value
            base_name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            if base_name and (base_name == module or base_name.startswith(module[:2])):
                found.append(f"{path.name}:{node.lineno} {base_name}.{node.attr}")
    return found


def test_no_test_reaches_for_a_windows_only_attribute_unguarded():
    offences = []
    for path in sorted(_TESTS.glob("test_*.py")):
        if path.name == pathlib.Path(__file__).name:
            continue
        offences.extend(_offences(path))

    assert not offences, (
        "these exist only on Windows and raise AttributeError on the Linux runner. "
        "Use getattr with a default, patch with create=True, or skip:\n  " + "\n  ".join(offences)
    )
