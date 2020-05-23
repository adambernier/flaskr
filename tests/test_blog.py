import pytest

from flaskr.db import get_db


def test_index(client, auth):
    response = client.get("/blog",follow_redirects=True)
    assert b"Log In" in response.data
    with open('/home/adamcbernier/flask_blog/tests/response.data','wb') as f:
        f.write(response.data)
    #assert b"Register" in response.data

    #auth.login()
    #response = client.get("/blog",follow_redirects=True)
    assert b"test title" in response.data
    assert b"2019-01-01" in response.data
    #assert b"test body" in response.data
    #assert b'href="blog/test-title/update"' in response.data


@pytest.mark.parametrize("path", ("/blog/create", "/blog/test-title/update", "/blog/1/delete"))
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers["Location"] == "http://localhost/auth/login"


def test_author_required(app, client, auth):
    # change the post author to another user
    with app.app_context():
        db = get_db()
        db.execute("UPDATE post SET author_id = 2 WHERE id = 1;")
        db.execute("SELECT id, title_slug FROM post WHERE id = 1;")
        post_id, post_title_slug = db.fetchone()
        print(post_id)
        print(post_title_slug)

    #auth.login()
    # current user can't modify other user's post
    assert client.post(f"/blog/{post_title_slug}/update").status_code in (302,404) #403
    assert client.post(f"/blog/{post_id}/delete").status_code in (302,404) #403
    # current user doesn't see edit link
    assert b'href="/blog/test-title/update"' not in client.get("/").data


@pytest.mark.parametrize("path", ("/blog/test-title/update", "/blog/2/delete"))
def test_exists_required(client, auth, path):
    auth.login()
    assert client.post(path).status_code in (302,404)


def test_create(client, auth, app):
    #auth.login()
    assert client.get("/blog/create").status_code in (200,302)
    client.post("/blog/create", data={"title": "created", "body": ""})

    with app.app_context():
        db = get_db()
        db.execute("SELECT COUNT(id) as cnt FROM post;")
        count = db.fetchone()['cnt']
        assert count == 1


# ~ def test_update(client, auth, app):
    # ~ #auth.login()
    # ~ assert client.get("/blog/test-title/update").status_code in (200,302)
    # ~ client.post("/blog/test-title/update", data={"title": "updated", "body": ""})

    # ~ with app.app_context():
        # ~ db = get_db()
        # ~ db.execute("SELECT title FROM post WHERE id = 1;")
        # ~ post = db.fetchone()
        # ~ assert post["title"] == "updated"


@pytest.mark.parametrize("path", ("/blog/create", "/blog/test-title/update"))
def test_create_update_validate(client, auth, path):
    #auth.login()
    response = client.post(path, data={"title": "", "body": ""})
    assert b"Title is required." in response.data


def test_delete(client, auth, app):
    #auth.login()
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
