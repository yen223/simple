""" simple """

# python imports
import re
import datetime
import os
from functools import wraps
from unicodedata import normalize

# web stuff and markdown imports
import markdown
from flask.ext.sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash
from flask import render_template, request, Flask, flash, redirect, url_for, \
                  abort, jsonify, Response, make_response
from werkzeug.contrib.cache import FileSystemCache, NullCache

app = Flask(__name__)
app.config.from_object('settings')
db = SQLAlchemy(app)
cache_directory = os.path.dirname(__file__)
try:
    cache = FileSystemCache(os.path.join(cache_directory, "cache"))
except Exception,e:
    print "Could not create cache folder, caching will be disabled."
    print "Error: %s"%e
    cache = NullCache()



_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

MARKDOWN_PARSER = markdown.Markdown(extensions=['fenced_code'], 
                                    output_format="html5", 
                                    safe_mode=True)

class Post(db.Model):
    def __init__(self, title=None, created_at=None):
        if title:
            self.title = title
            self.slug = slugify(title)
        if created_at:
            self.created_at = created_at
            self.updated_at = created_at

    __tablename__ = "posts"
    id    = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String())
    slug  = db.Column(db.String(), unique=True)
    text  = db.Column(db.String(), default="")
    draft = db.Column(db.Boolean(), index=True, default=True)
    views = db.Column(db.Integer(), default=0)
    created_at = db.Column(db.DateTime, index=True)
    updated_at = db.Column(db.DateTime)

    def render_content(self):
        _cached = cache.get("post_%s"%self.id)
        if _cached is not None:
            return _cached
        text = MARKDOWN_PARSER.convert(self.text)
        cache.set("post_%s"%self.id, text)
        return text

    def set_content(self, content):
        cache.delete("post_%s"%self.id)
        self.text = content


try:
    db.create_all()
except Exception:
    pass

def is_admin():
    auth = request.authorization
    if not auth or not (auth.username == app.config["ADMIN_USERNAME"]
                        and check_password_hash(app.config["ADMIN_PASSWORD"], 
                                                auth.password)):
        return False
    return True

def requires_authentication(func):
    """ function decorator for handling authentication """
    @wraps(func)
    def _auth_decorator(*args, **kwargs):
        """ does the wrapping """
        if not is_admin():
            return Response("Could not authenticate you", 
                            401, 
                            {"WWW-Authenticate":'Basic realm="Login Required"'})
        return func(*args, **kwargs)

    return _auth_decorator
@app.route("/test")
def testpost():
    return render_template("test_post.html")

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/blog/")
def index():
    """ Index Page. Here is where the magic starts """
    page = request.args.get("page", 0, type=int)
    posts_master = db.session.query(Post)\
                       .filter_by(draft=False)\
                       .order_by(Post.created_at.desc())
    
    posts_count = posts_master.count()

    posts = posts_master\
                .limit(app.config["POSTS_PER_PAGE"])\
                .offset(page * app.config["POSTS_PER_PAGE"])\
                .all()

    # Sorry for the verbose names, but this seemed like a sensible
    # thing to do.
    last_possible_post_on_page = page * app.config["POSTS_PER_PAGE"]\
                               + app.config["POSTS_PER_PAGE"]
    there_is_more = posts_count > last_possible_post_on_page
    return render_template("index.html", 
                           posts=posts, 
                           now=datetime.datetime.now(),
                           is_more=there_is_more, 
                           current_page=page,
                           is_admin=is_admin())

@app.route("/about")
def show_about_page():
    """Display the About page"""
    return render_template("about.html")

'''@app.route("/style.css")
def render_font_style():
    t = render_template("font_style.css",
                            font_name=app.config["FONT_NAME"])
    return Response(t, mimetype="text/css")'''

@app.route("/<int:post_id>")
def view_post(post_id):
    """ view_post renders a post and returns the Response object """
    try:
        post = db.session.query(Post).filter_by(id=post_id, draft=False).one()
    except Exception:
        return abort(404)

    db.session.query(Post)\
        .filter_by(id=post_id)\
        .update({Post.views:Post.views + 1})
    db.session.commit()

    return render_template("view.html", post=post, is_admin=is_admin())

@app.route("/<slug>")
def view_post_slug(slug):
    try:
        post = db.session.query(Post).filter_by(slug=slug, draft=False).one()
    except Exception:
        #TODO: Better exception
        return abort(404)

    if not any(botname in request.user_agent.string for botname in 
                ['Googlebot',  'Slurp',         'Twiceler',     'msnbot',
                 'KaloogaBot', 'YodaoBot',      '"Baiduspider',
                 'googlebot',  'Speedy Spider', 'DotBot']):
        db.session.query(Post)\
            .filter_by(slug=slug)\
            .update({Post.views:Post.views+1})
        db.session.commit()

    pid = request.args.get("pid", "0")
    return render_template("view.html", post=post, pid=pid, is_admin=is_admin())

@app.route("/new", methods=["POST", "GET"])
@requires_authentication
def new_post():
    post = Post(title=request.form.get("title","untitled"),
                created_at=datetime.datetime.now())

    db.session.add(post)
    db.session.commit()

    return redirect(url_for("edit", post_id=post.id))

@app.route("/edit/<int:post_id>", methods=["GET","POST"])
@requires_authentication
def edit(post_id):
    try:
        post = db.session.query(Post).filter_by(id=post_id).one()
    except Exception:
        #TODO: better exception
        return abort(404)

    if request.method == "GET":
        return render_template("edit.html", post=post)
    else:
        if post.title != request.form.get("post_title", ""):
            post.title = request.form.get("post_title","")
            post.slug = slugify(post.title)
        post.set_content(request.form.get("post_content",""))
        post.updated_at = datetime.datetime.now()

        if any(request.form.getlist("post_draft", type=int)):
            post.draft = True
        else:
            post.draft = False

        db.session.add(post)
        db.session.commit()
        return redirect(url_for("edit", post_id=post_id))

@app.route("/delete/<int:post_id>", methods=["GET","POST"])
@requires_authentication
def delete(post_id):
    try:
        post = db.session.query(Post).filter_by(id=post_id).one()
    except Exception:
        # TODO: define better exceptions for db failure.
        flash("Error deleting post ID %s"%post_id, category="error")
    else:
        db.session.delete(post)
        db.session.commit()

    return redirect(request.args.get("next","") 
        or request.referrer 
        or url_for('index'))

@app.route("/admin", methods=["GET", "POST"])
@requires_authentication
def admin():
    drafts = db.session.query(Post)\
                 .filter_by(draft=True)\
                 .order_by(Post.created_at.desc()).all()
    posts  = db.session.query(Post)\
                 .filter_by(draft=False)\
                 .order_by(Post.created_at.desc()).all()
    return render_template("admin.html", drafts=drafts, posts=posts)

@app.route("/admin/save/<int:post_id>", methods=["POST"])
@requires_authentication
def save_post(post_id):
    try:
        post = db.session.query(Post).filter_by(id=post_id).one()
    except Exception:
        # TODO Better exception
        return abort(404)
    if post.title != request.form.get("title", ""):
        post.title = request.form.get("title","")
        post.slug = slugify(post.title)
    post.set_content(request.form.get("content", ""))
    post.updated_at = datetime.datetime.now()
    db.session.add(post)
    db.session.commit()
    return jsonify(success=True)

@app.route("/preview/<int:post_id>")
@requires_authentication
def preview(post_id):
    try:
        post = db.session.query(Post).filter_by(id=post_id).one()
    except Exception:
        # TODO: Better exception
        return abort(404)

    return render_template("post_preview.html", post=post)

@app.route("/posts.rss")
def feed():
    posts = db.session.query(Post)\
                .filter_by(draft=False)\
                .order_by(Post.created_at.desc())\
                .limit(10)\
                .all()

    response = make_response(render_template('index.xml', posts=posts))
    response.mimetype = "application/xml"
    return response

def slugify(text, delim=u'-'):
    """Generates an slightly worse ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = normalize('NFKD', unicode(word)).encode('ascii', 'ignore')
        if word:
            result.append(word)
    slug = unicode(delim.join(result))
    # This could have issues if a post is marked as draft, then live, then 
    # draft, then live and there are > 1 posts with the same slug. Oh well.
    count = db.session.query(Post).filter_by(slug=slug).count()
    if count > 0:
        return "%s%s%s" % (slug, delim, count)
    else:
        return slug

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == "__main__":
    # Listen on all interfaces. This is so I could view the page on my iPhone/WP7 *not* so you can deploy using this file.

    #app.run(host="0.0.0.0")
    app.run(debug=True)
