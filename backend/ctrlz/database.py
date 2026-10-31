"""Backend-only database connections; PostgreSQL tables live in private schemas."""
import re
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


def postgres_url(value):
    url = make_url(value)
    if url.get_backend_name() == 'postgresql' or url.drivername == 'postgres':
        url = url.set(drivername='postgresql+psycopg')
        if url.host and url.host.endswith(('.supabase.co', '.supabase.com')):
            url = url.update_query_dict({'sslmode':'require'})
        return url
    return None


def database_engine(value, schema=None):
    url = postgres_url(value)
    if url is None:
        return create_engine(value, connect_args={'check_same_thread':False, 'timeout':30})
    if schema is not None and not re.fullmatch(r'ctrlz_[a-z0-9_]+', schema):
        raise ValueError('Invalid private database schema')
    engine = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout':15}, hide_parameters=True)
    if schema:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            connection.execute(text(f'REVOKE ALL ON SCHEMA "{schema}" FROM PUBLIC'))
        engine = engine.execution_options(schema_translate_map={None:schema})
    return engine


def private_tables(engine, names):
    if engine.dialect.name != 'postgresql':return
    schema = engine.get_execution_options().get('schema_translate_map', {}).get(None)
    with engine.begin() as connection:
        for name in names:
            connection.execute(text(f'ALTER TABLE "{schema}"."{name}" ENABLE ROW LEVEL SECURITY'))
