"""Versioned recovery copies, written only below the prototype runtime directory."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from pyfigures.atomic_io import write_atomic


class Recovery:
    def __init__(self, session, state_dir):
        self.session = session
        self.root = Path(state_dir) / 'recovery'
        self.folder = self.root / session.id
        self.folder.mkdir(parents=True, exist_ok=True)
        self.latest = None
        self.error = None

    def capture(self):
        s, w = self.session, self.session.window
        path = self.folder / f'revision_{s.revision:06d}.pyf'
        try:
            w._save_state_to_file(str(path))
            base = str(path.with_suffix(''))
            w._copy_sidecars(w._sidecar_base(), base)
            staged = s.runtime / ('original_' + s.id) / 'current.pyf'
            if staged.exists():
                w._copy_sidecars(str(staged.with_suffix('')), base)
            manifest = {'session_id': s.id, 'revision': s.revision, 'snapshot': str(path),
                        'source_path': w.current_file, 'unsaved': w._dirty,
                        'created_at': datetime.now(timezone.utc).isoformat(),
                        'note': 'Recovery copy; original source file is not automatically saved.'}
            write_atomic(str(self.folder / 'latest.json'), json.dumps(manifest, indent=2))
            write_atomic(str(path.with_suffix('.recovery.json')), json.dumps(manifest, indent=2))
            self.latest, self.error = str(path), None
            # Retain the newest 20 document versions per session, with their sidecars.
            for old in sorted(self.folder.glob('revision_*.pyf'))[:-20]:
                for sibling in self.folder.glob(old.stem + '.*'):
                    if sibling.is_file():
                        sibling.unlink()
        except Exception as exc:
            self.error = str(exc)

    def list(self):
        found = []
        for path in self.root.glob('*/latest.json'):
            try:
                found.append(json.loads(path.read_text(encoding='utf-8')))
            except (OSError, ValueError):
                continue
        return sorted(found, key=lambda item: item['created_at'], reverse=True)[:30]

    def resolve(self, snapshot):
        path = Path(snapshot).resolve()
        if not path.is_relative_to(self.root.resolve()) or path.suffix.lower() != '.pyf' or not path.is_file():
            raise ValueError('Choose an existing .pyf from the recovery folder')
        return path
