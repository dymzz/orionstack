"""Read-only pgBackRest adapter. pgBackRest owns backup and restore execution."""
import json
import os
from pathlib import PurePosixPath
import re
import subprocess
from app.dataops.ports import DependencyUnavailable


class PgBackRest:
    def __init__(self, executable=None, stanza=None, repo=None, runner=None):
        self.executable = executable or os.getenv('ORIONSTACK_PGBACKREST_BIN', 'pgbackrest')
        self.stanza = stanza or os.getenv('ORIONSTACK_PGBACKREST_STANZA','')
        self.repo = repo or int(os.getenv('ORIONSTACK_PGBACKREST_REPO','1'))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',self.stanza) or not 1 <= self.repo <= 256:
            raise DependencyUnavailable('pgBackRest is not configured')
        self.runner = runner or subprocess.run

    def command(self, operation, *args):
        # All options are server-owned; no shell or caller-provided command.
        result = [self.executable, f'--stanza={self.stanza}', f'--repo={self.repo}', '--log-level-console=off']
        config = os.getenv('ORIONSTACK_PGBACKREST_CONFIG')
        if config: result.append('--config=' + config)
        return [*result, operation, *args]

    def _json(self, operation, *args):
        try:
            result = self.runner(self.command(operation,*args), capture_output=True, timeout=15, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if len(result.stdout) > 8*1024*1024: raise ValueError('Oversized repository response')
            return json.loads(result.stdout)
        except Exception: raise DependencyUnavailable('pgBackRest repository is unavailable') from None

    def info(self):
        try:
            items = self._json('info','--output=json')
            stanza = next(s for s in items if s['name'] == self.stanza)
            backups = []
            for item in stanza.get('backup',[]):
                label = item['label']; self.validate_label(label)
                backups.append({'backup_id':label,'type':item['type'],
                    'created_at':item.get('timestamp',{}).get('stop'),
                    'size_bytes':item.get('info',{}).get('repository',{}).get('size'),
                    'status':'failed' if item.get('error') else 'database_backup_recorded',
                    'recovery_status':'not_verified', 'object_storage_state':'not_recorded',
                    'restore_test':'not_run'})
            return {'provider':'pgbackrest','status':stanza.get('status',{}).get('message','unknown'),
                'items':backups, 'recovery_domain':'postgresql_and_object_storage'}
        except DependencyUnavailable: raise
        except Exception: raise DependencyUnavailable('Invalid pgBackRest repository metadata') from None

    @staticmethod
    def validate_label(label):
        if not re.fullmatch(r'[0-9]{8}-[0-9]{6}F(?:_[0-9]{8}-[0-9]{6}[DI])?',label):
            raise ValueError('Invalid pgBackRest backup ID')

    def files(self, backup_id):
        self.validate_label(backup_id)
        if backup_id not in {b['backup_id'] for b in self.info()['items']}: raise LookupError('Backup is unavailable')
        root = f'backup/{self.stanza}/{backup_id}'
        items = self._json('repo-ls','--output=json','--recurse',root)
        result=[]
        for name, item in items.items():
            path = PurePosixPath(name)
            if item.get('type') != 'file' or path.is_absolute() or '\\' in name or any(p in ('','..','.') for p in name.split('/')):
                continue
            result.append({'filename':name,'size_bytes':item.get('size')})
        return result

    def download(self, backup_id, filename):
        # Re-list before download. Never expose arbitrary repo paths (keys/config/WAL).
        if filename not in {f['filename'] for f in self.files(backup_id)}: raise LookupError('Backup file is unavailable')
        path = f'backup/{self.stanza}/{backup_id}/{filename}'
        try:
            process = subprocess.Popen(self.command('repo-get',path), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except OSError: raise DependencyUnavailable('pgBackRest download is unavailable') from None
        def stream():
            try:
                while data := process.stdout.read(1024*1024): yield data
                if process.wait(timeout=15): raise DependencyUnavailable('pgBackRest download failed')
            finally:
                process.stdout.close()
                if process.poll() is None: process.kill(); process.wait(timeout=5)
        return stream()
