"""Poster/album "Source Data" consolidation bundle.

Mirrors pyfigures.mcp_server.export_source_data's role for a .pyf figure,
but for a whole poster/album: copies every page's background/image files
into out_dir/images (renamed by page + shape index so nothing collides) and
writes a portable copy of the document whose paths point at those copies —
the bundle reopens standalone, without depending on the original external
image files still being at their original location.

If a PosterImage was flattened from a .pyf (dropped in as a figure — see
poster_canvas._render_pyf_to_png / PosterImage.source_pyf), that .pyf's own
Source Data bundle is additionally nested inside the corresponding images/
entry (as out_dir/images/<name>_pyf_bundle/) — a bundle inside a bundle, so
the figure behind a photo stays traceable all the way to its own
panels/scripts/CSVs, not just the flattened PNG that's actually on the page.

Kept in its own module rather than folded into poster_headless.py since
it's the one place anything in pyfigures/poster/ reaches outside the
package (into pyfigures.mcp_server, itself Qt-free — see its own module
docstring) — everything else in this package stays self-contained.
"""
import json
import os
import shutil


def _unique_name(used, base):
    if base not in used:
        used.add(base)
        return base
    root, ext = os.path.splitext(base)
    k = 1
    candidate = f'{root}_{k}{ext}'
    while candidate in used:
        k += 1
        candidate = f'{root}_{k}{ext}'
    used.add(candidate)
    return candidate


def export_poster_source_data(canvas, poster_path, out_dir, dpi=300):
    """Consolidate *canvas* (already loaded from *poster_path*) into
    *out_dir*. Mutates the given canvas's shape/background paths in place
    (it's expected to be a throwaway instance created just for this export,
    never saved back over the original poster/album file). Returns a dict
    summarising what was written."""
    images_dir = os.path.join(out_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    used_names = set()
    manifest = []

    for pi, page in enumerate(canvas.pages):
        bg = page.background
        if bg is not None and bg.path and os.path.isfile(bg.path):
            base = _unique_name(used_names, f'p{pi + 1:02d}_background__{os.path.basename(bg.path)}')
            dest = os.path.join(images_dir, base)
            shutil.copy2(bg.path, dest)
            manifest.append({'page': pi, 'kind': page.kind, 'role': 'background',
                             'file': f'images/{base}'})
            bg.path = dest

        for si, shape in enumerate(page.shapes_to_draw):
            path = getattr(shape, 'path', None)
            if not path or not os.path.isfile(path):
                continue
            base = _unique_name(used_names, f'p{pi + 1:02d}_s{si:02d}__{os.path.basename(path)}')
            dest = os.path.join(images_dir, base)
            shutil.copy2(path, dest)
            entry = {'page': pi, 'kind': page.kind, 'shape_index': si, 'role': 'image',
                     'file': f'images/{base}'}

            source_pyf = getattr(shape, 'source_pyf', None)
            if source_pyf and os.path.isfile(source_pyf):
                # Inception: this image is a flattened .pyf — bundle that
                # figure's own source data too, nested right next to its
                # flattened copy, not just the PNG that's actually on the page.
                bundle_name = os.path.splitext(base)[0] + '_pyf_bundle'
                bundle_dir = os.path.join(images_dir, bundle_name)
                entry['source_pyf'] = os.path.basename(source_pyf)
                try:
                    from pyfigures.mcp_server import export_source_data
                    nested = export_source_data(source_pyf, bundle_dir, dpi=dpi)
                    if isinstance(nested, str) and nested.startswith('ERROR'):
                        entry['source_pyf_bundle_error'] = nested
                    else:
                        entry['source_pyf_bundle'] = f'images/{bundle_name}'
                except Exception as exc:
                    entry['source_pyf_bundle_error'] = f'{type(exc).__name__}: {exc}'

            shape.path = dest
            manifest.append(entry)

    doc_ext = 'pyfalbum' if canvas.suggested_filetype() == 'pyfalbum' else 'pyfposter'
    doc_name = os.path.splitext(os.path.basename(poster_path))[0] + f'.{doc_ext}'
    doc_path = os.path.join(out_dir, doc_name)
    canvas.file_path = None
    canvas.save(doc_path, filetype=doc_ext)

    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({
            'source_poster': os.path.basename(poster_path),
            'document': doc_name,
            'page_count': len(canvas.pages),
            'files': manifest,
        }, f, ensure_ascii=False, indent=2)

    lines = [f'Source data for: {os.path.basename(poster_path)}', '']
    for e in manifest:
        line = f"Page {e['page'] + 1} ({e['kind']})"
        if 'shape_index' in e:
            line += f", shape {e['shape_index']}"
        line += f": {e['file']}"
        if e.get('source_pyf'):
            line += f' (flattened from {e["source_pyf"]}'
            if e.get('source_pyf_bundle'):
                line += f', bundled at {e["source_pyf_bundle"]}'
            elif e.get('source_pyf_bundle_error'):
                line += f', bundling failed: {e["source_pyf_bundle_error"]}'
            line += ')'
        lines.append(line)
    with open(os.path.join(out_dir, 'MANIFEST.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    return {
        'output_dir': out_dir,
        'document': doc_path,
        'page_count': len(canvas.pages),
        'n_files': len(manifest),
        'nested_pyf_bundles': sum(1 for e in manifest if e.get('source_pyf_bundle')),
    }
