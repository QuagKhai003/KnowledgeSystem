import ast
from pathlib import Path


def parse_code(file_path: str) -> dict:
    """Parse a Python source file into structural AST representation."""
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")

    if file_path.endswith(".py"):
        return _parse_python(file_path, text)

    # For JS/TS files, return basic structure until tree-sitter is configured
    return _parse_basic(file_path, text)


def _parse_python(file_path: str, source: str) -> dict:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {
            "parser_source": "python_ast",
            "file_path": file_path,
            "error": "SyntaxError",
            "imports": [],
            "classes": [],
            "functions": [],
        }

    imports = _extract_imports(tree)
    classes = _extract_classes(tree)
    functions = _extract_functions(tree)

    return {
        "parser_source": "python_ast",
        "file_path": file_path,
        "imports": imports,
        "classes": classes,
        "functions": functions,
    }


def _extract_imports(tree: ast.Module) -> list[dict]:
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({
                    "module": alias.name,
                    "alias": alias.asname,
                    "line": node.lineno,
                })
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append({
                    "module": f"{module}.{alias.name}",
                    "alias": alias.asname,
                    "line": node.lineno,
                })
    return imports


def _extract_classes(tree: ast.Module) -> list[dict]:
    classes = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            bases = [_name_of(b) for b in node.bases]
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                    methods.append({
                        "name": item.name,
                        "args": [a.arg for a in item.args.args if a.arg != "self"],
                        "line_bounds": [item.lineno, item.end_lineno],
                        "decorators": [_name_of(d) for d in item.decorator_list],
                    })
            classes.append({
                "name": node.name,
                "bases": bases,
                "line_bounds": [node.lineno, node.end_lineno],
                "methods": methods,
                "decorators": [_name_of(d) for d in node.decorator_list],
            })
    return classes


def _extract_functions(tree: ast.Module) -> list[dict]:
    functions = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
                "line_bounds": [node.lineno, node.end_lineno],
                "decorators": [_name_of(d) for d in node.decorator_list],
                "returns": _annotation_str(node.returns),
            })
    return functions


def _name_of(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name_of(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return _name_of(node.func)
    return ast.dump(node)


def _annotation_str(node) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_name_of(node.value)}.{node.attr}"
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return ast.dump(node)


def _parse_basic(file_path: str, source: str) -> dict:
    """Basic line-count structure for non-Python files."""
    lines = source.splitlines()
    return {
        "parser_source": "basic_text",
        "file_path": file_path,
        "line_count": len(lines),
        "imports": [],
        "classes": [],
        "functions": [],
    }
