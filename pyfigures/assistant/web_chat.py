"""Edit the figure from an online chat page (Mistral Le Chat / Emmy, ChatGPT,
Claude, Gemini…) instead of an API: no key, the user's own login.

The page has no tool calls, so the model is asked to write the operations it
wants as JSON between two marker lines::

    PYFIGURES-CALLS
    [{"tool": "find_pyfigures_tools", "arguments": {"query": "scale bar"}}]
    END-PYFIGURES-CALLS

PyFigures reads them from the page text (any site: no per-site selectors),
runs them on the shared figure when the user clicks Apply (look-ups may run
by themselves), and writes the results into the chat box; the user presses
Send. The operations are those of the chat sidebar (categorized_mcp), run
in this process through the live session's local bridge, so they must run
off the Qt thread (the session answers on it).

Qt-free here; the panel is pyfigures.gui.web_chat_panel.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import threading

BEGIN = 'PYFIGURES-CALLS'
END = 'END-PYFIGURES-CALLS'
RESULTS = 'PYFIGURES-RESULTS'
TEMPLATE = 'TOOL_NAME'       # the placeholder of the example block, never a real call
_BLOCK = re.compile(r'(?<![A-Z-])' + re.escape(BEGIN) + r'\s*(.*?)\s*' + re.escape(END), re.S)

# look-ups: change nothing, so they may run without a click
READ_ONLY = frozenset({'inspect_figure', 'preview_figure', 'list_pyfigures_categories', 'find_pyfigures_tools'})

# chat pages offered in the panel; any other address can be typed (and is remembered)
PRESETS = (
    ('Mistral Le Chat', 'https://chat.mistral.ai/chat'),
    ('ChatGPT', 'https://chatgpt.com/'),
    ('Claude', 'https://claude.ai/new'),
    ('Gemini', 'https://gemini.google.com/app'),
)

MAX_RESULT_CHARS = 6000      # per call, in the message written back into the chat box


class Block:
    """One PYFIGURES-CALLS block read from the page: its calls, or why it
    could not be read."""

    def __init__(self, raw, calls=None, error=None):
        self.raw = raw
        self.calls = calls or []
        self.error = error
        self.key = hashlib.sha1(re.sub(r'\s+', '', raw).encode('utf-8')).hexdigest()

    @property
    def read_only(self):
        return bool(self.calls) and all(c['tool'] in READ_ONLY for c in self.calls)

    def describe(self):
        if self.error:
            return 'Unreadable request: ' + self.error
        return '\n'.join(describe_call(c) for c in self.calls)


def describe_call(call):
    """One line for the user: the operation and its arguments."""
    tool, args = call['tool'], call.get('arguments') or {}
    if tool == 'use_pyfigures_tool':
        tool, args = args.get('tool_name', '?'), args.get('arguments') or {}
    text = json.dumps(args, ensure_ascii=False)
    return f'{tool} {text if len(text) < 200 else text[:197] + "…"}'


def _strip_fences(text):
    text = text.strip()
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
    return re.sub(r'\s*```$', '', text).strip()


def _load(text):
    """JSON as models write it in a chat: smart quotes and trailing commas
    are tolerated."""
    text = _strip_fences(text)
    text = text.replace('“', '"').replace('”', '"').replace(' ', ' ')
    # a page's code block adds its own words around the JSON ("json", "Copy code")
    starts = [i for i in (text.find('['), text.find('{')) if i >= 0]
    end = max(text.rfind(']'), text.rfind('}'))
    if starts and end > min(starts):
        text = text[min(starts):end + 1]
    try:
        return json.loads(text)
    except ValueError:
        return json.loads(re.sub(r',\s*([\]}])', r'\1', text))


def parse_blocks(text, tool_names=None):
    """Every complete PYFIGURES-CALLS block in *text* (a page or a pasted
    reply), in order. A call to an inner operation by its own name is
    wrapped into use_pyfigures_tool, as the sidebar's model would call it.
    Blocks that are not JSON (such as the example in the instructions) come
    back with an error."""
    names = set(tool_names or ()) | READ_ONLY | {'use_pyfigures_tool', 'undo_redo', 'select_live_objects'}
    blocks = []
    for match in _BLOCK.finditer(text or ''):
        raw = match.group(1)
        if TEMPLATE in raw:
            continue        # the example of the instructions, shown on the page once sent
        try:
            value = _load(raw)
        except ValueError as exc:
            blocks.append(Block(raw, error=f'not valid JSON ({exc})'))
            continue
        if isinstance(value, dict) and 'calls' in value:
            value = value['calls']
        if isinstance(value, dict):
            value = [value]
        calls, error = [], None
        if not isinstance(value, list) or not value:
            error = 'expected a list of {"tool": …, "arguments": {…}}'
        else:
            for item in value:
                if not isinstance(item, dict) or not isinstance(item.get('tool') or item.get('name'), str):
                    error = 'each call needs "tool" and "arguments"'
                    break
                tool = item.get('tool') or item.get('name')
                args = item.get('arguments', item.get('args', {}))
                if not isinstance(args, dict):
                    error = f'the arguments of {tool} must be a JSON object'
                    break
                if tool not in names:
                    args = {'tool_name': tool, 'arguments': args}
                    tool = 'use_pyfigures_tool'
                calls.append({'tool': tool, 'arguments': args})
        blocks.append(Block(raw, calls=None if error else calls, error=error))
    return blocks


def instructions_prompt(tools, server_instructions, state=None):
    """The first message: how to ask for operations, the operations, the
    figure as it is now. The user adds their request after it."""
    lines = [
        'You are helping me edit a scientific figure that is open in PyFigures on my computer. '
        'You cannot call tools directly in this chat. Instead, when you want PyFigures to run operations, '
        'end your answer with a JSON list of calls between the two marker lines of this example '
        '(each marker alone on its line):',
        '',
        BEGIN,
        '[{"tool": "' + TEMPLATE + '", "arguments": {...}}]',
        END,
        '',
        'Rules:',
        '- Use only the tools listed below, with their exact argument names. Inner operations found with '
        'find_pyfigures_tools are run through use_pyfigures_tool(tool_name, arguments).',
        '- Write at most one block per answer, then stop and wait: I run it in PyFigures and paste back a '
        f'message starting with {RESULTS}. Never invent results.',
        '- Look up the exact arguments of an operation (find_pyfigures_tools) before its first use.',
        '- Put the JSON in a code block if you like, but write the two marker lines exactly as shown.',
        '- When no operation is needed (a question, a how-to), answer normally without a block.',
        '',
        'PyFigures guidance:',
        server_instructions.strip(),
        '',
        'Tools:',
    ]
    for tool in tools:
        schema = dict(tool.get('inputSchema') or {})
        schema.pop('title', None)
        lines.append(f'- {tool["name"]}: {(tool.get("description") or "").strip()}')
        lines.append('  arguments schema: ' + json.dumps(schema, ensure_ascii=False, separators=(',', ':')))
    if state is not None:
        lines += ['', 'The figure now (inspect_figure):', _truncate(json.dumps(state, ensure_ascii=False), 8000)]
    lines += ['', 'Reply "Ready" and wait for my request.']
    return '\n'.join(lines)


def _truncate(text, limit):
    return text if len(text) <= limit else text[:limit] + f'… [{len(text) - limit} more characters cut]'


def results_message(outcomes):
    """The message written back into the chat box after a block ran:
    outcomes = [(call, ok, text)]."""
    lines = [f'{RESULTS} (from PyFigures):']
    for i, (call, ok, text) in enumerate(outcomes, 1):
        lines.append(f'{i}. {describe_call(call)} -> {"OK" if ok else "ERROR"}')
        lines.append(_truncate(text, MAX_RESULT_CHARS))
    lines.append('Continue with the next step, or tell me what changed if the request is done.')
    return '\n'.join(lines)


def _content_text(blocks, images):
    """Text of MCP content blocks; images are kept aside (PNG bytes)."""
    parts = []
    for block in blocks:
        kind = getattr(block, 'type', None)
        if kind == 'text':
            parts.append(block.text)
        elif kind == 'image':
            images.append(base64.b64decode(block.data))
            parts.append('[image: a preview PyFigures keeps for you; ask me to paste it if you need to see it]')
        else:
            parts.append(str(block))
    return '\n'.join(parts)


class ToolRunner:
    """The chat sidebar's operations (categorized_mcp over live_mcp's
    bridge), called in this process. Every call blocks until the shared
    window answered, so call only from a worker thread (run_async)."""

    def __init__(self, server=None):
        self._server = server
        self._lock = threading.Lock()

    @property
    def server(self):
        with self._lock:
            if self._server is None:
                from . import live_mcp
                from .categorized_mcp import build_server
                self._server = build_server(live_mcp.mcp, live_mcp.request)
            return self._server

    def tools(self):
        """[{name, description, inputSchema}] of the advertised operations."""
        listed = asyncio.run(self.server.list_tools())
        return [{'name': t.name, 'description': t.description, 'inputSchema': t.inputSchema} for t in listed]

    def instructions(self):
        return self.server.instructions or ''

    def call(self, tool, arguments):
        """(ok, text, images) of one operation."""
        images = []
        try:
            result = asyncio.run(self.server.call_tool(tool, dict(arguments or {})))
        except Exception as exc:
            return False, str(exc), images
        if isinstance(result, tuple):
            result = result[0]
        if isinstance(result, dict):
            return True, json.dumps(result, ensure_ascii=False), images
        return True, _content_text(result, images), images

    def first_prompt(self):
        """The instructions message, with the figure as it is now."""
        ok, text, _ = self.call('inspect_figure', {})
        state = None
        if ok:
            try:
                state = json.loads(text)
            except ValueError:
                state = text
        return instructions_prompt(self.tools(), self.instructions(), state)

    def run_block(self, block):
        """[(call, ok, text)] and the images, calls in order; stops at the
        first failed edit (the next ones assumed it worked)."""
        outcomes, images = [], []
        for call in block.calls:
            ok, text, imgs = self.call(call['tool'], call['arguments'])
            outcomes.append((call, ok, text))
            images += imgs
            if not ok and call['tool'] not in READ_ONLY:
                for rest in block.calls[len(outcomes):]:
                    outcomes.append((rest, False, 'Not run: an earlier operation in this block failed.'))
                break
        return outcomes, images


def run_async(function, done, *args):
    """function(*args) on a worker thread; done(result or exception) is
    called on that thread (the panel re-posts it to the Qt thread)."""
    def work():
        try:
            value = function(*args)
        except Exception as exc:        # handed to the panel, which shows it
            value = exc
        done(value)
    thread = threading.Thread(target=work, daemon=True, name='pyfigures-web-chat')
    thread.start()
    return thread
