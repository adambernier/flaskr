import pytest

from flaskr.db import get_db


def test_index(client, auth):
    response = client.get("/")
    assert b"Log In" in response.data
    #assert b"Register" in response.data

    auth.login()
    response = client.get("/")
    assert b"test title" in response.data
    assert b"by test on 2019-01-01" in response.data
    assert b"test body" in response.data
    assert b'href="/test-title/update"' in response.data


@pytest.mark.parametrize("path", ("/create", "blog/test-title/update", "/test-title/delete"))
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers["Location"] == "http://localhost/auth/login"


def test_author_required(app, client, auth):
    # change the post author to another user
    with app.app_context():
        db = get_db()
        db.execute("UPDATE post SET author_id = 2 WHERE id = 1;")
        post_title = db.execute("SELECT title FROM post WHERE id = 1;").fetchone()

    auth.login()
    # current user can't modify other user's post
    assert client.post(f"/{post_title}/update").status_code == 403
    assert client.post(f"/{post_title}/delete").status_code == 403
    # current user doesn't see edit link
    assert b'href="/{}/update"'.format(post_title) not in client.get("/").data


@pytest.mark.parametrize("path", ("blog/2/update", "/2/delete"))
def test_exists_required(client, auth, path):
    auth.login()
    assert client.post(path).status_code == 404


def test_create(client, auth, app):
    auth.login()
    assert client.get("blog/create").status_code == 200
    client.post("blog/create", data={"title": "created", "body": ""})

    with app.app_context():
        db = get_db()
        db.execute("SELECT COUNT(id) as cnt FROM post")
        count = db.fetchone()['cnt']
        assert count == 2


def test_update(client, auth, app):
    auth.login()
    assert client.get("blog/test-title/update").status_code == 200
    client.post("blog/test-title/update", data={"title": "updated", "body": ""})

    with app.app_context():
        db = get_db()
        db.execute("SELECT * FROM post WHERE id = 1;")
        post = db.fetchone()
        assert post["title"] == "updated"


@pytest.mark.parametrize("path", ("blog/create", "blog/test-title/update"))
def test_create_update_validate(client, auth, path):
    auth.login()
    response = client.post(path, data={"title": "", "body": ""})
    assert b"Title is required." in response.data


def test_delete(client, auth, app):
    auth.login()
    with app.app_context():
        db = get_db()
        db.execute("SELECT max(id) as max_id FROM post;")
        post_id = db.fetchone()['max_id']
        response = client.post(f"blog/{post_id}/delete")
        #assert response.headers["Location"] == "http://localhost/"

        #db = get_db()
        db.execute("SELECT * FROM post WHERE id = %s;",(post_id,))
        post = db.fetchone()
        assert post is None
