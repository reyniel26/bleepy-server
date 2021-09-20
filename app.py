#================================================== Imports
#Flask
from flask import Flask, render_template, flash, redirect, url_for, request
#For decorator
from functools import wraps 

#Model for DB
from model import Model
#Bleepy module
from bleepy.bleepy import VideoFile, AudioFile, SpeechToText, ProfanityExtractor, ProfanityBlocker

#================================================== Configs
app = Flask(__name__)
app.secret_key = 'bleepy_server' #Set the secret_key

#================================================== Objects
db = Model()

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



#================================================== Routes 

#Index Page
@app.route('/')
@testConn
def index():
    #create template folder
    #inside of template folder is the home.html
    return render_template('index.html')

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
    return render_template('signup.html')

#Signin Page
@app.route('/signin', methods=["POST",'GET'])
@testConn
def signin():
    if request.method == "POST":
        flash('You are now logged in ', 'success')
        return redirect(url_for('dashboard'))
    return render_template('signin.html')

#Pages that can only be access when logged in

#Settings Page
@app.route('/settings')
@testConn
def settings():
    
    return render_template('settings.html')

#Dashboard Page
@app.route('/dashboard')
@testConn
def dashboard():
    
    return render_template('dashboard.html')

#================================================== Run APP 
if __name__ == '__main__':
    app.run(debug=True)
