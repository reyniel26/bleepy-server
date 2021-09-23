#================================================== Imports
#Flask
from typing import Dict
from flask import Flask, config, render_template, flash, redirect, url_for, request, make_response
#For decorator
from functools import wraps 
#JWT
import jwt

#Model for DB
from model import Model
#Configs
from config import ProductionConfig, DevelopmentConfig
#Bleepy module
from bleepy.bleepy import VideoFile, AudioFile, SpeechToText, ProfanityExtractor, ProfanityBlocker

#================================================== Configs
app = Flask(__name__)
app.config.from_object(ProductionConfig if app.config["ENV"] == "production" else DevelopmentConfig)

#================================================== Objects
db = Model(
    app.config["DB_HOST"],
    app.config["DB_USER"],
    app.config["DB_PWD"],
    app.config["DB_NAME"]
    )

#================================================== Control Methods
def testConn(f):
    """
    Check if the db server is up | Decorator | from functools import wraps
    Note: Include this wrapper in every route that requires dbms
    Or Include this wrapper to all routes except for the error page
    """
    @wraps(f)
    def wrap(*args, **kwargs):
        if db.hasConnection():
            return f(*args, **kwargs)
        else:
            return redirect(url_for('error'))
    return wrap

def generateToken(**kwargs:str):
    """
    To generate token, specify the key and values
    Example: key_one="the value_one",key_two="value_two" 
    """
    token = jwt.encode(kwargs,app.secret_key,algorithm="HS256")
    return token

def getTokenValues(token:str):
    """
    Return Dict value of JWT or return None if the token is invalid
    """
    try:
        values = jwt.decode(token,app.secret_key,algorithms=["HS256"])
        return values
    except:
        return None

def authentication(f):
    """
    Check the authentication token of the user
    if the token not exist, its expires or credentials not set yet
    if the token not have values or has invalid secretkey, its invalid
    if the token not have authid, its invalid
    """
    @wraps(f)
    def wrap(*args, **kwargs):
        cookies = request.cookies
        token = cookies.get(app.config["AUTH_TOKEN_NAME"])
        if not token:
            #The token not exist
            flash("Invalid Authentication. Please try to login","warning")
            return redirect(url_for('signin'))
        
        tokenvalues = getTokenValues(token)

        if not tokenvalues:
            #The token values is None
            flash("Invalid Authentication","danger")
            return redirect(url_for('signin'))
        
        try:
            acc_id = tokenvalues["authid"]
        except:
            #The token doenst contain authid
            flash("Invalid Authentication","danger")
            return redirect(url_for('signin'))
        
        # Query the acc_id
        # if not exist return error

        return f(*args, **kwargs)
    return wrap

def viewData(**kwargs:str):
    """
    This method will pass constant data that will be use by the templates
    In rendering templates, always include this
    Example: render_template("index.html", viewdata = viewData())
    Another example: render_template("index.html", viewdata = viewData( somedata = "data"))
    """
    viewdata = {
        "auth_token":app.config["AUTH_TOKEN_NAME"]
    }
    viewdata.update(**kwargs)
    return viewdata
#================================================== Routes 

#Index Page
@app.route('/')
@testConn
def index():
    #create template folder
    #inside of template folder is the home.html
    return render_template('index.html', viewdata = viewData() )

#Error Page
@app.route('/error')
def error():
    if db.hasConnection():
        return redirect(url_for('index'))
    return render_template('error.html')

#Signup Page
@app.route('/signup', methods=["POST",'GET'])
@testConn
def signup():
    if request.method == "POST":
        flash('You are now logged in ', 'success')
        return redirect(url_for('dashboard'))
    return render_template('signup.html', viewdata = viewData() )

#Signin Page
@app.route('/signin', methods=["POST",'GET'])
@testConn
def signin():
    if request.method == "POST":
        email = request.form["email"]
        pwd = request.form["pwd"]
        remember = request.form.getlist("remember")
        #remember 30days or else remember for 5mins
        max_age = (60*60*24*30) if remember else (60*5)  

        if email != "sampleemail@gmail.com":
            flash('Wrong Email', 'danger')
            return render_template('signin.html', viewdata = viewData() )
        if pwd != "password":
            flash('Wrong Password', 'danger')
            return render_template('signin.html', viewdata = viewData() )

        #set response
        res = make_response(redirect(url_for('dashboard')))
        #set cookie token
        res.set_cookie(app.config["AUTH_TOKEN_NAME"], 
            value = generateToken(authid="1",validuntil=max_age),
            max_age = max_age
            )

        flash('You are now logged in ', 'success')
        return res
    return render_template('signin.html', viewdata = viewData())

#Pages and routes that can only be access when logged in
#@authentication

#Settings Page
@app.route('/settings')
@testConn
@authentication
def settings():
    
    return render_template('settings.html', viewdata = viewData())

#Dashboard Page
@app.route('/dashboard')
@testConn
@authentication
def dashboard():
    
    return render_template('dashboard.html', viewdata = viewData())

#Log out route
@app.route('/logout')
@testConn
@authentication
def logout():
    #set response
    res = make_response(redirect(url_for('signin')))
    #set cookie token | expires = 0 to delete cookie
    res.set_cookie(app.config["AUTH_TOKEN_NAME"],
        value = "",
        expires=0
        )
    flash('You are now logged out ', 'success')
    return res

#Bleep Video Page
@app.route('/bleepvideo')
@testConn
@authentication
def bleepvideo():
    
    return render_template('bleepvideo.html', viewdata = viewData())
#================================================== Run APP 
if __name__ == '__main__':
    app.run()
