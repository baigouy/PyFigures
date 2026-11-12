"""Discover actual registered MCP tools, not helper functions or a manual allowlist."""
import base64
import inspect
from typing import Any, Optional, get_type_hints
import pyfigures.mcp_server as original
from mcp.server.fastmcp import Image
from mcp.types import ImageContent, ToolAnnotations


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


def annotations_of_panel(decoded, state, ref):
    """get_annotations(panel_ref="C"): the entries of that panel only (a visible
    letter or a panel ID; the argument was refused as unknown, 2026-11-12)."""
    import json
    wanted = str(ref).strip().casefold()
    hits = [p for p in state.get('panel_references') or []
            if str(p.get('panel_id')) == wanted or wanted in [str(v).casefold() for v in p.get('letters', [])]]
    if len(hits) != 1:
        raise ValueError(f'No single panel is named {ref!r}; omit panel_ref to list every annotation.')
    entries = json.loads(decoded) if isinstance(decoded, str) else decoded
    if not isinstance(entries, list):
        return decoded
    kept = [e for e in entries if e.get('group_path') == hits[0].get('group_path')
            and e.get('image_index') == hits[0].get('image_index')]
    return json.dumps(kept, indent=2)


def register_all(server, send):
    """Keep every original name/help/argument, defaulting figure targets to live."""
    for name, tool in registry().items():
        parameter = live_parameter(name)
        # Guidance requires a real window identity, not a temporary document.
        route = parameter
        native_params=inspect.signature(tool.fn).parameters
        addressable=bool(route and {'group_path','image_index'} <= set(native_params))
        text_indexed=name in ('style_annotation','set_annotation_text')

        def make_wrapper(tool=tool, name=name, parameter=route, native_params=native_params, addressable=addressable, text_indexed=text_indexed):
            def invoke(**kwargs):
                def finish(value, evidence):
                    if name == 'set_figure_caption':
                        value = dict(value) if isinstance(value, dict) else {'result': value}
                        for key in ('caption_text','caption_title','caption_markdown','caption_ends_with_period','caption_readback_error'):
                            if key in evidence:value[key] = evidence[key]
                    from .result_evidence import with_font_evidence
                    return with_font_evidence(value, kwargs.get('font_family'))
                if text_indexed:
                    index=kwargs.pop('text_index',None)
                    if index is not None:
                        if kwargs.get('annotation_index') is not None and kwargs['annotation_index']!=index:
                            raise ValueError('Conflicting text_index and annotation_index; use text_index from get_annotations for text tools')
                        kwargs['annotation_index']=index
                only = kwargs.pop('panel_ref', None) if name == 'get_annotations' else None
                ref=kwargs.get('panel_ref')
                if addressable:
                    for key in ('group_path','image_index'):
                        if kwargs.get(key) is None:
                            kwargs.pop(key,None)
                            if ref is None and native_params[key].default is not inspect.Parameter.empty:
                                kwargs[key]=native_params[key].default
                            elif ref is None:
                                raise ValueError('Supply panel_ref for a named live panel, or both group_path and image_index')
                if text_indexed and kwargs.get('annotation_index') is None:
                    raise ValueError('Supply text_index from get_annotations (text tools count texts, not all annotations)')
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
                    if only is not None:
                        decoded = annotations_of_panel(decoded, state, only)
                    if result['document_changed'] or result.get('metadata_changed') or name in ('add_corner_labels', 'set_label_background'):
                        return finish({'result': decoded, 'document_changed': result['document_changed'],
                                'metadata_changed': result.get('metadata_changed', False), 'revision': result['revision'],
                                'persistence': result.get('persistence'), 'verification': result.get('verification'),
                                'verified_lettering': result.get('verified_lettering'),
                                'verified_changes': result.get('verified_changes'),
                                'verified_specification': result.get('verified_specification')}, result)
                    return finish(decoded, result)
                if kwargs.pop('panel_ref',None) is not None:
                    raise ValueError('panel_ref is for the live GUI; explicit file tools require native indices')
                return tool.fn(**kwargs)
            hints = get_type_hints(inspect.unwrap(tool.fn))
            params = []
            for p in inspect.signature(tool.fn).parameters.values():
                p = p.replace(kind=inspect.Parameter.KEYWORD_ONLY,
                              annotation=hints.get(p.name, p.annotation))
                if p.name == parameter:
                    p = p.replace(default='live')
                if addressable and p.name in ('group_path','image_index'):
                    p=p.replace(default=None,annotation=Optional[p.annotation])
                if text_indexed and p.name=='annotation_index':
                    p=p.replace(name='text_index')
                params.append(p)
            if addressable or name == 'get_annotations':
                params.append(inspect.Parameter('panel_ref',inspect.Parameter.KEYWORD_ONLY,default=None,annotation=str | None))
            invoke.__name__ = name
            invoke.__signature__ = inspect.Signature(params, return_annotation=Any)
            invoke.__annotations__ = {p.name: p.annotation for p in params}
            invoke.__annotations__['return'] = Any
            return invoke

        suffix = (f' Live adapter: {route} defaults to "live", meaning the OPEN PyFigures document including unsaved changes. Omit it for live editing. An explicit filesystem path uses the original file-based tool. Live document changes are undoable and not automatically saved.'
                  if route else ' Original file/service tool: retains its original explicit paths and side effects; does not automatically load its output in the GUI.')
        if name == 'list_fonts':
            suffix = ' Read-only installed font inventory and exact-name availability check; no document change.'
        if name == 'list_luts':
            suffix = ' Read-only LUT name inventory and exact-name availability check; no document change.'
        if addressable:
            suffix += ' PREFER panel_ref (visible letter or inspected panel ID) for a named LIVE panel; omit group_path/image_index. Resolved against current GUI state on the Qt thread. Conflicting numeric addresses are rejected, never silently substituted.'
        if text_indexed:
            suffix += ' Use the required text_index from get_annotations. The native Python parameter called annotation_index counts TEXTS; the live MCP schema deliberately calls it text_index to distinguish it from ROI/removal indices.'
        if name in ('get_image_property', 'set_image_property'):
            suffix += ' Image rotation is property_name="theta" in degrees; unrotate/reset rotation means value="0". inspect_figure panel_references maps visible letters to group_path/image_index.'
        wording = {
            'add_arrow': "style='arrowhead' already draws a head with NO shaft. Verify get_annotations.kind='arrowhead'; its short nonzero endpoints encode direction, not a visible shaft. Do not collapse endpoints to make it head-only. ",
            'list_fonts': 'Read-only fonts/typeface inventory. For is Helvetica/Arial available or installed, pass query and answer font_check.installed; if missing, report drawn_as and offer alternatives. For list fonts omit query and summarise installed_families/count. ',
            'set_figure_caption': 'caption is exact plain text, including its final period when supplied; title is a separate field. caption_markdown is an optional formatted string of that same text, never a boolean. ',
            'add_annotation': 'Write/put <words> on <panel> supplies literal text without needing quotation marks. Add dependent text before a later swap so it travels with its image. ',
            'set_scale_bar': 'Single-panel operation: Give a a scale bar names panel a. Prefer panel_ref even without a selection. Length and pixel size must be finite and positive. To change one thing of an existing bar pass only that (bar_height_px for thicker/thinner, placement, label="" for no text, bar_color, label_color); the rest is kept. Bulk is only for an explicit whole-figure request. ',
            'set_scale_bar_all': 'Whole-figure operation ONLY when explicitly requested; a named panel never authorizes bulk changes. Length and pixel size must be finite and positive. ',
        }
        description=tool.description.replace('annotation_index','text_index') if text_indexed else tool.description
        description=wording.get(name, '')+description
        server.add_tool(make_wrapper(), name=name, description=description + suffix,
                        annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False) if name in ('list_fonts','list_luts') else tool.annotations, structured_output=False)
    return len(registry())
