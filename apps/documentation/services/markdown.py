from __future__ import annotations

import html
import posixpath
import re

import frontmatter
import markdown
import nh3
from markdown.treeprocessors import Treeprocessor
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name

FENCE_RE = re.compile(r"^```([\w+-]*)\s*$")
CALLOUT_RE = re.compile(
    r"^>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$",
    re.IGNORECASE,
)
HEADING_RE = re.compile(r'<h([23]) id="([^"]+)"[^>]*>(.*?)</h\1>', re.S)

ICONS = {
    "note": '<circle cx="12" cy="12" r="9"/><path d="M12 8h.01M12 12v4"/>',
    "tip": '<path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/><circle cx="12" cy="12" r="3"/>',
    "important": '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4M12 17h.01"/>',
    "warning": '<path d="M12 3 2 20h20L12 3Z"/>',
    "caution": '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 9v4M12 16h.01"/>',
}

LABELS = {
    "note": "Note",
    "tip": "Tip",
    "important": "Important",
    "warning": "Warning",
    "caution": "Caution",
}

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "button", "circle", "code", "div",
    "em", "figcaption", "figure", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
    "i", "img", "li", "line", "ol", "p", "path", "polyline", "pre", "rect",
    "span", "strong", "svg", "table", "tbody", "td", "th", "thead", "tr", "ul",
}

ALLOWED_ATTRIBUTES = {
    "*": {"class", "id"},
    "a": {"href", "title", "target", "rel"},
    "img": {"src", "alt", "title", "width", "height"},
    "button": {"type", "aria-label", "data-copy"},
    "svg": {"viewbox", "width", "height", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "xmlns"},
    "path": {"d"},
    "circle": {"cx", "cy", "r"},
    "rect": {"x", "y", "width", "height", "rx"},
    "line": {"x1", "y1", "x2", "y2"},
    "polyline": {"points"},
    "th": {"align"},
    "td": {"align"},
}


def slugify(value, separator):
    value = str(value).lower()
    value = re.sub(r"[^a-z0-9]+", separator, value)
    return value.strip(separator)


def resolve_path(base_dir, target):
    target = target.strip("/")
    if target.startswith("/"):
        return posixpath.normpath(target).lstrip("/")
    joined = posixpath.join(base_dir or "", target)
    return posixpath.normpath(joined).lstrip("/")


class LinkRewriteTreeprocessor(Treeprocessor):
    def __init__(self, md, site_slug, base_dir, url_path=None):
        super().__init__(md)
        self.site_slug = site_slug
        self.base_dir = base_dir
        self.url_path = url_path or (lambda value: value)

    def run(self, root):
        for el in root.iter():
            if el.tag == "a":
                href = el.get("href")
                if href:
                    new = self._rewrite_link(href)
                    if new is not None:
                        el.set("href", new)
            elif el.tag == "img":
                src = el.get("src")
                if src:
                    new = self._rewrite_image(src)
                    if new is not None:
                        el.set("src", new)

    def _rewrite_link(self, href):
        if href.startswith(("http://", "https://", "mailto:", "#")):
            return None
        target, _, fragment = href.partition("#")
        if target.endswith(".md"):
            target = target[:-3]
        resolved = resolve_path(self.base_dir, target) if target else ""
        if resolved:
            path = f"/docs/{self.site_slug}/{self.url_path(resolved)}"
        else:
            path = f"/docs/{self.site_slug}"
        return f"{path}/#{fragment}" if fragment else f"{path}/"

    def _rewrite_image(self, src):
        if src.startswith(("http://", "https://", "data:")):
            return None
        resolved = resolve_path(self.base_dir, src)
        return f"/docs/{self.site_slug}/assets/{resolved}"


class MarkdownRenderer:
    def __init__(self, site_slug, url_path=None):
        self.site_slug = site_slug
        self.url_path = url_path or (lambda value: value)

    def render(self, raw, path):
        try:
            post = frontmatter.loads(raw)
            metadata = dict(post.metadata or {})
            body = post.content or ""
        except Exception:
            metadata = {}
            body = raw or ""

        base_dir = posixpath.dirname(path) if path else ""
        html = self._convert(body, base_dir, allow_callouts=True)
        clean = nh3.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            url_schemes={"http", "https", "mailto"},
            link_rel=None,
        )
        return {
            "title": str(metadata.get("title") or "").strip(),
            "description": str(metadata.get("description") or "").strip(),
            "hidden": bool(metadata.get("hidden", False)),
            "draft": bool(metadata.get("draft", False)),
            "html": clean,
            "headings": _extract_headings(clean),
        }

    def _convert(self, text, base_dir, allow_callouts):
        out = []
        for kind, content in self._tokenize(text, base_dir, allow_callouts):
            if kind == "html":
                out.append(content)
            else:
                out.append(self._render_md(content, base_dir))
        return "".join(out)

    def _tokenize(self, text, base_dir, allow_callouts):
        segments = []
        lines = text.split("\n")
        i = 0
        buf = []

        def flush():
            if buf:
                segments.append(("md", "\n".join(buf)))
                buf.clear()

        while i < len(lines):
            line = lines[i]
            fenced = FENCE_RE.match(line)
            if fenced:
                flush()
                lang = fenced.group(1) or "text"
                i += 1
                code = []
                while i < len(lines) and not lines[i].strip().startswith("```"):
                    code.append(lines[i])
                    i += 1
                i += 1
                if lang == "mermaid":
                    segments.append(("html", self._render_mermaid("\n".join(code))))
                else:
                    segments.append(("html", self._render_code(lang, "\n".join(code))))
                continue
            callout = CALLOUT_RE.match(line) if allow_callouts else None
            if callout:
                flush()
                kind = callout.group(1).lower()
                i += 1
                body = []
                while i < len(lines) and lines[i].startswith(">"):
                    body.append(lines[i].lstrip(">").lstrip(" "))
                    i += 1
                inner = self._convert("\n".join(body), base_dir, allow_callouts=False)
                segments.append(("html", self._render_callout(kind, inner)))
                continue
            buf.append(line)
            i += 1
        flush()
        return segments

    def _render_md(self, content, base_dir):
        md = markdown.Markdown(
            extensions=["tables", "sane_lists", "attr_list", "toc"],
            extension_configs={"toc": {"slugify": slugify}},
        )
        md.treeprocessors.register(
            LinkRewriteTreeprocessor(md, self.site_slug, base_dir, self.url_path),
            "linkrewrite",
            5,
        )
        return md.convert(content)

    def _render_mermaid(self, code):
        text = html.escape(code)
        return (
            '<div class="mermaid-block">'
            f'<pre class="mermaid">{text}</pre>'
            "</div>"
        )

    def _render_code(self, lang, code):
        try:
            lexer = get_lexer_by_name(lang) if lang and lang != "text" else TextLexer()
        except Exception:
            lexer = TextLexer()
        formatter = HtmlFormatter(nowrap=True)
        highlighted = highlight(code, lexer, formatter)
        label = html.escape(lang or "text")
        copy_data = html.escape(code, quote=True)
        return (
            '<div class="codeblock">'
            '<div class="codeblock-head">'
            f'<span class="codeblock-lang">{label}</span>'
            f'<button type="button" class="codeblock-copy" data-copy="{copy_data}">'
            '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>'
            "<span>Copy</span>"
            "</button>"
            "</div>"
            f"<pre><code>{highlighted}</code></pre>"
            "</div>"
        )

    def _render_callout(self, kind, inner_html):
        icon = ICONS.get(kind, ICONS["note"])
        label = LABELS.get(kind, "Note")
        return (
            f'<div class="callout callout-{kind}">'
            f'<svg class="callout-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{icon}</svg>'
            f'<div class="callout-body"><div class="callout-title">{label}</div>{inner_html}</div>'
            "</div>"
        )


def _extract_headings(html_text):
    headings = []
    for match in HEADING_RE.finditer(html_text):
        text = re.sub(r"<[^>]+>", "", match.group(3))
        text = html.unescape(text).strip()
        headings.append(
            {
                "level": int(match.group(1)),
                "id": match.group(2),
                "text": text,
            },
        )
    return headings
