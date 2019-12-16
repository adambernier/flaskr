import os

import psycopg2
import urllib.parse as urlparse

from flask import Flask
from flask_misaka import Misaka

def create_app(test_config=None):
    md = Misaka()
    
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 # cache issue
    
    md.init_app(app)
    
    from . import db
    db.init_app(app)
    
    from . import auth
    app.register_blueprint(auth.bp)
    
    from . import blog
    app.register_blueprint(blog.bp)
    app.add_url_rule('/', endpoint='index')
    
    url = urlparse.urlparse(os.environ['DATABASE_URL'])
    dbname = url.path[1:]
    user = url.username
    password = url.password
    host = url.hostname
    port = url.port
    
    app.config.from_pyfile(os.path.join('.','instance/config.py'),silent=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ['SECRET_KEY'],
        DATABASE=psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
            )
        #DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)
    
    # images 
    UPLOAD_DIR = os.path.join(app.instance_path,'uploads')
    os.makedirs(UPLOAD_DIR,exist_ok=True)
    ALLOWED_EXTENSIONS = set(['png', 'jpg'])
    app.config['UPLOAD_DIR'] = UPLOAD_DIR
    app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    return app
    
    @app.after_request
    def add_header(response):
        response.cache_control.max_age = 0
        return response

app = create_app()
