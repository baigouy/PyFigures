"""Read-only technical readiness evidence from the original native checks."""
import hashlib,re
import xml.etree.ElementTree as ET
from pathlib import Path

def review_file(path,arguments):
    from .original_registry import registry
    path=Path(path)
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    allowed={'journal','column','width_mm','min_dpi'}
    if set(arguments)-allowed:raise ValueError('Unknown readiness argument')
    common={k:v for k,v in arguments.items() if v is not None}
    outputs={};checks={};blockers=[]
    for name in ('check_resolution','check_journal_compliance'):
        from .plot_lifecycle import figure_scope
        with figure_scope():text=str(registry()[name].fn(pyf_path=str(path),**common))
        outputs[name]=text
        errors=text.startswith('ERROR') or 'unknown source size' in text.lower()
        failed=bool(re.search(r'^\s*\[FAIL\]',text,re.M))
        if name=='check_journal_compliance':
            passed='VERDICT: the mechanical checks pass.' in text or 'VERDICT: READY' in text or 'VERDICT: COMPLIANT' in text or ('COMPLIANT' in text and 'NOT' not in text)
        else:
            passed=not failed and not errors and ('meet ' in text or 'No raster panels found' in text)
        checks[name]={'status':'incomplete' if errors else 'fail' if failed else 'pass' if passed else 'incomplete','report':text}
        blockers.extend(line.strip() for line in text.splitlines() if re.match(r'\s*\[FAIL\]',line))
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before,'A read-only quality check changed its snapshot'
    if any(c['status']=='fail' for c in checks.values()):status='blocked'
    elif all(c['status']=='pass' for c in checks.values()):status='technical_checks_passed'
    else:status='incomplete'
    if not any(n.findtext('isText')!='True' for n in ET.parse(path).getroot().iter('Image2D')):
        status='incomplete';blockers.append('The figure has no image panels to review.')
    return {'kind':'submission_review','status':status,'checks':checks,'blockers':blockers,
        'target':common,'read_only':True,'snapshot_sha256':before,
        'scope':'Technical journal/resolution checks only; scientific content and statistical assumptions are not certified.'}

def review_live(session,arguments):
    import json,tempfile
    session.sync()
    if arguments:session._turn_submission_target=dict(arguments)
    else:arguments=dict(getattr(session,'_turn_submission_target',{}) or {})
    key=(session.revision,json.dumps(arguments,sort_keys=True))
    cache=getattr(session,'_submission_review_cache',None)
    if cache and cache[0]==key:return cache[1]
    with tempfile.TemporaryDirectory(prefix='quality_',dir=session.runtime) as folder:
        target=Path(folder)/'snapshot.pyf'
        session.window._save_state_to_file(str(target))
        session.window._copy_sidecars(session.window._sidecar_base(),str(target.with_suffix('')))
        current=session.runtime/('original_'+session.id)/'current'
        session.window._copy_sidecars(str(current),str(target.with_suffix('')))
        result=review_file(target,arguments)
    result.update(review_revision=session.revision,panel_count=len(session.snapshot()['panel_references']))
    if not result['panel_count']:
        result.update(status='incomplete',blockers=['The figure has no image panels to review.'])
    session._submission_review_cache=(key,result)
    return result
