import datetime as dt
import itertools as it

from flask import (
    Blueprint, current_app, flash, g, json, jsonify, redirect, 
    render_template, request, url_for
)
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)

from elasticsearch import helpers 
from psycopg2 import errors 
from slugify import slugify
from werkzeug.exceptions import abort, BadRequestKeyError

from flaskr.auth import login_required
from flaskr.db import get_db

def paginate(iterable, page_size):
    while True:
        i1, i2 = it.tee(iterable)
        iterable, page = (it.islice(i1, page_size, None),
                list(it.islice(i2, page_size)))
        if len(page) == 0:
            break
        yield page

bp = Blueprint('blog', __name__)

@bp.route('/')
@bp.route('/',defaults={'page':1})
@bp.route('/page/<int:page>')
def index(page=None):
    if not page:
        page = 1
    PAGINATION_SIZE = 3
    db = get_db()
    db.execute("""
        SELECT count(p.id) row_count, min(p.id) min_id
        FROM post p;
        """)
    result = db.fetchone()
    count, min_id = result['row_count'], result['min_id']
    offset = (page - 1) * PAGINATION_SIZE 
    db.execute("""
        SELECT p.id, title, title_slug, body, created, author_id, 
            username, role_id, pt.tags, pt.tag_slugs
         FROM post p
         JOIN (
             SELECT p2.id, ROW_NUMBER() OVER () rownum
             FROM post p2
         ) p2
         ON p2.id = p.id 
         JOIN usr u ON p.author_id = u.id
         LEFT JOIN (
             SELECT pt.post_id, string_agg(t.title, ' ') tags, 
                 string_agg(t.slug, ' ') tag_slugs
             FROM tag t
                 JOIN post_tag pt
                 ON pt.tag_id = t.id
             GROUP BY pt.post_id
         ) pt
         ON pt.post_id = p.id
         ORDER BY created DESC
         LIMIT %s
         OFFSET %s;""",
        (PAGINATION_SIZE,offset,)
    )
    posts = db.fetchall()
    try:
        if posts[-1]['id'] == min_id:
            last_post = True
        else:
            last_post = False
    except IndexError:
        last_post = True
        
    if current_user.is_authenticated:
        g.user = current_user
        #db.execute('SELECT role_id FROM usr WHERE id = %s;',
        #           (g.user['id'],))
        #user = db.fetchone()
        
    return render_template('blog/index.html',posts=posts,page=page,
        PAGINATION_SIZE=PAGINATION_SIZE,last_post=last_post)

@bp.route('/fts',defaults={'page':1})
@bp.route('/fts/<search_slug>/page/<int:page>')
def fts(page=None,search_slug=None):
    if not page:
        page = 1
    PAGINATION_SIZE = 3
    search = request.args.get('autocomplete')
    offset = (page - 1) * PAGINATION_SIZE 
    if not search:
        search = search_slug
    else:
        search = slugify(search)
    # begin fts 
    query = {
        "query": {
            "multi_match": {
                "query": search,
                "fields": ["post_body", "post_title", "post_tags"]
            }
        }
    }
    results = current_app.es.search(index="blog-index", 
                                    #doc_type="post", 
                                    body=query)
    scan = helpers.scan(current_app.es,query=query,scroll='1m',
                        index='blog-index')
    ids = tuple(sorted(scan_result['_id'] for scan_result in scan))
    if len(ids) == 0:
        abort(404,f"No posts with {search} in either body or title.")
    # end fts 
    placeholders = ",".join(["%s" for id in ids])
    qry = f"""
        SELECT count(p.id) row_count, min(p.id) min_id 
        FROM post p
        WHERE p.id in ({placeholders});
        """
    db = get_db()
    db.execute(qry,ids) # ids is a tuple
    result = db.fetchone()
    count, min_id = result['row_count'], result['min_id']
    
    qry = f"""
        SELECT p.id, title, body, created, author_id, username, role_id,
            pt.tags, pt.tag_slugs 
         FROM post p
         JOIN (
             SELECT p2.id, ROW_NUMBER() OVER () rownum
             FROM post p2
             WHERE p2.id IN ({placeholders})
         ) p2
         ON p2.id = p.id 
         JOIN usr u ON p.author_id = u.id
         LEFT JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') tags, 
                string_agg(t.slug, ' ') tag_slugs
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            GROUP BY pt.post_id
         ) pt
         ON pt.post_id = p.id
         WHERE p.id IN ({placeholders})
         ORDER BY created DESC
         LIMIT %s
         OFFSET %s;"""
    db.execute(qry,ids+ids+(PAGINATION_SIZE,offset,))
    posts = db.fetchall()
    try:
        if posts[-1]['id'] == min_id:
            last_post = True
        else:
            last_post = False
    except IndexError:
        last_post = True
    
    search_slug = slugify(search)
    
    return render_template('blog/index.html',posts=posts,page=page,
        PAGINATION_SIZE=PAGINATION_SIZE,last_post=last_post,
        search_slug=search_slug)

@bp.route('/create', methods=('GET', 'POST',))
@login_required
def create():
    if request.method == 'POST':
        title = request.form['title']
        title_slug = slugify(title)
        body = request.form['body']
        tags = request.form['tags']
        tags = tags.split(' ') # expand to allow other delimiters?
        tag_slugs = [slugify(tag) for tag in tags]
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute('''
                INSERT INTO post (title, title_slug, body, author_id, 
                                  thank_count)
                VALUES (%s,%s,%s,%s,%s) RETURNING id;''',
                (title,title_slug,body,g.user['id'],0)
            )
            post_id = db.fetchone()['id']
            tag_ids = []
            for tag,tag_slug in zip(tags,tag_slugs):
                try:                 
                    db.execute(
                        'INSERT INTO tag (title, slug)'
                        ' VALUES (%s,%s) RETURNING id;',
                        (tag, tag_slug,)
                    )
                    tag_ids.append(db.fetchone()['id'])
                except errors.UniqueViolation:
                    db.execute(
                        'SELECT id FROM tag WHERE slug = %s;',
                        (tag_slug,)
                    )
                    tag_ids.append(db.fetchone()['id'])
            db.executemany(
                'INSERT INTO post_tag (post_id, tag_id)'
                ' VALUES (%s,%s);',
                list(zip([post_id]*len(tag_ids),tag_ids))
            )
            # begin elasticsearch
            suggest = [word for word in title_slug.split('-')]
            suggest += [tag_slug for tag_slug in tag_slugs]
            doc = {
                    'post_author': g.user['id'],
                    'post_body': body,
                    'post_title': [word for word in title_slug.split('-')],
                    'post_tags': [tag_slug for tag_slug in tag_slugs],
                    'post_timestamp': dt.datetime.now(),
                    'suggest': suggest,
                }
            result = current_app.es.index(index="blog-index", 
                                          #doc_type='post', 
                                          id=post_id, 
                                          body=doc)
            current_app.es.indices.refresh(index='blog-index')
            # end elasticsearch
            return redirect(url_for('blog.index'))

    return render_template('blog/create.html')
    
@bp.route('/create_comment', methods=('POST',))
def create_comment():
    body = request.form['body']
    post_id = request.form['post_id']
    author_id = request.form['author_id']
    
    db = get_db()
    db.execute(
        'INSERT INTO post_comment (body, post_id, author_id)'
        ' VALUES (%s,%s,%s);',
        (body,post_id,author_id)
    )
    
    return redirect(url_for('blog.index'))

def get_post(title_slug, check_author=True):
    get_db().execute("""
        SELECT p.id, title, title_slug, body, created, author_id, username, 
            role_id, thank_count, pt.tags, pt.tag_slugs 
         FROM post p JOIN usr u ON p.author_id = u.id
         LEFT JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') tags, 
                string_agg(t.slug, ' ') tag_slugs 
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            GROUP BY pt.post_id
         ) pt
         ON pt.post_id = p.id
         WHERE p.title_slug = %s;""",
        (title_slug,)
    )
    post = get_db().fetchone()

    if post is None:
        abort(404, "Post id {0} doesn't exist.".format(id))

    #if check_author and post['author_id'] != g.user['id']:
    #    abort(403)
        
    get_db().execute("""
        SELECT c.id, body, created, username, c.author_id 
        FROM post_comment c
            LEFT JOIN usr u 
            ON u.id = c.author_id 
        WHERE c.post_id = %s;""", 
        (post['id'],)
    )
    comments = get_db().fetchall()

    return post, comments 
    
@bp.route('/<title_slug>/thank', methods=('POST',))
def thank(title_slug):
    if request.method == "POST":
        db = get_db()
        db.execute('''UPDATE post 
                      SET thank_count = thank_count + 1
                      WHERE title_slug = %s;''',(title_slug,))
        if db.rowcount == 1:
            db.execute('''
                SELECT thank_count 
                FROM post 
                WHERE title_slug = %s;''',(title_slug,))
            thank_count = db.fetchone()['thank_count']
            #return json.dumps({'status': 'success', 'thank_count': thank_count})
            return f'''<p id="click-response">Post thanked {thank_count} time(s).</p>'''
        else:
            return json.dumps({'status': 'record not updated'})
        return redirect(url_for('blog.detail'))
    
#@bp.route('/<int:id>/detail',methods=('GET',))
@bp.route('/<title_slug>',methods=('GET',))
def detail(title_slug):
    post, comments = get_post(title_slug)
    try:
        thank_count = request.args['thank_count']
    except BadRequestKeyError:
        thank_count = post['thank_count']
    return render_template('blog/detail.html', post=post, 
                           comments=comments, thank_count=thank_count)
    
#@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@bp.route('/<title_slug>/update', methods=('GET', 'POST'))
@login_required
def update(title_slug):
    post, comments = get_post(title_slug)

    if request.method == 'POST':
        old_title_slug = title_slug
        
        title = request.form['title']
        title_slug = slugify(title)
        body = request.form['body']
        tags = request.form['tags']
        tags = tags.split(' ') # expand to allow other delimiters?
        tag_slugs = [slugify(tag) for tag in tags]
        error = None

        if not title:
            error = 'Title is required.'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE post SET title = %s, title_slug = %s, body = %s'
                ' WHERE title_slug = %s RETURNING id;',
                (title, title_slug, body, old_title_slug)
            )
            id = db.fetchone()['id']
            # doesn't cost a lot to just delete any existing tags 
            db.execute('DELETE FROM post_tag where post_id = %s;', (id,))
            tag_ids = []
            for tag,tag_slug in zip(tags,tag_slugs):
                try:                 
                    db.execute(
                        'INSERT INTO tag (title, slug)'
                        ' VALUES (%s,%s) RETURNING id;',
                        (tag, tag_slug,)
                    )
                    tag_ids.append(db.fetchone()['id'])
                except errors.UniqueViolation:
                    db.execute(
                        'SELECT id FROM tag WHERE slug = %s;',
                        (tag_slug,)
                    )
                    tag_ids.append(db.fetchone()['id'])
            db.executemany(
                'INSERT INTO post_tag (post_id, tag_id)'
                ' VALUES (%s,%s);',
                list(zip([id]*len(tag_ids),tag_ids))
            )
            # begin elasticsearch
            suggest = [word for word in title_slug.split('-')]
            suggest += [tag_slug for tag_slug in tag_slugs]
            doc = {
                    'post_author': g.user['id'],
                    'post_body': body,
                    'post_title': [word for word in title_slug.split('-')],
                    'post_tags': [tag_slug for tag_slug in tag_slugs],
                    'post_timestamp': dt.datetime.now(),
                    'suggest': suggest,
                }
            result = current_app.es.index(index="blog-index", 
                                          #doc_type='post', 
                                          id=id, 
                                          body=doc)
            current_app.es.indices.refresh(index='blog-index')
            # end elasticsearch
            return redirect(url_for('blog.index'))

    return render_template('blog/update.html', post=post)

@bp.route('/tag',defaults={'page':1})
@bp.route('/tag/<tag_slug>/page/<int:page>')
def tag(page=None,tag_slug=None):
    if not page:
        page = 1
    PAGINATION_SIZE = 3
    offset = (page - 1) * PAGINATION_SIZE 
    
    if not tag_slug:
        tag_slug = request.args.get('autocomplete')
    
    tag_slug = tag_slug.strip()
    
    db = get_db()
    db.execute("""
        SELECT count(distinct p.id) row_count, min(p.id) min_id 
        FROM post p
        JOIN (
            SELECT pt.post_id 
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            WHERE t.slug = %s
            GROUP BY pt.post_id
        ) pt
        ON pt.post_id = p.id
        """,(tag_slug,))
    result = db.fetchone()
    count, min_id = result['row_count'], result['min_id']
    db.execute("""
        SELECT p.id, title, body, created, author_id, username, role_id,
               pt.tags, pt.tag_slugs, pt_addl.addl_tags, pt_addl.addl_tag_slugs
         FROM post p
         JOIN (
             SELECT p2.id, ROW_NUMBER() OVER () rownum
             FROM post p2
             JOIN (
                SELECT pt.post_id 
                FROM tag t
                    JOIN post_tag pt
                    ON pt.tag_id = t.id
                WHERE t.slug = %s
                GROUP BY pt.post_id
             ) pt
             ON pt.post_id = p2.id
         ) p2
         ON p2.id = p.id 
         JOIN usr u ON p.author_id = u.id
         JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') tags, 
                string_agg(t.title, ' ') tag_slugs 
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            WHERE t.slug = %s
            GROUP BY pt.post_id
         ) pt
         ON pt.post_id = p.id
         LEFT JOIN (
            SELECT pt.post_id, string_agg(t.title, ' ') addl_tags,
                string_agg(t.title, ' ') addl_tag_slugs
            FROM tag t
                JOIN post_tag pt
                ON pt.tag_id = t.id
            WHERE t.slug <> %s
            GROUP BY pt.post_id
         ) pt_addl
         ON pt_addl.post_id = p.id
         ORDER BY created DESC
         LIMIT %s
         OFFSET %s;""",
        (tag_slug,tag_slug,tag_slug,PAGINATION_SIZE,offset,)
    )
    posts = db.fetchall()
    try:
        if posts[-1]['id'] == min_id:
            last_post = True
        else:
            last_post = False
    except IndexError:
        last_post = True
    return render_template('blog/index.html',posts=posts,page=page,
        PAGINATION_SIZE=PAGINATION_SIZE,last_post=last_post,tag_slug=tag_slug)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    db = get_db()
    db.execute('DELETE FROM post_tag where post_id = %s;', (id,))
    db.execute('DELETE FROM post_comment where post_id = %s;', (id,))
    db.execute('DELETE FROM post WHERE id = %s;', (id,))
    return redirect(url_for('blog.index'))
    
@bp.route('/<int:id>/comment_delete', methods=('POST',))
@login_required
def comment_delete(id):
    db = get_db()
    db.execute('DELETE FROM post_comment where id = %s;', (id,))
    return redirect(url_for('blog.index'))

@bp.route('/autocomplete', methods=('GET',))
def autocomplete():
    search = request.args.get('q')
    
    # ~ db = get_db()
    # ~ db.execute('''
        # ~ SELECT title 
        # ~ FROM tag 
        # ~ WHERE slug like %s
        # ~ ORDER by title;''',
        # ~ ('%' + search + '%',)
        # ~ )
    # ~ tags = [t['slug'] for t in db.fetchall()]
    
    # this is regular search
    # ~ doc = {
        # ~ "query": {
            # ~ "multi_match": {
                # ~ "query": search,
                # ~ "fields": ["text", "title", "tags"]
                # ~ }
            # ~ }
        # ~ }
    doc = {
        "suggest": {
            "tag-suggestion" : {
                "prefix" : search, 
                "completion" : { 
                    "field" : "suggest" 
                }
            }
        }
    }
    results = current_app.es.search(index="blog-index",body=doc)
    #print(json.dumps(results, indent=4, sort_keys=True))
    matching_results = []
    try:
        for matching_result in results['suggest']['tag-suggestion'][0]['options']:
            matching_results.append(matching_result['text'])
    except IndexError:
        pass 
    
    return jsonify(matching_results=matching_results)

@bp.route('/privacy_policy')
def privacy_policy():
    privacy_language = '''
The following policy is intended to explain how your personal information will be treated when you use our site. Personal information includes your name, e-mail addresses, click-through activity and any other personal information you may provide here.

Email and other private information

When you decide to go through registration process in order to obtain personal user account at mechanical-meat.com, you are proposed to fill registration form which asks for your email and name. Your email is needed for us to complete registration process and to restore your account password if you will ask about it. We will not send you any spam messages. Actually, you will get emails from Mechanical Meat only if you chose to - it can be used to notify you about private messages, sent to you by other users, or satisfaction of your request or appearance of new comments to your articles etc.

Please, do not use your email address as your user-name unless you are fully aware of fact that it will become visible to all visitors of the site.
'''
    return render_template('blog/privacy_policy.html',privacy_language=privacy_language)

@bp.route('/robots.txt')
def robots():
    return render_template('robots.txt')

