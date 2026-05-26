"""Tree-sitter based code parser — structural extraction for 30+ languages."""

from pathlib import Path
from tree_sitter import Language, Parser, Node

_LANGUAGES: dict[str, Language] = {}
_GRAMMARS = {
    ".js": ("tree_sitter_javascript", "language"),
    ".jsx": ("tree_sitter_javascript", "language"),
    ".ts": ("tree_sitter_typescript", "language_typescript"),
    ".tsx": ("tree_sitter_typescript", "language_tsx"),
    ".go": ("tree_sitter_go", "language"),
    ".rs": ("tree_sitter_rust", "language"),
    ".java": ("tree_sitter_java", "language"),
    ".c": ("tree_sitter_c", "language"),
    ".h": ("tree_sitter_c", "language"),
    ".cpp": ("tree_sitter_cpp", "language"),
    ".cc": ("tree_sitter_cpp", "language"),
    ".cxx": ("tree_sitter_cpp", "language"),
    ".hpp": ("tree_sitter_cpp", "language"),
    ".cs": ("tree_sitter_c_sharp", "language"),
    ".rb": ("tree_sitter_ruby", "language"),
    ".sh": ("tree_sitter_bash", "language"),
    ".bash": ("tree_sitter_bash", "language"),
}

CLASS_TYPES = {
    "class_declaration", "class_definition", "interface_declaration",
    "struct_item", "struct_declaration", "struct_specifier",
    "impl_item", "enum_declaration", "enum_item",
    "type_declaration", "type_spec", "module",
}

FUNCTION_TYPES = {
    "function_declaration", "function_definition", "function_item",
    "method_declaration", "method_definition",
    "arrow_function", "generator_function_declaration",
}

IMPORT_TYPES = {
    "import_statement", "import_declaration", "use_declaration",
    "include_directive", "preproc_include",
}

COMMENT_TYPES = {"comment", "block_comment", "line_comment"}


def get_language(ext: str) -> Language | None:
    if ext in _LANGUAGES:
        return _LANGUAGES[ext]
    spec = _GRAMMARS.get(ext)
    if not spec:
        return None
    module_name, func_name = spec
    try:
        mod = __import__(module_name)
        lang = Language(getattr(mod, func_name)())
        _LANGUAGES[ext] = lang
        return lang
    except (ImportError, AttributeError, OSError):
        _LANGUAGES[ext] = None
        return None


def supports(ext: str) -> bool:
    return ext in _GRAMMARS


def parse_with_tree_sitter(file_path: str) -> dict | None:
    path = Path(file_path)
    ext = path.suffix.lower()
    lang = get_language(ext)
    if lang is None:
        return None

    source = path.read_text(encoding="utf-8", errors="replace")
    source_bytes = source.encode("utf-8")

    parser = Parser(lang)
    tree = parser.parse(source_bytes)
    root = tree.root_node

    classes = _extract_classes(root, source_bytes)
    functions = _extract_functions(root, source_bytes)
    imports = _extract_imports(root, source_bytes)
    comments = _extract_comments(root, source_bytes)

    return {
        "parser_source": f"tree_sitter_{ext.lstrip('.')}",
        "file_path": file_path,
        "raw_text": source,
        "imports": imports,
        "classes": classes,
        "functions": functions,
        "docstrings": [],
        "comments": comments,
    }


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _find_children_by_type(node: Node, types: set[str]) -> list[Node]:
    return [c for c in node.children if c.type in types]


def _find_all_by_type(node: Node, types: set[str], max_depth: int = 3) -> list[Node]:
    results = []
    _walk(node, types, results, 0, max_depth)
    return results


def _walk(node: Node, types: set[str], results: list, depth: int, max_depth: int):
    if depth > max_depth:
        return
    if node.type in types:
        results.append(node)
    for child in node.children:
        _walk(child, types, results, depth + 1, max_depth)


NAME_TYPES = {"identifier", "type_identifier", "name",
              "property_identifier", "field_identifier"}


def _get_name(node: Node, source: bytes) -> str:
    for child in node.children:
        if child.type in NAME_TYPES:
            return _text(child, source)
    return ""


def _extract_classes(root: Node, source: bytes) -> list[dict]:
    classes = []
    for node in _find_all_by_type(root, CLASS_TYPES, max_depth=2):
        name = _get_name(node, source)
        if not name:
            continue

        bases = _get_bases(node, source)
        methods = []
        for method in _find_all_by_type(node, FUNCTION_TYPES, max_depth=3):
            mname = _get_name(method, source)
            if mname:
                methods.append({
                    "name": mname,
                    "args": _get_params(method, source),
                    "line_bounds": [method.start_point.row + 1, method.end_point.row + 1],
                    "decorators": [],
                })

        classes.append({
            "name": name,
            "bases": bases,
            "line_bounds": [node.start_point.row + 1, node.end_point.row + 1],
            "methods": methods,
            "decorators": [],
        })
    return classes


def _extract_functions(root: Node, source: bytes) -> list[dict]:
    functions = []
    class_nodes = _find_all_by_type(root, CLASS_TYPES, max_depth=2)
    class_ranges = {(n.start_byte, n.end_byte) for n in class_nodes}

    for node in _find_all_by_type(root, FUNCTION_TYPES, max_depth=2):
        if _is_inside_ranges(node, class_ranges):
            continue

        name = _get_name(node, source)
        if not name:
            name = _get_arrow_name(node, source)
        if not name:
            continue

        functions.append({
            "name": name,
            "args": _get_params(node, source),
            "line_bounds": [node.start_point.row + 1, node.end_point.row + 1],
            "decorators": [],
            "returns": _get_return_type(node, source),
        })

    # Arrow functions assigned to variables (top-level)
    for node in root.children:
        if node.type in ("lexical_declaration", "variable_declaration"):
            for decl in node.children:
                if decl.type == "variable_declarator":
                    arrow = None
                    vname = ""
                    for child in decl.children:
                        if child.type in ("identifier", "name"):
                            vname = _text(child, source)
                        if child.type == "arrow_function":
                            arrow = child
                    if arrow and vname:
                        if not any(f["name"] == vname for f in functions):
                            functions.append({
                                "name": vname,
                                "args": _get_params(arrow, source),
                                "line_bounds": [node.start_point.row + 1, node.end_point.row + 1],
                                "decorators": [],
                                "returns": _get_return_type(arrow, source),
                            })
    return functions


def _extract_imports(root: Node, source: bytes) -> list[dict]:
    imports = []
    for node in _find_all_by_type(root, IMPORT_TYPES, max_depth=1):
        # Go-style grouped imports: import ( "fmt"; "net/http" )
        spec_list = [c for c in node.children if c.type == "import_spec_list"]
        if spec_list:
            for spec in spec_list[0].children:
                if spec.type == "import_spec":
                    for lit in spec.children:
                        if "string" in lit.type:
                            module = _text(lit, source).strip('"\'')
                            if module:
                                imports.append({"module": module, "alias": None, "line": spec.start_point.row + 1})
            continue

        text = _text(node, source).strip().rstrip(";")
        module = _parse_import_module(node, source, text)
        if module:
            imports.append({"module": module, "alias": None, "line": node.start_point.row + 1})
    return imports


def _extract_comments(root: Node, source: bytes) -> list[str]:
    comments = []
    for node in _find_all_by_type(root, COMMENT_TYPES, max_depth=10):
        text = _text(node, source)
        for line in text.splitlines():
            cleaned = line.strip().lstrip("/*#").rstrip("*/").strip()
            if cleaned and len(cleaned) > 3:
                comments.append(cleaned)
    return comments


def _get_bases(node: Node, source: bytes) -> list[str]:
    bases = []
    for child in node.children:
        if child.type in ("class_heritage", "superclass", "superclass_reference"):
            for sub in _find_all_by_type(child, {"identifier", "type_identifier"}, max_depth=3):
                name = _text(sub, source)
                if name and name not in ("extends", "implements"):
                    bases.append(name)
    return bases


def _get_params(node: Node, source: bytes) -> list[str]:
    PARAM_CONTAINER = {"formal_parameters", "parameter_list", "parameters",
                       "function_parameters", "method_parameters"}
    PARAM_TYPES = {"identifier", "required_parameter", "optional_parameter",
                   "parameter", "simple_parameter", "formal_parameter",
                   "parameter_declaration", "shorthand_field_identifier"}

    # Go methods have two parameter_list nodes: receiver, then actual params
    param_lists = [c for c in node.children if c.type in PARAM_CONTAINER]
    if node.type == "method_declaration" and len(param_lists) >= 2:
        param_lists = param_lists[1:]

    for plist in param_lists:
        params = []
        for p in plist.children:
            if p.type in PARAM_TYPES:
                name = _get_name(p, source) or _text(p, source).split(":")[0].split("=")[0].strip()
                if name and name not in ("(", ")", ",", "self", "this"):
                    params.append(name)
        return params
    return []


def _get_return_type(node: Node, source: bytes) -> str | None:
    for child in node.children:
        if child.type == "type_annotation":
            return _text(child, source).lstrip(": ").strip()
        if child.type in ("return_type", "result_type"):
            return _text(child, source).strip()
    return None


def _get_arrow_name(node: Node, source: bytes) -> str:
    parent = node.parent
    if parent and parent.type == "variable_declarator":
        return _get_name(parent, source)
    return ""


def _is_inside_ranges(node: Node, ranges: set[tuple[int, int]]) -> bool:
    for start, end in ranges:
        if node.start_byte > start and node.end_byte < end:
            return True
    return False


def _parse_import_module(node: Node, source: bytes, text: str) -> str:
    for child in node.children:
        if child.type == "string" or child.type == "string_literal":
            return _text(child, source).strip("'\"")
        if child.type == "scoped_identifier":
            return _text(child, source).replace("::", ".")
        if child.type == "use_tree" or child.type == "use_list":
            return _text(child, source).replace("::", ".")
        if child.type == "import_spec_list":
            for spec in child.children:
                if spec.type == "import_spec":
                    return _text(spec, source).strip('"')
        if child.type == "path":
            return _text(child, source).replace("/", ".")
    if "from" in text:
        parts = text.split("from")
        return parts[-1].strip().strip("'\"")
    return text.split()[-1].strip("'\"") if text.split() else ""
