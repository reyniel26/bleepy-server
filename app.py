#================================================== Imports
#Flask
from flask import Flask, render_template, flash, redirect, url_for, request, make_response, jsonify, send_file
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
        # reserror = make_response(redirect(url_for('signin')))
        # reserror = setAuth(redirect(url_for('signin')))
        reserror = setAuth(redirect(url_for('signin')))
        #set cookie token | expires = 0 to delete cookie
        # reserror.set_cookie(app.config["AUTH_TOKEN_NAME"],
        #     value = "",
        #     expires=0
        #     )

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

        max_age = tokenvalues.get("validuntil")
        if max_age == app.config["AUTH_MIN_AGE"]: #reset auth
            res = setAuth(f(*args, **kwargs),acc_id=acc_id,max_age=max_age)
            return res

        return f(*args, **kwargs)
    return wrap

def isAlreadyLoggedin(f):
    """
    If the user is already logged in go to dashboard
    Applicable to sign in and sign up page
    """
    @wraps(f)
    def wrap(*args, **kwargs):
        cookies = request.cookies
        token = cookies.get(app.config["AUTH_TOKEN_NAME"])
        if token:
            flash("You are already logged in","warning")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrap

def getIdViaAuth() -> str:
    cookies = request.cookies
    token = cookies.get(app.config["AUTH_TOKEN_NAME"])
    tokenvalues = getTokenValues(token)
    return tokenvalues["authid"]

def setAuth(response,**kwargs):
    """
    set acc_id and max_age
    example setAuth(render_template("home.html"),acc_id=acc_id,max_age=max_age)
    if the acc_id and max_age is not set auth will set no value with expire 0
    """
    #set response
    res = make_response(response)
    #set cookie token
    if kwargs.get("acc_id") and kwargs.get("max_age"):
        res.set_cookie(app.config["AUTH_TOKEN_NAME"], 
            value = generateToken(authid=kwargs.get("acc_id"),validuntil=kwargs.get("max_age")),
            max_age = kwargs.get("max_age")
            )
    else:
        res.set_cookie(app.config["AUTH_TOKEN_NAME"],
        value = "",
        expires=0
        )
    return res

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

def removeStaticDirectory(directory):
    "This remove static"
    filelocation = ""
    if "static" in directory:
        for i in directory.split("/")[1:]:
            filelocation+=i+"/"
        filelocation = filelocation[:-1]
    else:
        filelocation = directory
    return filelocation

def getFileNameFromDirectory(directory):
    directory = removeStaticDirectory(directory)
    return directory.split("/")[-1]

def saveBleepedVideo(vid_id,bleepsound_id,pfilename,pfilelocation,psavedirectory,profanities:list):
    bleepedvideoinfo = {
        "filename":"NaN",
        "filelocation":"NaN"
    }

    try:
        msg = db.insertBleepedVideo(vid_id,bleepsound_id,pfilename,pfilelocation,psavedirectory)
        print(msg)
        
        bleepedvideoinfo = db.selectBleepVideoByFileName(pfilename)
        pvid_id = bleepedvideoinfo.get("pvideo_id")
        vals = []

        for profanity in profanities:
            item = (profanity["word"],profanity["start"],profanity["end"],pvid_id)
            vals.append(item)
        
        msg = db.insertProfanities(vals)


        bleepedvideoinfo["profanitycount"] = db.countProfanityWordsByBleepedVideo(pvid_id).get("count")
        bleepedvideoinfo["uniqueprofanitycount"] = db.countUniqueProfanityWordsByBleepedVideo(pvid_id).get("count")
        mostfrequent = db.selectMostFrequentProfanityWordByVideo(pvid_id)
        bleepedvideoinfo["mostfrequentword"] = mostfrequent.get("word")
        bleepedvideoinfo["mostfrequentwordoccurence"]  = mostfrequent.get("occurence")
        bleepedvideoinfo["profanities"] = db.selectProfanitiesOfVideo(pvid_id) #list
        bleepedvideoinfo["uniqueprofanities"] = db.selectUniqueProfanityWordsByVideo(pvid_id) #list
        bleepedvideoinfo["top10profanities"] = db.selectTop10ProfanitiesByVideo(pvid_id)


    except Exception as e:
        print (e)
        bleepedvideoinfo["error"] = e
    
    return bleepedvideoinfo


    



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
@isAlreadyLoggedin
def signup():
    if request.method == "POST":

        fname = request.form.get("fname")
        lname = request.form.get("lname")
        email = sanitizeEmail(request.form.get("email"))
        pwd = request.form.get("pwd")
        confirmpwd = request.form.get("confirmpwd")
        isagree = request.form.getlist("agreetandc")



        flash('You are now logged in ', 'success')
        return redirect(url_for('dashboard'))
    return render_template('signup.html', viewdata = viewData() )

#Signin Page
@app.route('/signin', methods=["POST",'GET'])
@testConn
@isAlreadyLoggedin
def signin():
    if request.method == "POST":
        email = sanitizeEmail(request.form.get("email"))
        pwd = request.form.get("pwd")
        remember = request.form.getlist("remember")
        #remember 30days or else remember for 5mins
        max_age = app.config["AUTH_MAX_AGE"] if remember else app.config["AUTH_MIN_AGE"]

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

        # #set response
        # res = make_response(redirect(url_for('dashboard')))
        # #set cookie token
        # res.set_cookie(app.config["AUTH_TOKEN_NAME"], 
        #     value = generateToken(authid=acc_id,validuntil=max_age),
        #     max_age = max_age
        #     )
        res = setAuth(redirect(url_for('dashboard')),acc_id=acc_id,max_age=max_age)

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
    acc_id = getIdViaAuth() 

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
def logout():
    """
    Log out does not now need authentication, it just delete auth cache is exist
    """
    res = setAuth(redirect(url_for('signin')))
    flash('You are now logged out ', 'success')
    return res

#Bleep Video Page
@app.route('/bleepvideo')
@testConn
@authentication
def bleepvideo():
    acc_id = getIdViaAuth() 

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
        acc_id = getIdViaAuth() 


        vid_id = request.form.get("vid_id")

        videoinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)
        #videoinfo contains = filelocation, filename, see db
        
        filelocation = "/static/"+videoinfo.get("filelocation") if videoinfo  else ""
        
        
        return jsonify({"filelocation":filelocation})

    return jsonify('')

#Get BleepSound Link
@app.route('/getbleepsoundinfo', methods=["POST",'GET'])
@testConn
@authentication
def getbleepsoundinfo():
    if request.method == "POST":

        bleepsoundid= request.form.get("bleepsound_id")
        bleepsoundinfo = db.selectBleepSoundById(bleepsoundid)
    
        filelocation = "/static/"+bleepsoundinfo.get("filelocation") if bleepsoundinfo else ""
    
        
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
        acc_id = getIdViaAuth() 

        videoinfo = {
            "filename":"Error",
            "filelocation":"Error"
        }

        bleepsounds = db.selectBleepSounds()

        #If choose video
        if request.form.get("choosevideo"):

            vid_id = request.form.get("vid_id")
            videoinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)

            msg = str(videoinfo.get("filename"))+" has been choosen"
            return jsonify({ 'bleepstep1response': render_template('includes/bleepstep/_bleepstep2.html', viewdata = viewData(videoinfo=videoinfo, bleepsounds=bleepsounds)),
                             'responsemsg': render_template('includes/_messages.html', msg=msg)
                        })

        elif request.files.get("uploadFile"):
            file = request.files.get("uploadFile")
            # print(request.cookies.get('filesize'))

            # if not allowedFileSize(request.cookies.get('filesize')):
            if not allowedFileSize(request.form.get('uploadfilesize')):
                errormsg = "File too large. Maximum File size allowed is "+str(app.config["MAX_FILESIZE_GB"])+" gb"
                return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })

            video = VideoFile()
            
            if not video.isAllowedExt(video.getExtension(file.filename)):
                errormsg = "File type is not allowed. Allowed file extension are: "+str(video.getAllowedExts())
                return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })
            
            #Save Video
            filename = file.filename
            uniquefilename = str(uuid.uuid4()) +"."+video.getExtension(file.filename)

            videoinfo = saveVideo(file,filename,uniquefilename,acc_id)

            msg = "File Uploaded Successfully"
            return jsonify({ 'bleepstep1response': render_template('includes/bleepstep/_bleepstep2.html', viewdata = viewData(videoinfo=videoinfo,bleepsounds=bleepsounds)) ,
                            'responsemsg': render_template('includes/_messages.html', msg=msg)
                        })

    return jsonify('')

#BleepStep2
#RunBleepy 
@app.route('/bleepstep2', methods=["POST",'GET'])
@testConn
@authentication
def bleepstep2():
    if request.method == "POST":
        acc_id = getIdViaAuth()

        vid_id = request.form.get("vid_id")
        bleepsound_id = request.form.get("bleepsound_id")

        if not (vid_id and bleepsound_id):
            errormsg = "Invalid request! Video and Bleep Sound has no value"
            return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })
        
        videoinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)
        bleepsoundinfo = db.selectBleepSoundById(bleepsound_id)

        video_filelocation = videoinfo.get("filelocation")
        bleep_longversion = bleepsoundinfo.get("longversion") #This file will be use as bleep sound

        if not (video_filelocation and bleep_longversion):
            errormsg = "Invalid request! There is no data for video and bleep sound"
            return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })
        
        video = VideoFile()
        audio = AudioFile()

        if not ( video.isFileAllowed("static/"+video_filelocation) and audio.isFileAllowed("static/"+bleep_longversion) ):
            errormsg = "Invalid request! Video or Bleep Sound doesnt exist"
            return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })
        
        video.setFile("static/"+video_filelocation)
        audio.setFile("static/"+bleep_longversion)
        

        try:
            
            stt = SpeechToText("stt-language-models/model-en")
            extractor = ProfanityExtractor()
            blocker = ProfanityBlocker()
            blocker.setClipsDirectory("static/media/Trash/Videos")
            blocker.setSaveDirectory("static/media/Storage/Videos/Processed")
            
            stt.run(video)

            extractor.setProfanities([]) #Reset Profanities
            extractor.run(stt.getResults())
            profanities = extractor.getProfanities()
            

            if len(profanities) > 0:
                blocker.run(video,audio,profanities)
                block_directory = blocker.getFileLocation()
                block_filelocation = removeStaticDirectory(block_directory)
                block_filename = getFileNameFromDirectory(block_filelocation)
                bleepedvideoinfo = saveBleepedVideo(vid_id,bleepsound_id,block_filename,block_filelocation,block_directory,profanities)
                #Save to db
            else:
                msg = "This video is already profanity free. No profanities detected"
                print(msg)
                return jsonify({ 'bleepstep2response': render_template('includes/bleepstep/_bleepstep3.html', viewdata = viewData() ) ,
                        'responsemsg': render_template('includes/_messages.html', msg=msg)
                    })

        except Exception as e:
            errormsg = e
            return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })
        
        msg = "The video is now profanity free"
        return jsonify({ 'bleepstep2response': render_template('includes/bleepstep/_bleepstep3.html', viewdata = viewData(bleepedvideoinfo=bleepedvideoinfo)) ,
                        'responsemsg': render_template('includes/_messages.html', msg=msg)
                    })

    return jsonify('')


#BleepStep3
#RunBleepy 
@app.route('/bleepstep3/<path>', methods=["POST",'GET'])
@testConn
@authentication
def bleepstep3(path):
    
    try:
        acc_id = getIdViaAuth()
        bleepvideo_id = path
        bleepedvideoinfo = db.selectBleepedVideosByAccountAndPvid(acc_id,bleepvideo_id)
        file_path = "static/"+bleepedvideoinfo.get("pfilelocation")
        filename = "bleepedversion"+bleepedvideoinfo.get("filename")
        attachment = True
        print(file_path)

        return send_file(file_path,as_attachment=attachment,attachment_filename=filename)
    
    except Exception as e:
        errormsg = "Request has been denied"
        return render_template('includes/_messages.html', error=errormsg)
    
    

#================================================== Run APP 
if __name__ == '__main__':
    app.run()
