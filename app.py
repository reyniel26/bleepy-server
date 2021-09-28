#================================================== Imports
#Flask
from flask import Flask, render_template, flash, redirect, url_for, request, make_response, jsonify
#For decorator
from functools import wraps 
#JWT
import jwt
#Passlib
from passlib.hash import sha256_crypt
#Date time
import datetime
#OS
import os
#Uuid = for unique random id
import uuid

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
video = VideoFile()

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

        #making sure there is no cookie left
        reserror = make_response(redirect(url_for('signin')))
        #set cookie token | expires = 0 to delete cookie
        reserror.set_cookie(app.config["AUTH_TOKEN_NAME"],
            value = "",
            expires=0
            )

        if not token:
            #The token not exist
            flash("Invalid Authentication. Please try to login","warning")
            return reserror
        
        tokenvalues = getTokenValues(token)

        if not tokenvalues:
            #The token values is None
            flash("Invalid Authentication","danger")
            return reserror
        
        try:
            acc_id = tokenvalues.get("authid")
        except:
            #The token doenst contain authid
            flash("Invalid Authentication","danger")
            return reserror
        
        # Query the acc_id
        data = db.selectAccountViaId(acc_id)
        if data == None:
            flash("Invalid Authentication. User not found: "+data,"danger")
            return reserror
        try:
            id = data["account_id"]
        except Exception as e:
            flash("Error: "+data,"danger")
            return reserror
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

def sanitizeEmail(email:str):
    """
    Sanitize email by removing invalid characters
    """
    invalids = [" ","\"","\\", "/", "<", ">","|","\t",":"]
    for x in invalids:
        email = email.strip(x)
    return email

def allowedFileSize(filesize) ->bool:
    return int(filesize) <= app.config['MAX_VIDEO_FILESIZE']

def saveVideo(file,filename,uniquefilename,acc_id):
    fileinfo = {
        "filename":"NaN",
        "filelocation":"NaN"
    }

    parent_folder = "static/"+app.config['VIDEO_UPLOADS']
    folder = str(acc_id)
    savefolder = app.config['VIDEO_UPLOADS']+"/"+folder

    #Try to create folder if not exist
    try:
        path = os.path.join(parent_folder, folder)
        os.mkdir(path)
    except(FileExistsError):
        pass

    #SaveToDirectories
    file.save(os.path.join("static/"+savefolder, uniquefilename))

    #SaveToDB
    filelocation = savefolder+"/"+uniquefilename
    savedirectory = "static/"+filelocation
    msg = db.insertVideo(filename,uniquefilename,filelocation,savedirectory)
    print(msg)
    vid_id = db.selectVideoByUniqueFilename(uniquefilename).get("video_id")
    msg = db.insertUploadedBy(vid_id,acc_id)
    print(msg)

    fileinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)

    return fileinfo
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
        email = sanitizeEmail(request.form.get("email"))
        pwd = request.form.get("pwd")
        remember = request.form.getlist("remember")
        #remember 30days or else remember for 5mins
        max_age = (60*60*24*30) if remember else (60*5)

        #Validation
        if email == "" or pwd == "":
            flash('Invalid! Email or Password should not be empty', 'danger')
            return redirect(url_for('signin'))

        #DB Model
        data = db.selectAccountViaEmail(email)

        if not data:
            flash('Wrong Email', 'danger')
            return redirect(url_for('signin'))
        
        
        acc_pwd = data.get("pwd")
        acc_id = data.get("account_id")

        if acc_pwd == None or acc_id == None:
            flash('Internal Error', 'danger')
            return redirect(url_for('signin'))

        pwd_candidate = pwd
        
        if not sha256_crypt.verify(pwd_candidate, acc_pwd):
            flash('Wrong Password', 'danger')
            return redirect(url_for('signin'))

        #set response
        res = make_response(redirect(url_for('dashboard')))
        #set cookie token
        res.set_cookie(app.config["AUTH_TOKEN_NAME"], 
            value = generateToken(authid=acc_id,validuntil=max_age),
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
    cookies = request.cookies
    token = cookies.get(app.config["AUTH_TOKEN_NAME"])
    tokenvalues = getTokenValues(token)
    acc_id = tokenvalues["authid"]

    data = db.selectAccountViaId(acc_id)
    fullname = str(data.get("fname")+" "+data.get("lname")).title()
    now = datetime.datetime.now()

    user_data = {
        "fullname":fullname,
        "videoscount":db.countVideosUploadedByAcc(acc_id).get("count"),
        "bleepedvideoscount":db.countBleepVideosUploadedByAcc(acc_id).get("count"),
        "mostfrequentprofanities":db.selectUniqueProfanityWordsByAccount(acc_id),
        "bleepedvideos":db.selectBleepedVideosByAccount(acc_id),
        "datetoday":now.strftime("%B %d %Y")+", "+now.strftime("%A")
    }

    feeds = db.selectFeeds(acc_id)
    latestbleep_data = db.selectLatestBleepSummaryData(acc_id)
    
    return render_template('dashboard.html', viewdata = viewData( user_data=user_data,feeds=feeds, latestbleep_data=latestbleep_data ))

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
    cookies = request.cookies
    token = cookies.get(app.config["AUTH_TOKEN_NAME"])
    tokenvalues = getTokenValues(token)
    acc_id = tokenvalues["authid"]

    videos = db.selectVideosUploadedByAccount(acc_id)
    
    return render_template('bleepvideo.html', viewdata = viewData(videos=videos))

#Routes that returns JSONs
#@authentication

#Get Video Link
@app.route('/getvideoinfo', methods=["POST",'GET'])
@testConn
@authentication
def getvideoinfo():
    if request.method == "POST":
        cookies = request.cookies
        token = cookies.get(app.config["AUTH_TOKEN_NAME"])
        tokenvalues = getTokenValues(token)
        acc_id = tokenvalues["authid"]


        vid_id = request.form.get("vid_id")

        videoinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)
        #videoinfo contains = filelocation, filename, see db
        
        filelocation = "/static/"+videoinfo.get("filelocation") if videoinfo  else ""
        
        
        return jsonify({"filelocation":filelocation})

    return jsonify('')

#Routes for Bleep Steps
#@authentication

#BleepStep1 
@app.route('/bleepstep1', methods=["POST",'GET'])
@testConn
@authentication
def bleepstep1():
    if request.method == "POST":
        cookies = request.cookies
        token = cookies.get(app.config["AUTH_TOKEN_NAME"])
        tokenvalues = getTokenValues(token)
        acc_id = tokenvalues["authid"]

        videoinfo = {
            "filename":"Error",
            "filelocation":"Error"
        }

        #If choose video
        if request.form.get("choosevideo"):

            vid_id = request.form.get("vid_id")
            videoinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)

            msg = str(videoinfo.get("filename"))+" has been choosen"
            return jsonify({ 'bleepstep1response': render_template('includes/bleepstep/_bleepstep2.html', viewdata = viewData(videoinfo=videoinfo)),
                             'responsemsg': render_template('includes/_messages.html', msg=msg)
                        })

        elif request.files.get("uploadFile"):
            file = request.files.get("uploadFile")
            print(request.cookies.get('filesize'))

            if not allowedFileSize(request.cookies.get('filesize')):
                errormsg = "File too large. Maximum File size allowed is "+str(app.config["MAX_FILESIZE_GB"])+" gb"
                return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })

            #Save Video
            if not video.isAllowedExt(video.getExtension(file.filename)):
                errormsg = "File type is not allowed"
                return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })

            filename = file.filename
            uniquefilename = str(uuid.uuid4()) +"."+video.getExtension(file.filename)

            videoinfo = saveVideo(file,filename,uniquefilename,acc_id)

            msg = "File Uploaded Successfully"
            return jsonify({ 'bleepstep1response': render_template('includes/bleepstep/_bleepstep2.html', viewdata = viewData(videoinfo=videoinfo)) ,
                            'responsemsg': render_template('includes/_messages.html', msg=msg)
                        })

    return jsonify('')

#================================================== Run APP 
if __name__ == '__main__':
    app.run()
