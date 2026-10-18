"""Create consistent local SQLite backups; never copies API secrets."""
import sqlite3
import os
import time
from pathlib import Path

ROOT = Path(os.environ.get('NF_DATA_DIR') or Path(__file__).resolve().parent).resolve()


def backup_databases():
    destination = ROOT / 'backups' / str(time.time_ns())
    destination.mkdir(parents=True)
    count = 0
    for source in ROOT.glob('*.sqlite3'):
        original = sqlite3.connect(source)
        copied = sqlite3.connect(destination / source.name)
        try:
            original.backup(copied)
            if copied.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('Backup integrity check failed.')
        finally:
            copied.close()
            original.close()
        count += 1
    return destination, count


if __name__ == '__main__':
    path, count = backup_databases()
    print('Verified database backups:', count)
    print('Location:', path)
