"""A small HTML reader for scrapers that read web pages (standard library only).

`parse(text)` returns a tree of `Node`s. Scrapers find elements by tag and
class and read their text; fixture cleaners keep only the parts a scraper
reads and write them back out with `to_html`. It is forgiving, like a
browser: a closing tag with no opening tag is ignored, and an element left
open is closed by its parent's closing tag.
"""

from __future__ import annotations

import html as _html
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from html.parser import HTMLParser

VOID = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
)
_SPACE = re.compile(r"\s+")


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)
    parent: Node | None = field(default=None, repr=False)

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def iter(self) -> Iterator[Node]:
        """Every element below this one, in page order."""
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(self, tag: str | None = None, cls: str | None = None) -> list[Node]:
        return [
            n
            for n in self.iter()
            if (tag is None or n.tag == tag) and (cls is None or cls in n.classes)
        ]

    def find(self, tag: str | None = None, cls: str | None = None) -> Node | None:
        found = self.find_all(tag, cls)
        return found[0] if found else None

    def text(self) -> str:
        """The visible text, with runs of spaces and line breaks made one space."""
        parts: list[str] = []

        def walk(node: Node) -> None:
            if node.tag in ("script", "style"):
                return
            for child in node.children:
                if isinstance(child, str):
                    parts.append(child)
                else:
                    if child.tag == "br":
                        parts.append(" ")
                    walk(child)

        walk(self)
        return _SPACE.sub(" ", "".join(parts)).strip()

    def remove(self, tags: set[str] | frozenset[str] = frozenset(), cls: str | None = None) -> None:
        """Drop every element below this one with one of these tags, or this class."""
        kept: list[Node | str] = []
        for child in self.children:
            if isinstance(child, Node) and (child.tag in tags or (cls and cls in child.classes)):
                continue
            if isinstance(child, Node):
                child.remove(tags, cls)
            kept.append(child)
        self.children = kept


class _Builder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {k: (v or "") for k, v in attrs}, parent=self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def parse(text: str) -> Node:
    builder = _Builder()
    builder.feed(text)
    builder.close()
    return builder.root


def to_html(node: Node | str) -> str:
    """Write a node (or text) back out as HTML."""
    if isinstance(node, str):
        return _html.escape(node, quote=False)
    inner = "".join(to_html(c) for c in node.children)
    if node.tag == "#document":
        return inner
    attrs = "".join(f' {k}="{_html.escape(v)}"' for k, v in node.attrs.items())
    if node.tag in VOID:
        return f"<{node.tag}{attrs}>"
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


def document(nodes: list[Node], note: str) -> str:
    """A small page holding only these elements, for a fixture."""
    body = "\n".join(to_html(n) for n in nodes)
    return (
        '<!doctype html>\n<html><head><meta charset="utf-8"></head><body>\n'
        f"<!-- {_html.escape(note)} -->\n{body}\n</body></html>\n"
    )
