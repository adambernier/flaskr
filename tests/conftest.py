import os
#import tempfile
import urllib.parse as urlparse

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import pytest

from flaskr import create_app
from flaskr.db import get_db
from flaskr.db import init_db

# read in SQL for populating test data
#with open(os.path.join(os.path.dirname(__file__),"data.sql"),"rb") as f:
#    _data_sql = f.read().decode("utf8")
with open(os.path.join(os.path.dirname(__file__),"data.sql"),"rb") as f:
    _data_sql = f.read().decode('utf8')


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # create a temporary file to isolate the database for each test
    #db_fd, db_path = tempfile.mkstemp()
    url = urlparse.urlparse(os.environ['TEST_DATABASE_URL'])
    dbname = url.path[1:]
    user = url.username
    password = url.password
    host = url.hostname
    port = url.port

    con = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
                )
    con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    #g.db = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # create the app with common test config
    app = create_app({"TESTING": True, "DATABASE": con})

    # create the database and load test data
    with app.app_context():
        init_db()
        get_db().execute(_data_sql)
        #get_db().executescript(_data_sql)

    yield app

    # close and remove the temporary database
    #os.close(db_fd)
    #os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


class AuthActions(object):
    def __init__(self, client):
        self._client = client

    def login(self, username="test", password="test"):
        return self._client.post(
            "/auth/login", data={"username": username, "password": password}
        )

    def logout(self):
        return self._client.get("/auth/logout")


@pytest.fixture
def auth(client):
    return AuthActions(client)
