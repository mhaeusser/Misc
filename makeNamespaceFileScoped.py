import os
import re
import sys
from typing import Optional, Tuple

IDENT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")

def is_identifier_char(ch: str) -> bool:
    return ch in IDENT

def skip_ws_and_comments(s: str, i: int) -> int:
    n = len(s)
    while i < n:
        if s.startswith("//", i):
            i = s.find("\n", i)
            if i == -1: return n
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j == -1 else j + 2
        elif i < n and s[i] in " \t\r\n":
            i += 1
        else:
            break
    return i

def scan_string_or_char(s: str, i: int) -> int:
    n = len(s)
    quote = s[i]
    verbatim = False
    j = i - 1
    while j >= 0 and s[j] in ("@", "$"):
        if s[j] == "@":
            verbatim = True
        j -= 1
    i += 1
    if quote == "'":  # char
        escape = False
        while i < n:
            c = s[i]
            if not verbatim and c == "\\" and not escape:
                escape = True
                i += 1
                continue
            if c == "'" and not escape:
                return i + 1
            escape = False
            i += 1
        return n
    else:  # string
        if verbatim:
            while i < n:
                if s[i] == '"':
                    if i + 1 < n and s[i + 1] == '"':
                        i += 2
                        continue
                    return i + 1
                i += 1
            return n
        else:
            escape = False
            while i < n:
                c = s[i]
                if c == "\\" and not escape:
                    escape = True
                    i += 1
                    continue
                if c == '"' and not escape:
                    return i + 1
                escape = False
                i += 1
            return n

def find_top_level_namespace_block(s: str) -> Optional[Tuple[int, int, int, str]]:
    n = len(s)
    i, depth = 0, 0
    while i < n:
        c = s[i]
        if c in ("'", '"'):
            i = scan_string_or_char(s, i)
            continue
        if s.startswith("//", i):
            i = s.find("\n", i)
            if i == -1: break
            continue
        if s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if c == '{':
            depth += 1; i += 1; continue
        if c == '}':
            depth = max(0, depth - 1); i += 1; continue

        if depth == 0 and s.startswith("namespace", i):
            before = s[i - 1] if i > 0 else ' '
            after = s[i + len("namespace")] if i + len("namespace") < n else ' '
            if not is_identifier_char(before) and not is_identifier_char(after):
                ns_start = i
                i += len("namespace")
                i = skip_ws_and_comments(s, i)
                name_start = i
                while i < n and (is_identifier_char(s[i]) or s[i] == '.'):
                    i += 1
                ns_name = s[name_start:i].strip()
                if not ns_name:
                    return None
                j = skip_ws_and_comments(s, i)
                if j < n and s[j] == ';':
                    return None  # already file-scoped
                if j < n and s[j] == '{':
                    open_brace = j
                    k = open_brace + 1
                    inner_depth = 1
                    while k < n:
                        ch = s[k]
                        if ch in ("'", '"'):
                            k = scan_string_or_char(s, k)
                            continue
                        if s.startswith("//", k):
                            k = s.find("\n", k)
                            if k == -1: k = n
                            continue
                        if s.startswith("/*", k):
                            t = s.find("*/", k + 2)
                            k = n if t == -1 else t + 2
                            continue
                        if s[k] == '{':
                            inner_depth += 1
                        elif s[k] == '}':
                            inner_depth -= 1
                            if inner_depth == 0:
                                return ns_start, open_brace, k, ns_name
                        k += 1
        i += 1
    return None

def only_ws_or_comments(s: str) -> bool:
    return skip_ws_and_comments(s, 0) == len(s)

def has_namespace_keyword(s: str) -> bool:
    return re.search(r'(?<![\w])namespace(?![\w])', s) is not None

def contains_nested_namespace(src_inside: str) -> bool:
    cleaned = []
    i, n = 0, len(src_inside)
    while i < n:
        if src_inside[i] in ("'", '"'):
            i = scan_string_or_char(src_inside, i); continue
        if src_inside.startswith("//", i):
            i = src_inside.find("\n", i)
            if i == -1: break
            continue
        if src_inside.startswith("/*", i):
            j = src_inside.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        cleaned.append(src_inside[i]); i += 1
    return has_namespace_keyword("".join(cleaned))

def dedent_one_level(block: str) -> str:
    out_lines = []
    for line in block.splitlines():
        if line.startswith("\t"):
            out_lines.append(line[1:])
        else:
            spaces = len(line) - len(line.lstrip(" "))
            out_lines.append(line[min(spaces, 4):])
    return "\n".join(out_lines)

def convert_content(content: str) -> Tuple[str, str]:
    match = find_top_level_namespace_block(content)
    if not match:
        return content, "No convertible top-level block-scoped namespace found."
    ns_start, open_brace, close_brace, ns_name = match
    before = content[:ns_start]
    body = content[open_brace + 1:close_brace]
    after = content[close_brace + 1:]
    if not only_ws_or_comments(after):
        return content, "Skipped: content after namespace closing brace."
    if contains_nested_namespace(body):
        return content, "Skipped: nested namespace declarations detected."
    new_header = f"namespace {ns_name};\n\n"
    new_body = dedent_one_level(body).strip("\n")
    return before + new_header + new_body + "\n", "Converted."

def process_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        original = f.read()
    new_content, status = convert_content(original)
    if new_content != original and "Converted" in status:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
    return f"{status} {path}"

def process_directory(directory: str):
    for root, _, files in os.walk(directory):
        for name in files:
            if name.endswith(".cs"):
                path = os.path.join(root, name)
                try:
                    print(process_file(path))
                except Exception as e:
                    print(f"Error: {path}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_namespaces.py <directory>")
        sys.exit(1)
    process_directory(sys.argv[1])
