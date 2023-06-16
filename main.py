from flask import Flask, render_template, redirect, url_for, flash, abort, request
from functools import wraps
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
import os

# Building application using flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)

# email id
email = os.environ.get("Email")

# collecting data from environment
uri = os.getenv("DATABASE_URL")
if uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql://", 1)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(uri,'sqlite:///user.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.app_context().push()
db = SQLAlchemy(app)

# flask login with app
loginmanager = LoginManager()
loginmanager.init_app(app)

# avatar profile
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# admin only decorator
def admin_only(f):
    @wraps(f)
    def check_user(*args,**kwargs):
        if current_user.id != 1:
            return abort(403)
        else:
            return f(*args,**kwargs)
    return check_user

# Table for collecting user information
class User(UserMixin,db.Model):
    __tablename__='user'
    id = db.Column(db.Integer,primary_key=True)
    email = db.Column(db.String(250),nullable=False,unique=True)
    password = db.Column(db.String(250),nullable=False)
    name = db.Column(db.String(250),nullable=False)
    parent_author = relationship('BlogPost',back_populates='child_author')
    parent_commenter = relationship('Comment',back_populates='child_commenter')

# Table for collecting posts information
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    author_id = db.Column(db.Integer,db.ForeignKey('user.id'))
    child_author = relationship('User', back_populates='parent_author')
    comments = relationship('Comment', back_populates='child_comments')

# Table for collecting comments information
class Comment(db.Model):
    __tablename__= "comments"
    id = db.Column(db.Integer,primary_key=True)
    comment_text = db.Column(db.Text,nullable=False)
    commenter_id = db.Column(db.Integer,db.ForeignKey('user.id'), nullable=False)
    child_commenter = relationship('User', back_populates='parent_commenter')
    post_id = db.Column(db.Integer,db.ForeignKey('blog_posts.id'), nullable=False)
    child_comments = relationship('BlogPost',back_populates='comments')

with app.app_context():
    db.create_all()

# config flask login
@loginmanager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# home page of website
@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts,current_user=current_user)

# Registration webpage
@app.route('/register',methods=['POST','GET'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if db.session.query(User).filter_by(email=form.email.data).first():
            flash('This email id is already registered. Please try login.')
            return redirect(url_for('login'))
        else:
            user = User(
                email = form.email.data,
                password = generate_password_hash(form.password.data,
                                                method='pbkdf2:sha256',
                                                salt_length=8),
                name = form.name.data                                
            )
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('get_all_posts'))
    return render_template("register.html",form=form,current_user=current_user)

# Login webpage
@app.route('/login',methods=['POST','GET'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        user = db.session.query(User).filter_by(email=email).first()
        if user:
            if check_password_hash(user.password,password):
                login_user(user)
                return redirect(url_for('get_all_posts'))
            else:
                flash('Incorrect password. Please try again.')
                return redirect(url_for('login'))
        else:
            flash('This email is not registered yet. Please try again.')
            return redirect(url_for('login'))
    return render_template("login.html",form=form,current_user=current_user)

# To logout the user
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# To present particular post in detail on post webpage
@app.route("/post/<int:post_id>",methods=['GET','POST'])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)
    comments = db.session.query(Comment).filter_by(post_id=requested_post.id).all()
    if form.validate_on_submit():
        comment = Comment(
            comment_text = form.comment.data,
            child_commenter = current_user,
            child_comments = requested_post,
            post_id = post_id
        )
        if current_user.is_authenticated:
            db.session.add(comment)
            db.session.commit()
            return redirect(url_for('show_post',post_id=post_id))
        else:
            flash('Please login first to comment.')
            return redirect(url_for('login'))
    return render_template("post.html",
                           form=form,
                           post=requested_post,
                           gravatar=gravatar,
                           comments=comments,
                           current_user=current_user)

# Webpage for information about blog
@app.route("/about")
def about():
    return render_template("about.html",current_user=current_user)

# Webpage for contact information
@app.route("/contact",methods=['GET','POST'])
def contact():
    return render_template("contact.html",current_user=current_user, email=email)

# For adding new post(admin only)
@app.route("/new-post",methods=['GET','POST'])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            child_author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form,current_user=current_user)

# for editing the existing posts on blog(admin only)
@app.route("/edit-post/<int:post_id>",methods=['GET','POST'])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form,current_user=current_user)

# for deleting any existing post (admin only)
@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))

if __name__ == "__main__":
    app.run(debug=True)
