import re


def markdown_to_html(md_text: str, title: str = "") -> str:
    body = _convert_body(md_text)
    return _wrap_document(body, title)


_FENCED_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def _convert_body(text: str) -> str:
    code_blocks = []

    def _save_code(m):
        code_blocks.append((m.group(1) or "", m.group(2)))
        return f"\x00CODEBLOCK{len(code_blocks) - 1}\x00"

    text = _FENCED_RE.sub(_save_code, text)

    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()

        if not stripped and result and result[-1] == "":
            i += 1
            continue

        if not stripped:
            result.append("")
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            content = _convert_inline(heading.group(2))
            result.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        if re.match(r"^[-*_]{3,}$", stripped):
            result.append("<hr>")
            i += 1
            continue

        if "|" in stripped and _is_table_row(stripped):
            table_lines = []
            while i < len(lines) and lines[i].strip() and _is_table_row(lines[i].strip()):
                table_lines.append(lines[i].strip())
                i += 1
            result.append(_render_table(table_lines))
            continue

        blockquote_match = re.match(r"^>\s?(.*)", stripped)
        if blockquote_match:
            bq_lines = []
            while i < len(lines) and (lines[i].strip().startswith(">") or not lines[i].strip()):
                bq_line = lines[i].strip()
                if bq_line.startswith(">"):
                    bq_lines.append(re.sub(r"^>\s?", "", bq_line))
                else:
                    bq_lines.append("")
                i += 1
            content = _convert_inline("\n".join(bq_lines))
            result.append(f"<blockquote><p>{content}</p></blockquote>")
            continue

        ul_match = re.match(r"^[-*+]\s+(.*)", stripped)
        if ul_match:
            items = []
            while i < len(lines):
                s = lines[i].strip()
                m = re.match(r"^[-*+]\s+(.*)", s)
                if not m:
                    break
                items.append(_convert_inline(m.group(1)))
                i += 1
            result.append(_render_list(items, ordered=False))
            continue

        ol_match = re.match(r"^\d+\.\s+(.*)", stripped)
        if ol_match:
            items = []
            while i < len(lines):
                s = lines[i].strip()
                m = re.match(r"^\d+\.\s+(.*)", s)
                if not m:
                    break
                items.append(_convert_inline(m.group(1)))
                i += 1
            result.append(_render_list(items, ordered=True))
            continue

        para_lines = []
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i].strip()):
            para_lines.append(lines[i].strip())
            i += 1
        content = _convert_inline(" ".join(para_lines))
        result.append(f"<p>{content}</p>")

    body = "\n".join(line for line in result if line is not None)

    for idx, (lang, code) in enumerate(code_blocks):
        marker = f"\x00CODEBLOCK{idx}\x00"
        body = body.replace(f"<p>{marker}</p>", _render_code_block(code, lang))

    return body


def _is_block_start(line: str) -> bool:
    return bool(
        re.match(r"^#{1,6}\s+", line)
        or re.match(r"^[-*_]{3,}$", line)
        or re.match(r"^[-*+]\s+", line)
        or re.match(r"^\d+\.\s+", line)
        or re.match(r"^>\s?", line)
        or _is_table_row(line)
    )


def _is_table_row(line: str) -> bool:
    return bool(re.match(r"^\|.*\|$", line.strip()))


def _render_table(lines):
    if not lines:
        return ""
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if not rows:
        return ""

    max_cols = max(len(r) for r in rows)
    header = rows[0]
    data_rows = rows[1:]

    if len(data_rows) >= 1 and all(
        re.match(r"^:?-{3,}:?$", cell.strip()) for cell in data_rows[0]
    ):
        data_rows = data_rows[1:]

    thead = "<thead><tr>" + "".join(
        f"<th>{_convert_inline(header[i]) if i < len(header) else ''}</th>"
        for i in range(max_cols)
    ) + "</tr></thead>"

    tbody = "<tbody>"
    for row in data_rows:
        tbody += "<tr>" + "".join(
            f"<td>{_convert_inline(row[i]) if i < len(row) else ''}</td>"
            for i in range(max_cols)
        ) + "</tr>"
    tbody += "</tbody>"

    return f"<table>{thead}{tbody}</table>"


def _render_list(items, ordered=False):
    tag = "ol" if ordered else "ul"
    if not items:
        return f"<{tag}></{tag}>"
    return f"<{tag}>\n<li>" + "</li>\n<li>".join(items) + f"</li>\n</{tag}>"


def _render_code_block(code_text, lang=""):
    escaped = _escape_html(code_text.rstrip("\n"))
    lang_attr = f' class="language-{lang}"' if lang else ""
    return f"<pre><code{lang_attr}>{escaped}</code></pre>"


_INLINE_PATTERNS = [
    (re.compile(r"`([^`]+)`"), r'<code>\1</code>'),
    (re.compile(r"\*\*\*(.+?)\*\*\*"), r"<strong><em>\1</em></strong>"),
    (re.compile(r"___(.+?)___"), r"<strong><em>\1</em></strong>"),
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"__(.+?)__"), r"<strong>\1</strong>"),
    (re.compile(r"\*(.+?)\*"), r"<em>\1</em>"),
    (re.compile(r"\b_(.+?)_\b"), r"<em>\1</em>"),
    (re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"), r'<img alt="\1" src="\2">'),
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), r'<a href="\2">\1</a>'),
]


def _convert_inline(text: str) -> str:
    text = _escape_html(text)
    for pattern, replacement in _INLINE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _wrap_document(body: str, title: str = "") -> str:
    title_tag = f"<title>{_escape_html(title)}</title>" if title else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{title_tag}
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 960px; margin: 0 auto; padding: 20px; color: #333; background: #fff; }}
  h1 {{ border-bottom: 2px solid #e1e4e8; padding-bottom: 8px; }}
  h2 {{ border-bottom: 1px solid #e1e4e8; padding-bottom: 6px; margin-top: 32px; }}
  h3 {{ margin-top: 24px; }}
  h4 {{ margin-top: 20px; }}
  code {{ background: #f6f8fa; padding: 2px 6px; border-radius: 3px; font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 0.9em; }}
  pre {{ background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 6px; padding: 16px; overflow-x: auto; }}
  pre code {{ background: none; padding: 0; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f6f8fa; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafbfc; }}
  blockquote {{ border-left: 4px solid #ddd; margin: 16px 0; padding: 0 16px; color: #666; }}
  hr {{ border: none; border-top: 1px solid #e1e4e8; margin: 24px 0; }}
  ul, ol {{ padding-left: 24px; }}
  li {{ margin: 4px 0; }}
  a {{ color: #0366d6; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _find_prd_md_files(directory: str) -> "list[str]":
    import os
    import re
    result = []
    pattern = re.compile(r"^PRD-.+\.md$", re.IGNORECASE)
    try:
        for entry in sorted(os.listdir(directory)):
            if pattern.match(entry):
                result.append(os.path.join(directory, entry))
    except OSError:
        pass
    return result


def _ask_yes_no(prompt: str) -> bool:
    try:
        answer = input(prompt + " [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in ("y", "yes")


if __name__ == "__main__":
    import os
    import re
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "."
    yes_mode = "--yes" in sys.argv or "-y" in sys.argv

    if not yes_mode and target in ("--yes", "-y"):
        print("用法: python3 markdown_to_html.py [目录|PRD-*.md文件] [--yes|-y]")
        print("  --yes/-y  跳过确认，直接转换")
        sys.exit(0)

    _prd_pattern = re.compile(r"^PRD-.+\.md$", re.IGNORECASE)
    md_files = []
    if os.path.isfile(target) and _prd_pattern.match(os.path.basename(target)):
        md_files = [target]
    elif os.path.isdir(target):
        md_files = _find_prd_md_files(target)
    else:
        print(f"未找到匹配 PRD-*.md 的文件: {target}", file=sys.stderr)
        sys.exit(1)

    if not md_files:
        print("未找到 PRD-*.md 文件")
        sys.exit(0)

    print(f"找到 {len(md_files)} 个 PRD-*.md 文件:")
    for f in md_files:
        size = os.path.getsize(f)
        print(f"  {f} ({size} 字节)")

    if not yes_mode:
        if not _ask_yes_no("\n是否转换为 HTML?"):
            print("已取消")
            sys.exit(0)

    converted = 0
    for md_path in md_files:
        html_path = os.path.splitext(md_path)[0] + ".html"
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()
        except Exception as e:
            print(f"读取失败 {md_path}: {e}", file=sys.stderr)
            continue
        title = os.path.splitext(os.path.basename(md_path))[0]
        html = markdown_to_html(md_text, title=title)
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as e:
            print(f"写入失败 {html_path}: {e}", file=sys.stderr)
            continue
        converted += 1
        print(f"  {md_path} -> {html_path}")

    print(f"\n完成: {converted}/{len(md_files)} 个文件")
