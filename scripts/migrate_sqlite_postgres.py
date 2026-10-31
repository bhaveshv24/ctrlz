"""Copy a stopped deployment's SQLite data to an EMPTY Postgres target. Never deletes source data."""
import argparse
import os
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import insert, select, func, text
from ctrlz.accounts import Accounts
from ctrlz.database import postgres_url
from ctrlz.store import Store, Base


def migrate(root, operator):
    url = os.environ['DATABASE_URL']
    if not postgres_url(url):raise ValueError('DATABASE_URL must point to Postgres')
    source = root/'accounts.db'
    if not source.is_file():raise ValueError('Source accounts.db is missing')
    accounts = Accounts(root, url)
    with sqlite3.connect(source) as old:
        old.row_factory = sqlite3.Row
        account_rows = {table:[dict(row) for row in old.execute(f'SELECT * FROM {table}')] for table in ('users','sessions','attempts')}
    sources = [('operator', operator)] + [(u['id'], root/'workspaces'/u['id']/'workspace.db') for u in account_rows['users'] if u['role'] != 'admin']
    stores = [(Store('sqlite:///'+str(path.resolve())), Store(url, namespace=namespace), namespace) for namespace, path in sources if path.is_file()]
    # One transaction across all private schemas: any error rolls back every copied row.
    try:
        with accounts.engine.begin() as target:
            if target.scalar(text('SELECT COUNT(*) FROM ctrlz_accounts.users')):
                raise ValueError('Target already has accounts; refusing to overwrite')
            for old, new, namespace in stores:
                target.execution_options(schema_translate_map={None:'ctrlz_workspace_'+namespace})
                with old.engine.connect() as source_db:
                    for table in Base.metadata.sorted_tables:
                        if target.scalar(select(func.count()).select_from(table)):
                            raise ValueError('Target workspace is not empty; refusing to overwrite')
                    for table in Base.metadata.sorted_tables:
                        rows = list(source_db.execute(select(table)).mappings())
                        if rows:target.execute(insert(table), [dict(row) for row in rows])
                        if table.name in {'events','monitor_probes'}:
                            schema = 'ctrlz_workspace_'+namespace
                            target.execute(text(f"SELECT setval(pg_get_serial_sequence('{schema}.{table.name}', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {schema}.{table.name}"))
            for table, rows in account_rows.items():
                if not rows:continue
                columns = ','.join(rows[0])
                values = ','.join(':'+column for column in rows[0])
                target.execute(text(f'INSERT INTO ctrlz_accounts.{table} ({columns}) VALUES ({values})'), rows)
    finally:
        for old, new, _ in stores:
            old.engine.dispose();new.engine.dispose()
    print('Copy complete. Source files retained. Verify accounts and workspace counts before switching production.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--operator-db', type=Path, required=True)
    args = parser.parse_args()
    migrate(args.data_dir.resolve(), args.operator_db.resolve())
