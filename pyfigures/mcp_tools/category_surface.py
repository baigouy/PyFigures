"""The file MCP server's small surface: three tools over the full registry.

``python -m pyfigures.mcp_server --tools categories`` lists only
list_pyfigures_categories, find_pyfigures_tools and use_pyfigures_tool (a few
kB) instead of every tool with its full description (~85k tokens with 210
tools): the details of an operation come when the model searches for it.
The categories are the live chat's (pyfigures.assistant.categorized_mcp).
"""
from __future__ import annotations

import copy
import difflib
import re

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from pyfigures.assistant.categorized_mcp import CATEGORIES, category_for

INSTRUCTIONS = (
    "Inspect, create and edit PyFigures .pyf scientific-figure files (and posters). "
    "Only three functions are listed: list_pyfigures_categories gives the areas, "
    "find_pyfigures_tools(query=the user's words, in English) gives matching operations with their exact "
    "argument schema and guidance, use_pyfigures_tool(tool_name, arguments) runs one. "
    "Never guess an operation or argument name: search first; a wrong argument returns the schema. "
    "Start with describe_figure on an existing figure, create_figure for a new one.")

# synonyms the users' words come in (the live chat's list, plus the file tools' own words)
_ALIASES = {"gaps": "spacing", "gap": "spacing", "letters": "letter", "labels": "label", "rows": "row",
            "images": "image", "fonts": "font", "rotate": "rotation", "rotated": "rotation",
            "colour": "color", "colours": "color", "colors": "color", "grey": "gray", "plots": "plot",
            "graph": "plot", "graphs": "plot", "chart": "plot", "bars": "bar", "insets": "inset"}


# words that say nothing about the operation ("how wide IS THE figure, IN mm?")
_STOP = {"a", "an", "the", "is", "are", "was", "be", "in", "on", "of", "to", "for", "and", "or", "it",
         "its", "this", "that", "these", "my", "me", "i", "you", "can", "could", "please", "how", "what",
         "which", "do", "does", "with", "by", "at", "from", "as", "all", "every", "some", "make", "get"}
# what the user asks -> the word the operations use
_ALIASES.update({"wide": "width", "tall": "height", "high": "height", "big": "size", "large": "size",
                 "millimeters": "mm", "millimetres": "mm"})


def _stem(w):
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _words(text):
    return [_stem(_ALIASES.get(w, w)) for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if w not in _STOP]


def _word_set(text):
    return set(_words(text))


def build(full: FastMCP) -> FastMCP:
    """A FastMCP server whose three tools reach every tool of *full*."""
    tools = full._tool_manager._tools
    categories = {key: desc for key, desc in CATEGORIES.items()
                  if any(category_for(n) == key for n in tools)}
    # whole words (not substrings: "in" must not match "kinds"); the first docstring line
    # counts more than the rest
    index = {name: (_word_set(name.replace("_", " ")),
                    _word_set((tool.description or "").split("\n", 1)[0]),
                    _word_set(tool.description or ""))
             for name, tool in tools.items()}
    server = FastMCP("pyfigures", instructions=INSTRUCTIONS)

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def list_pyfigures_categories() -> dict:
        """The areas PyFigures operations fall in, with their number of operations."""
        return {key: {"description": desc, "operations": sum(category_for(n) == key for n in tools)}
                for key, desc in categories.items()}

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def find_pyfigures_tools(query: str = "", category: str = "", limit: int = 6, offset: int = 0) -> dict:
        """Find operations by the user's words (e.g. "scale bar", "rotate image", "export pdf"), optionally
        within a category; returns each match's exact argument schema. Changes nothing."""
        if category and category not in categories:
            raise ValueError(f"Unknown category {category!r}; one of: {', '.join(categories)}")
        limit = min(max(int(limit or 6), 1), 12)
        offset = max(int(offset or 0), 0)
        words = _words(query)
        q = (query or "").strip().lower()
        ranked = []
        for name, tool in tools.items():
            cat = category_for(name)
            if category and cat != category:
                continue
            title, first, desc = index[name]
            # every query word found counts most (an operation that covers the whole request
            # beats one that repeats a single word), then the name, then the first line
            score = sum(3 * (w in desc or w in title) + 5 * (w in title) + (w in first) for w in words)
            if q == name or re.search(r"(?<![a-z0-9_])" + re.escape(name) + r"(?![a-z0-9_])", q):
                score += 1000          # named exactly: "set_scale_bar schema"
            if words and not score:
                continue
            ranked.append((score, name, tool, cat))
        ranked.sort(key=lambda r: (-r[0], r[1]))
        found = []
        for _, name, tool, cat in ranked[offset:offset + limit]:
            found.append({"name": name, "category": cat, "description": tool.description,
                          "arguments_schema": copy.deepcopy(tool.parameters)})
        return {"total_matches": len(ranked), "offset": offset,
                "next_offset": offset + len(found) if offset + len(found) < len(ranked) else None,
                "run_with": "use_pyfigures_tool(tool_name=<name>, arguments={...})",
                "tools": found}

    @server.tool(structured_output=False)
    async def use_pyfigures_tool(tool_name: str, arguments: dict | None = None):
        """Run one PyFigures operation found with find_pyfigures_tools, with its arguments."""
        tool = tools.get(tool_name)
        if tool is None:
            close = difflib.get_close_matches(tool_name, list(tools), n=5, cutoff=0.5)
            raise ValueError(f"No operation {tool_name!r}."
                             + (f" Close: {', '.join(close)}." if close else "")
                             + " Search with find_pyfigures_tools(query=...). Nothing was changed.")
        try:
            return await full._tool_manager.call_tool(tool_name, dict(arguments or {}))
        except Exception as e:
            if "validation error" in str(e).lower():
                raise ValueError(f"{e}\nArguments of {tool_name}: {tool.parameters}\n"
                                 "Nothing was changed.") from e
            raise

    return server
