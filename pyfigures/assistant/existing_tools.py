"""Adapters over existing PyFigures file tools; originals are imported, never edited."""
import inspect
import re
import xml.etree.ElementTree as ET
from pyfigures.mcp_tools import structure as tools
from .original_registry import registry, live_parameter, encode
from pyfigures.mcp_tools.core import _new_group_elem, _decode

READ = ('describe_figure', 'list_images', 'get_annotations', 'get_figure_properties')
EDIT = ('set_spacing', 'set_orientation', 'reorder_children', 'set_annotation_text',
        'tidy_text', 'remove_image', 'remove_annotation', 'add_group', 'set_size',
        'move_image', 'recompute_layout', 'set_figure_properties')


def resolve(name):
    return registry()[name].fn


def checked(result):
    if isinstance(result, str) and (result.startswith('ERROR') or result.startswith('Layout recompute warning')):
        raise ValueError(result)
    return result


def catalogue():
    return {name: {'kind': 'read' if name in READ else ('live' if live_parameter(name) else 'native'),
                   'signature': str(inspect.signature(resolve(name))),
                   'live_target_parameter': live_parameter(name),
                   'batch_supported': name in READ + EDIT,
                   'help': tool.description}
            for name, tool in registry().items()}


def run(path, calls, read_only=False):
    if not isinstance(calls, list) or not 1 <= len(calls) <= 50:
        raise ValueError('Provide 1–50 calls')
    allowed = READ if read_only else EDIT
    prepared = []
    for call in calls:
        name, args = call['tool'], call.get('arguments', {})
        if name not in allowed or not isinstance(args, dict) or 'pyf_path' in args:
            raise ValueError('Unsupported tool or arguments; use the catalogue')
        fn = resolve(name)
        inspect.signature(fn).bind(path, **args)
        prepared.append((fn, args))
    from mcp.server.fastmcp.exceptions import ToolError
    try:
        from pathlib import Path
        from .partner_gui import carry_policies
        results = []
        for fn, args in prepared:
            before = Path(path).read_bytes()
            results.append(checked(fn(path, **args)))
            if Path(path).read_bytes() != before:
                Path(path).write_bytes(carry_policies(before, Path(path).read_bytes()))
        return results
    except ToolError as exc:
        raise ValueError(str(exc)) from exc


def parse_row_counts(value):
    """Images per row: 3, "3", [3, 2, 2, 2] or "3-2-2-2" (also "3,2,2,2" / "3 2 2 2").

    Returns (columns, row_counts): an equal split keeps row_counts None.
    """
    if isinstance(value, bool):
        raise ValueError('images per row must be a number such as 3 or one number per row such as 3-2-2-2')
    if isinstance(value, int):
        return value, None
    if isinstance(value, str):
        # 'x' separates only two numbers ("3x2"); "3-x" is not a number per row
        parts = [p for p in re.split(r'(?<=\d)\s*[x×]\s*(?=\d)|[\s,;/+-]+', value.strip()) if p]
        if not parts or not all(p.isdigit() for p in parts):
            raise ValueError(f'"{value}" is not a number of images per row (e.g. 3) or one number per row (e.g. 3-2-2-2)')
        value = [int(p) for p in parts]
    if isinstance(value, (list, tuple)):
        if not value or not all(type(n) is int for n in value):
            raise ValueError('row_counts must be a list of whole numbers, one per row, e.g. [3, 2, 2, 2]')
        if len(value) == 1:
            return value[0], None
        return max(value), list(value)
    raise ValueError('images per row must be a number such as 3 or one number per row such as 3-2-2-2')


def arrange_rows(path, columns, width, spacing, row_counts=None):
    """Regroup every image panel into rows, in reading order: `columns` per row
    (the last row may be shorter) or exactly `row_counts` (e.g. [3, 2, 2, 2])."""
    if row_counts is not None:
        if (not isinstance(row_counts, (list, tuple)) or not row_counts or len(row_counts) > 100
                or not all(type(n) is int and 1 <= n <= 100 for n in row_counts)):
            raise ValueError('row_counts must list 1 to 100 rows of 1 to 100 images each, e.g. [3, 2, 2, 2]')
        columns = max(row_counts)
    if type(columns) is not int or not 1 <= columns <= 100:
        raise ValueError('columns must be an integer from 1 to 100')
    if type(width) is not int or not 32 <= width <= 20000:
        raise ValueError('row_width_px must be an integer from 32 to 20000')
    if type(spacing) is not int or not 0 <= spacing <= 1000 or spacing * (columns - 1) >= width:
        raise ValueError('Invalid spacing for row width')
    root = ET.fromstring(tools.get_xml(path))
    images, labels = [], []
    def collect(node, nested=False):
        if _decode(node.findtext('isText')):
            if nested:
                raise ValueError('Nested text rows need manual handling before regrouping')
            labels.append(node)
        elif node.tag == 'Image2D':
            images.append(node)  # Keep full XML, including annotations, insets and crop.
        elif node.tag == 'Group':
            for child in node.find('content') or []:
                if child.tag not in ('Group', 'Image2D'):
                    raise ValueError('Unsupported group content')
                collect(child, True)
        else:
            raise ValueError('Unsupported canvas object; refusing to drop it')
    for node in list(root):
        if node.tag in ('Group', 'Image2D'):
            collect(node)
            root.remove(node)
    if not images:
        raise ValueError('No image panels to arrange')
    if row_counts is not None and sum(row_counts) != len(images):
        raise ValueError(f'row_counts {"-".join(map(str, row_counts))} places {sum(row_counts)} images but the figure '
                         f'has {len(images)}; give one number per row adding up to {len(images)}. Nothing was changed.')
    counts = list(row_counts) if row_counts is not None else [
        min(columns, len(images) - start) for start in range(0, len(images), columns)]
    start = 0
    for row, count in enumerate(counts):
        group = _new_group_elem('X', spacing, row + 1)
        group.find('size').text = str(float(width))
        group.find('content').extend(images[start:start + count])
        root.insert(row, group)
        start += count
    # Preserve standalone labels after the rows; their exact old position may change.
    for offset, label in enumerate(labels):
        root.insert(len(counts) + offset, label)
    checked(tools.write_xml(path, ET.tostring(root, encoding='unicode')))
    from pathlib import Path
    before_layout = Path(path).read_bytes()
    checked(tools.recompute_layout(path))
    from .partner_gui import carry_policies
    Path(path).write_bytes(carry_policies(before_layout, Path(path).read_bytes()))
    return {'image_count': len(images), 'rows': len(counts), 'images_per_row': counts,
            'columns': columns, 'preserved_labels': len(labels),
            'note': 'Existing group structure replaced; image traversal order and panel annotations retained. Standalone labels placed after image rows.'}


def set_letter_position(path, placement):
    """Set the authoritative figure position, not a replaceable corner annotation."""
    from pyfigures.mcp_tools.core import _encode_str
    position = ' '.join(placement.lower().replace('-', ' ').split())
    if position not in ('top left', 'top right', 'bottom left', 'bottom right'):
        raise ValueError('Use top left, top right, bottom left or bottom right')
    root = ET.fromstring(tools.get_xml(path))
    font = root.find('SerializableQFont')
    if font is None:
        font = ET.SubElement(root, 'SerializableQFont')
    field = font.find('placement')
    if field is None:
        field = ET.SubElement(font, 'placement')
    field.text = _encode_str(position)
    count = 0
    for annotation in root.iter('TAText2D'):
        if _decode(annotation.findtext('is_letter')) is True:
            field = annotation.find('placement')
            if field is None:
                field = ET.SubElement(annotation, 'placement')
            field.text = position
            count += 1
    checked(tools.write_xml(path, ET.tostring(root, encoding='unicode')))
    return {'letter_position': position, 'existing_letters_updated': count}
