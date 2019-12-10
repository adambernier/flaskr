import os
#import sqlite3
import urllib.parse as urlparse

import click
import psycopg2
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if 'db' not in g:
        url = urlparse.urlparse(os.environ['DATABASE_URL'])
        dbname = url.path[1:]
        user = url.username
        password = url.password
        host = url.hostname
        port = url.port

        g.db = psycopg2.connect(
                    dbname=dbname,
                    user=user,
                    password=password,
                    host=host,
                    port=port
                    )
        #g.db = sqlite3.connect(
        #    current_app.config['DATABASE'],
        #    detect_types=sqlite3.PARSE_DECLTYPES
        #)
        #g.db.row_factory = sqlite3.Row

    return g.db


def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    db = get_db()
    
    with current_app.open_resource('schema.sql') as f:
        db.execute(f.read().decode('utf8'))
        #db.executescript(f.read().decode('utf8'))


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
