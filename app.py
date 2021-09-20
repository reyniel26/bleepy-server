#================================================== Imports
#Flask
from flask import Flask, render_template

#Model for DB
from model import Model
#Bleepy module
from bleepy.bleepy import VideoFile, AudioFile, SpeechToText, ProfanityExtractor, ProfanityBlocker

#================================================== Objects
db = Model()

#================================================== Configs
app = Flask(__name__)
app.secret_key = 'bleepy_server' #Set the secret_key

#================================================== Routes 

#Index Page
@app.route('/')
def index():
    #create template folder
    #inside of template folder is the home.html
    return render_template('index.html')

#Signup Page
@app.route('/signup')
def signup():
    
    return render_template('signup.html')

#Signin Page
@app.route('/signin')
def signin():
    
    return render_template('signin.html')

#Pages that can only be access when logged in

#Settings Page
@app.route('/settings')
def settings():
    
    return render_template('settings.html')

#Dashboard Page
@app.route('/dashboard')
def dashboard():
    
    return render_template('dashboard.html')

#================================================== Run APP 
if __name__ == '__main__':
    app.run(debug=True)
