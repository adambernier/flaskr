import os

import psycopg2
import urllib.parse as urlparse

from flask import Flask, render_template, send_from_directory 
from flask_login import LoginManager
#from flask_misaka import Misaka
from flaskext.markdown import Markdown 

from elasticsearch import Elasticsearch

from .auth import User

def create_app(test_config=None):
    #md = Misaka(ext=('no-intra-emphasis',))
    
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True, static_folder='static')
    app.es = Elasticsearch([os.environ.get('SEARCHBOX_SSL_URL')])
    app.jinja_env.filters['zip'] = zip
    #app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 # cache issue
    
    # User session management setup
    # https://flask-login.readthedocs.io/en/latest
    login_manager = LoginManager()
    login_manager.init_app(app)
    
    #md.init_app(app)
    Markdown(app)
    
    from . import db
    db.init_app(app)
    
    from . import auth
    app.register_blueprint(auth.bp)
    
    from . import blog
    app.register_blueprint(blog.bp)
    app.add_url_rule('/', endpoint='index')
    
    from . import about 
    app.register_blueprint(about.bp)
    
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

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'
        
    @app.route('/googlef50b5373f53496a4.html')
    def googlef50b5373f53496a4():
        return send_from_directory(app.static_folder,'googlef50b5373f53496a4.html')

    @app.after_request
    def add_header(response):
        response.cache_control.max_age = 300
        response.cache_control.public = True
        return response

    return app

app = create_app()

# Flask-Login helper to retrieve a user from our db
@app.login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)
    
@app.errorhandler(404)
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404

