"""Discover actual registered MCP tools, not helper functions or a manual allowlist."""
import base64
import inspect
from typing import Any, get_type_hints
import pyfigures.mcp_server as original
from mcp.server.fastmcp import Image
from mcp.types import ImageContent


def registry():
    return original.mcp._tool_manager._tools


def live_parameter(name):
    if name in ('show_me_how', 'guidance_status', 'close_guidance'):
        return None
    params = inspect.signature(registry()[name].fn).parameters
    if 'pyf_path' in params:
        return 'pyf_path'
    if name == 'copy_style' and 'target_pyf' in params:
        return 'target_pyf'
    return None


def encode(value):
    if isinstance(value, Image):
        return {'__live_mcp_image__': value.to_image_content().model_dump()}
    if isinstance(value, ImageContent):
        return {'__live_mcp_image__': value.model_dump()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    return value


def decode(value):
    if isinstance(value, dict) and '__live_mcp_image__' in value:
        return ImageContent.model_validate(value['__live_mcp_image__'])
    if isinstance(value, list):
        return [decode(item) for item in value]
    if isinstance(value, dict):
        return {key: decode(item) for key, item in value.items()}
    return value


def register_all(server, send):
    """Keep every original name/help/argument, defaulting figure targets to live."""
    for name, tool in registry().items():
        parameter = live_parameter(name)
        # Guidance requires a real window identity, not a temporary document.
        route = parameter

        def make_wrapper(tool=tool, name=name, parameter=route):
            def invoke(**kwargs):
                target = kwargs.get(parameter, 'live') if parameter else None
                if parameter and target == 'live':
                    for attempt in range(2):
                        state = send('inspect')
                        try:
                            result = send('original_tool', state['session_id'], state['revision'],
                                          {'tool': name, 'arguments': kwargs})
                            break
                        except ValueError as exc:
                            if attempt or getattr(exc, 'code', '') not in ('REVISION_CONFLICT', 'SESSION_CHANGED'):
                                raise
                    decoded = decode(result['tool_result'])
                    if result['document_changed'] or result.get('metadata_changed') or name in ('add_corner_labels', 'set_label_background'):
                        return {'result': decoded, 'document_changed': result['document_changed'],
                                'metadata_changed': result.get('metadata_changed', False), 'revision': result['revision'],
                                'persistence': result.get('persistence'), 'verification': result.get('verification'),
                                'verified_lettering': result.get('verified_lettering'),
                                'verified_changes': result.get('verified_changes'),
                                'verified_specification': result.get('verified_specification')}
                    return decoded
                return tool.fn(**kwargs)
            hints = get_type_hints(inspect.unwrap(tool.fn))
            params = []
            for p in inspect.signature(tool.fn).parameters.values():
                p = p.replace(kind=inspect.Parameter.KEYWORD_ONLY,
                              annotation=hints.get(p.name, p.annotation))
                if p.name == parameter:
                    p = p.replace(default='live')
                params.append(p)
            invoke.__name__ = name
            invoke.__signature__ = inspect.Signature(params, return_annotation=Any)
            invoke.__annotations__ = {p.name: p.annotation for p in params}
            invoke.__annotations__['return'] = Any
            return invoke

        suffix = (f' Live adapter: {route} defaults to "live", meaning the OPEN PyFigures document including unsaved changes. Omit it for live editing. An explicit filesystem path uses the original file-based tool. Live document changes are undoable and not automatically saved.'
                  if route else ' Original file/service tool: retains its original explicit paths and side effects; does not automatically load its output in the GUI.')
        if name in ('get_image_property', 'set_image_property'):
            suffix += ' Image rotation is property_name="theta" in degrees; unrotate/reset rotation means value="0". inspect_figure panel_references maps visible letters to group_path/image_index.'
        server.add_tool(make_wrapper(), name=name, description=tool.description + suffix,
                        annotations=tool.annotations, structured_output=False)
    return len(registry())
