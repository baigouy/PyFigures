"""Read-only evidence added to successful tool results; never rewrites intent."""
import json
from pathlib import Path

def native_font_check(family):
    # The native list_fonts subprocess has the platform font DB; offscreen Qt does not.
    from .original_registry import registry
    value=registry()['list_fonts'].fn(query=family)
    report=json.loads(value) if isinstance(value,str) else value
    status=report.get('font_check') if isinstance(report,dict) else None
    if not isinstance(status,dict) or not isinstance(status.get('installed'),bool):
        raise ValueError('No verified installation status')
    if str(status.get('requested','')).casefold()!=str(family).casefold():
        raise ValueError('Font report does not match the requested family')
    return status

def with_font_evidence(result,family,lookup=None):
    if not family:return result
    lookup=lookup or native_font_check
    try:
        status=lookup(family)
        if status['installed']:return result
        alternatives=', '.join(status.get('alternatives',[])) or 'none reported'
        note=("Requested font "+repr(family)+" is not installed; drawn/exported as "+
              str(status.get('drawn_as','unknown'))+". Installed alternatives: "+
              alternatives+". Requested family retained.")
        fields={'font_check':status,'note':note}
    except Exception as exc:
        fields={'font_check_error':str(exc),'note':'Font installation could not be verified; do not claim the requested font is installed.'}
    value=dict(result) if isinstance(result,dict) else {'result':result}
    if value.get('note'):fields['note']=str(value['note'])+' '+fields['note']
    value.update(fields)
    # Model output bounds keep the prefix. Never hide limitations after a large snapshot.
    return {**fields, **value}

def compact_font_inventory(result,limit=20):
    report=json.loads(result) if isinstance(result,str) else result
    if not isinstance(report,dict) or not isinstance(report.get('installed_families'),list):
        return result
    report=dict(report);families=report['installed_families']
    preferred=['Arial','Helvetica','TeX Gyre Heros','Nimbus Sans','Arimo','Liberation Sans','DejaVu Sans','Calibri','Segoe UI']
    front=[name for name in preferred if name in families]
    sample=(front+[name for name in families if name not in front])[:limit]
    report.update(installed_families=sample,total_count=report.get('count',len(families)),
                  returned_count=len(sample),truncated=len(families)>len(sample),
                  guidance='Sample only; pass query to filter the full installed font list.')
    return report

def caption_evidence(path):
    try:
        value=json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(value.get('caption'),str):raise ValueError('No stored caption text')
        return {'caption_text':value['caption'],'caption_title':value.get('title'),
                'caption_markdown':value.get('caption_markdown'),
                'caption_ends_with_period':value['caption'].endswith('.')}
    except (OSError,ValueError,TypeError) as exc:
        return {'caption_readback_error':str(exc)}
