import ast
import re
from pathlib import Path


def parse_code(file_path: str) -> dict:
    """Parse a source file into structural representation with natural language extraction."""
    text = Path(file_path).read_text(encoding="utf-8", errors="replace")

    if file_path.endswith(".py"):
        return _parse_python(file_path, text)

    return _parse_generic_code(file_path, text)


def _parse_python(file_path: str, source: str) -> dict:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _parse_generic_code(file_path, source)

    imports = _extract_imports(tree)
    classes = _extract_classes(tree)
    functions = _extract_functions(tree)
    docstrings = _extract_docstrings(tree)
    comments = _extract_comments(source)

    return {
        "parser_source": "python_ast",
        "file_path": file_path,
        "raw_text": source,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "docstrings": docstrings,
        "comments": comments,
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


def _extract_docstrings(tree: ast.Module) -> list[str]:
    """Extract all docstrings from module, classes, and functions."""
    docs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node)
            if doc:
                docs.append(doc)
    return docs


def _extract_comments(source: str) -> list[str]:
    """Extract all # comments from source code."""
    comments = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if text and len(text) > 3:
                comments.append(text)
        elif "#" in stripped:
            idx = stripped.index("#")
            text = stripped[idx + 1:].strip()
            if text and len(text) > 3:
                comments.append(text)
    return comments


def _parse_generic_code(file_path: str, source: str) -> dict:
    """Parse any code file by extracting comments and identifier names."""
    comments = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            text = stripped.lstrip("/#").strip()
            if text and len(text) > 3:
                comments.append(text)
        if stripped.startswith("/*") or stripped.startswith("/**"):
            text = stripped.lstrip("/*").rstrip("*/").strip()
            if text and len(text) > 3:
                comments.append(text)

    return {
        "parser_source": "generic_code",
        "file_path": file_path,
        "raw_text": source,
        "imports": [],
        "classes": [],
        "functions": [],
        "docstrings": [],
        "comments": comments,
    }


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
    if isinstance(node, ast.Subscript):
        return f"{_annotation_str(node.value)}[{_annotation_str(node.slice)}]"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return f"{_annotation_str(node.left)} | {_annotation_str(node.right)}"
    if isinstance(node, ast.Tuple):
        return ", ".join(_annotation_str(e) or "" for e in node.elts)
    return ast.dump(node)
