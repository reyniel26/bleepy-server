#================================================== Imports
#Flask
from flask import Flask, render_template, flash, redirect, url_for, request, make_response, jsonify, send_file,abort
#For decorator
from functools import wraps 
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
#Controls
from control import TokenControls, BasicControls
#Configs
from config import ProductionConfig, DevelopmentConfig
#Bleepy module
from bleepy.bleepy import VideoFile, AudioFile, MediaFile, SpeechToText, ProfanityExtractor, ProfanityBlocker

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
tknctrl = TokenControls(app.secret_key)
bsctrl = BasicControls()


#================================================== App Control Methods
def getIdViaAuth():
    try:
        cookies = request.cookies
        token = cookies.get(app.config["AUTH_TOKEN_NAME"])
        tokenvalues = tknctrl.getTokenValues(token)
        return str(tokenvalues["authid"])
    except:
        return None

def getEmailViaAuth():
    try:
        return db.selectAccountViaId(getIdViaAuth()).get("email")
    except:
        return None

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
            value = tknctrl.generateToken(authid=kwargs.get("acc_id"),validuntil=kwargs.get("max_age")),
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

    To add active class to cardnav, use nameOfRoute=True
    Example: dashboard=True
    """
    viewdata = {
        "auth_token":app.config["AUTH_TOKEN_NAME"]
    }
    #If the user is logged in
    if getIdViaAuth():
        acc_id = getIdViaAuth()
        data = db.selectAccountViaId(acc_id)
        if data:
            fullname = str(data.get("fname")+" "+data.get("lname")).title()
            photo = data.get("photo")
            role_id = data.get("role_id")

            #User widget
            viewdata["uw_fullname"] = fullname
            viewdata["uw_photo"] = photo
            viewdata["uw_videoscount"] = db.countVideosUploadedByAcc(acc_id).get("count")
            viewdata["uw_bleepedvideoscount"] = db.countBleepVideosUploadedByAcc(acc_id).get("count")
            viewdata["uw_role"] = db.selectAccRole(acc_id).get("name")

            #Navigation
            viewdata["navigations"] = db.selectNavOfRole(role_id)
        
        

    viewdata.update(**kwargs)
    return viewdata

def allowedVideoFileSize(filesize) ->bool:
    return float(filesize) <= app.config['MAX_VIDEO_FILESIZE']

def allowedPhotoFileSize(filesize) ->bool:
    return float(filesize) <= bsctrl.bytesToMb(app.config['MAX_PHOTO_FILESIZE'])

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

#================================================== Decorators
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
            abort(500)
    return wrap

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
        
        tokenvalues = tknctrl.getTokenValues(token)

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

def isAdmin(f):
    """
    Check if the role of the user is admin
    """
    @wraps(f)
    def wrap(*args, **kwargs):
        acc_id = getIdViaAuth() 
        acc_role = db.selectAccRole(acc_id).get("name")
        if acc_role != app.config["ROLE_ADMIN"]:
            flash("You are not authorize to access this page","danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrap

def isEditor(f):
    """
    Check if the role of the user is editor or admin
    """
    @wraps(f)
    def wrap(*args, **kwargs):
        acc_id = getIdViaAuth() 
        acc_role = db.selectAccRole(acc_id).get("name")
        if not (acc_role == app.config["ROLE_ADMIN"] or acc_role == app.config["ROLE_EDITOR"]):
            flash("You are not authorize to access this page","danger")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrap

#================================================== Error handlers
@app.errorhandler(403)
def forbidden_error(error):
    return render_template('error.html',error_msg = error, error_code = 403,error_status = "warning"), 403

@app.errorhandler(404)
def not_found_error(error):
    return render_template('error.html',error_msg = error, error_code = 404,error_status = "danger"), 404

@app.errorhandler(405)
def method_not_allowed_error(error):
    return render_template('error.html',error_msg = error, error_code = 405,error_status = "danger"), 405

@app.errorhandler(410)
def gone_error(error):
    return render_template('error.html',error_msg = error, error_code = 410,error_status = "warning"), 410

@app.errorhandler(500)
def internal_server_error(error):
    return render_template('error.html',error_msg = error, error_code = 500,error_status = "danger"), 500


#================================================== Routes 

#Index Page
@app.route('/' )
@testConn
def index():
    #create template folder
    #inside of template folder is the home.html
    return render_template('index.html', viewdata = viewData() )

#Bleep Sounds
@app.route('/bleepsoundlist')
@testConn
def bleepsoundlist():
    
    bleepsounds = db.selectBleepSounds()
    latest_bleepsound = db.selectLatestBleepSound()

    return render_template('bleepsoundlist.html', viewdata = viewData(bleepsoundlist=True, bleepsounds=bleepsounds, latest_bleepsound =latest_bleepsound ) )


#Signup Page
@app.route('/signup', methods=["POST",'GET'])
@testConn
@isAlreadyLoggedin
def signup():
    if request.method == "POST":

        fname = request.form.get("fname").strip()
        lname = request.form.get("lname").strip()
        email = bsctrl.sanitizeEmail(request.form.get("email"))
        pwd = request.form.get("pwd")
        confirmpwd = request.form.get("confirmpwd")
        isagree = request.form.getlist("agreetandc")

        #Validations
        if fname == "" or lname == "" or email == "" or pwd == "" or confirmpwd == "":
            flash('Please fill up all fields', 'danger')
            return redirect(url_for('signup'))
        
        if not isagree:
            flash('Please check the Terms and Conditions', 'danger')
            return redirect(url_for('signup'))
        
        if pwd != confirmpwd:
            flash('Password and Confirm password not match', 'danger')
            return redirect(url_for('signup'))
        
        if not (fname.replace(" ", "").isalpha() and lname.replace(" ", "").isalpha()):
            flash('Invalid First Name of Last Name', 'danger')
            return redirect(url_for('signup'))
        
        checkemail = db.selectAccountViaEmail(email)
        if checkemail:
            if checkemail.get("email"):
                flash('Email is already taken or used by other user', 'danger')
                return redirect(url_for('signup'))
            else:
                flash('Error: '+checkemail.get("error"), 'danger')
                return redirect(url_for('signup'))
        
        #hash password
        hash_pwd = sha256_crypt.encrypt(str(pwd))
        
        #Save to db if valid
        msg = db.insertUser(email,fname,lname,hash_pwd)
        print(msg)

        #validate to db if the account save
        account = db.selectAccountViaEmail(email)

        if not account:
            flash('Sign up failed due to internal error. Account not save', 'danger')
            return redirect(url_for('signup'))
        
        acc_id = account.get("account_id")
        
        if not acc_id:
            flash('Sign up failed due to internal error', 'danger')
            return redirect(url_for('signup'))
        
        #set cookie
        max_age = app.config["AUTH_MIN_AGE"]
        res = setAuth(redirect(url_for('dashboard')),acc_id=acc_id,max_age=max_age)

        flash('You are now logged in ', 'success')
        return res
    return render_template('signup.html', viewdata = viewData() )

#Signin Page
@app.route('/signin', methods=["POST",'GET'])
@testConn
@isAlreadyLoggedin
def signin():
    if request.method == "POST":
        email = bsctrl.sanitizeEmail(request.form.get("email"))
        pwd = request.form.get("pwd")
        remember = request.form.getlist("remember")
        #remember 30days or else remember for 5mins
        max_age = app.config["AUTH_MAX_AGE"] if remember else app.config["AUTH_MIN_AGE"]

        #Validation
        if email == "" or pwd == "":
            flash('Invalid! Email or Password should not be empty', 'danger')
            return redirect(url_for('signin'))

        #DB Model
        account = db.selectAccountViaEmail(email)

        if not account:
            flash('Wrong Email', 'danger')
            return redirect(url_for('signin'))
        
        
        acc_pwd = account.get("pwd")
        acc_id = account.get("account_id")

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

#Log out route
@app.route('/logout')
@testConn
def logout():
    """
    Log out does not need authentication, it just delete auth cache is exist
    """
    res = setAuth(redirect(url_for('signin')))
    flash('You are now logged out ', 'success')
    return res

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
    now = datetime.datetime.now()
    acc_role = db.selectAccRole(acc_id).get("name")

    user_data = {
        "mostfrequentprofanities":db.selectUniqueProfanityWordsByAccount(acc_id),
        "bleepedvideos":db.selectBleepedVideosByAccount(acc_id),
        "datetoday":now.strftime("%B %d %Y")+", "+now.strftime("%A")
    }

    feeds = db.selectFeeds(acc_id) if acc_role != app.config["ROLE_ADMIN"] else db.selectAdminFeeds()
    latestbleep_data = db.selectLatestBleepSummaryData(acc_id)

    admin_data = {}
    editor_data = {}

    if acc_role == app.config["ROLE_EDITOR"] or acc_role == app.config["ROLE_ADMIN"]:
        #Set the data that the editor and admin can have
        editor_data = {
            "role":"editor"
        }
        

    if acc_role == app.config["ROLE_ADMIN"]:
        #Set the data that the editor and admin can have
        admin_data = {
            "accountCounts":db.selectAccountCountsByRole(),
            "latestusers":db.selectLatestUsers(),
            "trendfeeds":db.selectTrendFeed()
        }
        
    
    
    return render_template('dashboard.html', viewdata = viewData( dashboard=True, 
                            user_data=user_data, admin_data=admin_data, editor_data=editor_data,
                            feeds=feeds, latestbleep_data=latestbleep_data ))

#Profile route
@app.route('/profile')
@testConn
@authentication
def profile():
    acc_id = getIdViaAuth()
    data = db.selectAccountViaId(acc_id)

    user_data = {
        "fname":data.get("fname"),
        "lname":data.get("lname"),
        "email":data.get("email"),
        "photo":data.get("photo"),
    }
    max_photo_filesize = bsctrl.bytesToMb(app.config["MAX_PHOTO_FILESIZE"])
    
    return render_template('profile.html', viewdata = viewData(profile=True, user_data = user_data,max_photo_filesize=max_photo_filesize))

#Video List route
@app.route('/videolist')
@testConn
@authentication
def videolist():
    acc_id = getIdViaAuth()

    videos = db.selectVideosUploadedByAccount(acc_id)
    latest_video = db.selectLatestUploadedVideo(acc_id)
    
    return render_template('videolist.html', viewdata = viewData(videolist=True,videos=videos,latest_video=latest_video))

#Bleep Video List route
@app.route('/bleepvideolist')
@testConn
@authentication
def bleepvideolist():
    acc_id = getIdViaAuth()

    bleepedvideos = db.selectBleepedVideosByAccount(acc_id)
    latestbleep_data = db.selectLatestBleepSummaryData(acc_id)
    
    return render_template('bleepvideolist.html', viewdata = viewData(bleepvideolist=True,bleepedvideos=bleepedvideos,latestbleep_data=latestbleep_data))

#Bleep Video Info route
@app.route('/bleepvideoinfo/<path>',methods=["POST",'GET'])
@testConn
@authentication
def bleepvideoinfo(path):
    acc_id = getIdViaAuth()
    bleepinfo_data = {}
    if path:
        bleepvideo_id = path
        bleepinfo_data = db.selectBleepedVideoFullInfo(acc_id,bleepvideo_id)

    return render_template('bleepvideoinfo.html', viewdata = viewData(bleepvideolist=True,bleepinfo_data=bleepinfo_data))

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

#Get BleepSound Link
#This doesnt need authentication
@app.route('/getbleepsoundinfo', methods=["POST",'GET'])
@testConn
def getbleepsoundinfo():
    if request.method == "POST":

        bleepsoundid= request.form.get("bleepsound_id")
        bleepsoundinfo = db.selectBleepSoundById(bleepsoundid)
    
        filelocation = "/static/"+bleepsoundinfo.get("filelocation") if bleepsoundinfo else ""
        filename = bleepsoundinfo.get("filename")
        
        return jsonify({
            "filelocation":filelocation,
            "filename":filename
        })

    return jsonify('')


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
        filename = videoinfo.get("filename")
        upload_time= videoinfo.get("upload_time")

        return jsonify({
            "filelocation":filelocation,
            "filename":filename,
            "upload_time":upload_time
        })

    return jsonify('')

#Download bleep video
@app.route('/downloadbleeped/<path>', methods=["POST",'GET'])
@testConn
@authentication
def downloadbleeped(path):
    try:
        acc_id = getIdViaAuth()
        bleepvideo_id = path
        bleepedvideoinfo = db.selectBleepedVideosByAccountAndPvid(acc_id,bleepvideo_id)
        file_path = "static/"+bleepedvideoinfo.get("pfilelocation")
        filename = "bleepedversion"+bleepedvideoinfo.get("filename")
        return send_file(file_path,as_attachment=True,attachment_filename=filename)
    except Exception as e:
        errormsg = "Request has been denied"
        return render_template('includes/_messages.html', error=errormsg)
        
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

            # if not allowedVideoFileSize(request.cookies.get('filesize')):
            if not allowedVideoFileSize(request.form.get('uploadfilesize')):
                errormsg = "File too large. Maximum File size allowed is "+str(bsctrl.bytesToGb(app.config["MAX_VIDEO_FILESIZE"]))+" gb"
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
                block_filelocation = bsctrl.removeStaticDirectory(block_directory)
                block_filename = bsctrl.getFileNameFromDirectory(block_filelocation)
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
    return redirect(url_for('downloadbleeped',path=path))

#==============Update Profile   
#Update FNAME
@app.route('/updatefname', methods=["POST",'GET'])
@testConn
@authentication
def updatefname():
    if request.method == "POST":

        fname = request.form.get("fname").strip()
        acc_id = getIdViaAuth()
        acc = db.selectAccountViaId(acc_id)
        
        if acc:
            email = acc.get("email")
            oldfname = acc.get("fname")

            if fname == oldfname:
                flash('Nothing change', 'success')
            elif fname == "":
                flash('Invalid, Empty fields!', 'warning')
            else:
                db.updateAccFname(email,fname)
                flash('Success! First name has been updated', 'success')

            return redirect(url_for('profile')) 

    flash('Invalid request!', 'warning')
    return redirect(url_for('profile')) 

#Update LNAME
@app.route('/updatelname', methods=["POST",'GET'])
@testConn
@authentication
def updatelname():
    if request.method == "POST":

        lname = request.form.get("lname").strip()
        acc_id = getIdViaAuth()
        acc = db.selectAccountViaId(acc_id)
        
        if acc:
            email = acc.get("email")
            oldlname = acc.get("lname")

            if lname == oldlname:
                flash('Nothing change', 'success')
            elif lname == "":
                flash('Invalid, Empty fields!', 'warning')
            else:
                db.updateAccLname(email,lname)
                flash('Success! Last Name has been updated!', 'success')
                
            return redirect(url_for('profile')) 

    flash('Invalid request!', 'warning')
    return redirect(url_for('profile'))

#Update Email
@app.route('/updateemail', methods=["POST",'GET'])
@testConn
@authentication
def updateemail():
    if request.method == "POST":

        newemail = bsctrl.sanitizeEmail(request.form.get("email"))
        pwd = request.form.get("pwd")

        acc_id = getIdViaAuth()
        acc = db.selectAccountViaId(acc_id)
        
        if acc:
            oldemail = acc.get("email")
            acc_pwd = acc.get("pwd")

            if newemail == oldemail:
                flash('Nothing change', 'success')
            elif newemail == "" or pwd == "":
                flash('Invalid, Empty fields!', 'warning')
            else:
                checkemail = db.selectAccountViaEmail(newemail)
                if checkemail:
                    if checkemail.get("email"):
                        flash('Email is already taken or used by other user', 'danger')
                    else:
                        flash('Error: '+checkemail.get("error"), 'danger')
                else:
                    pwd_candidate = pwd
        
                    if not sha256_crypt.verify(pwd_candidate, acc_pwd):
                        flash('Wrong Password', 'danger')
                    else:
                        db.updateAccEmail(oldemail,newemail)
                        flash('Success! Email has been updated!', 'success')
                
            return redirect(url_for('profile')) 

    flash('Invalid request!', 'warning')
    return redirect(url_for('profile'))

#Update LNAME
@app.route('/updatepwd', methods=["POST",'GET'])
@testConn
@authentication
def updatepwd():
    if request.method == "POST":

        oldpwd = request.form.get("oldpwd")
        newpwd = request.form.get("newpwd")
        confirmpwd = request.form.get("confirmpwd")

        acc_id = getIdViaAuth()
        acc = db.selectAccountViaId(acc_id)
        
        if acc:
            email = acc.get("email")
            acc_pwd = acc.get("pwd")

            if oldpwd == newpwd:
                flash('Nothing change!', 'success')
            elif oldpwd == "" or newpwd == "" or confirmpwd == "":
                flash('Invalid, Empty fields!', 'warning')
            elif newpwd != confirmpwd:
                flash('Password not confirm', 'warning')
            elif not sha256_crypt.verify(oldpwd, acc_pwd):
                flash('Wrong Password', 'danger')
            else:
                #hash pass first
                hash_pwd = sha256_crypt.encrypt(str(newpwd))

                db.updateAccPwd(email,hash_pwd)
                flash('Success! Password has been updated!', 'success')
                
            return redirect(url_for('profile')) 

    flash('Invalid request!', 'warning')
    return redirect(url_for('profile'))

#Update Photo
@app.route('/updatephoto', methods=["POST",'GET'])
@testConn
@authentication
def updatephoto():
    if request.method == "POST":

        # fname = request.form.get("fname").strip()
        file = request.files.get("updatephoto")
        filesize = request.form.get('uploadfilesize')
        media = MediaFile()
        media.setAllowedExts(["png","jpg","jpeg"])

        acc_id = getIdViaAuth()
        acc = db.selectAccountViaId(acc_id)

        
        if acc:
            email = acc.get("email")
            oldphoto = acc.get("photo")


            if not allowedPhotoFileSize(filesize):
                flash("File too large. Maximum File size allowed is "+str(bsctrl.bytesToMb(app.config["MAX_PHOTO_FILESIZE"]))+" mb", 'warning')
            elif not media.isAllowedExt(media.getExtension(file.filename)):
                flash('File type is not allowed. Allowed file extension are: '+str(media.getAllowedExts()),'danger')
            else:
                if oldphoto != app.config["PHOTO_DEFAULT_USER"]:
                    if os.path.exists("static/"+oldphoto):
                        os.remove("static/"+oldphoto)

                parent_folder = "static/"+app.config['PHOTO_UPLOADS']
                folder = str(acc_id)
                savefolder = app.config['PHOTO_UPLOADS']+"/"+folder

                #Try to create folder if not exist
                uniquefilename = str(uuid.uuid4()) +"."+media.getExtension(file.filename)
                try:
                    path = os.path.join(parent_folder, folder)
                    os.mkdir(path)
                except(FileExistsError):
                    pass

                #SaveToDirectories
                file.save(os.path.join("static/"+savefolder, uniquefilename))

                #Save to db
                db.updateAccPhoto(email,savefolder+"/"+uniquefilename)
                flash('Success! Profile photo has been updated', 'success')

            return redirect(url_for('profile')) 

    flash('Invalid request!', 'warning')
    return redirect(url_for('profile')) 

#==============Admin Pages
# Manage Account 
@app.route('/manageaccount')
@testConn
@authentication
@isAdmin
def manageaccount():
    accounts = db.selectAccountsAll()
    roles = db.selectRoles()
    defaultpwd = app.config["DEFAULT_ACC_PWD"]
    return render_template('admin/manageaccount.html', viewdata = viewData(accounts=accounts,roles=roles, defaultpwd=defaultpwd))

#View Account
@app.route('/viewaccount',methods=["POST",'GET'])
@testConn
@authentication
@isAdmin
def viewaccount():
    data = {}
    if request.method == "POST":
        if request.form.get("acc_id"):
            data = db.selectAccountViaId(request.form.get("acc_id"))
    
    account = {
        'fname':str(data.get('fname')).title(),
        'lname':str(data.get('lname')).title(),
        'photo':url_for('static',filename = data.get('photo')),
        'email':data.get('email'),
        'role':str(data.get('role')).title(),
        'role_id':data.get('role_id')
    }
    return jsonify(account)

# Add Account 
@app.route('/addaccount',methods=["POST",'GET'])
@testConn
@authentication
@isAdmin
def addaccount():
    if request.method == "POST":
        fname = request.form.get("addfname").strip()
        lname = request.form.get("addlname").strip()
        email = bsctrl.sanitizeEmail(request.form.get("addemail"))
        pwd = request.form.get("addpwd")
        role_id = request.form.get("addrole")

        #Validations
        if fname == "" or lname == "" or email == "" or pwd == "" or role_id == "":
            flash('Please fill up all fields', 'danger')
            return redirect(url_for('manageaccount'))
        
        if not (fname.replace(" ", "").isalpha() and lname.replace(" ", "").isalpha()):
            flash('Invalid First Name of Last Name', 'danger')
            return redirect(url_for('manageaccount'))
        
        checkemail = db.selectAccountViaEmail(email)
        if checkemail:
            if checkemail.get("email"):
                flash('Email is already taken or used by other user', 'danger')
                return redirect(url_for('manageaccount'))
            else:
                flash('Error: '+checkemail.get("error"), 'danger')
                return redirect(url_for('manageaccount'))
        
        #hash password
        hash_pwd = sha256_crypt.encrypt(str(pwd))
        
        #Save to db if valid
        msg = db.insertAccount(email,fname,lname,hash_pwd,role_id)
        print(msg)

        #validate to db if the account save
        account = db.selectAccountViaEmail(email)

        if not account:
            flash('Sign up failed due to internal error. Account not save. Error:'+str(msg), 'danger')
            return redirect(url_for('manageaccount'))
        
        fullname = (fname+" "+lname).title()
        flash('Success! '+fullname+" has been added. "+str(msg) , 'success')
    else:
        flash('Invalid request!', 'warning')
    return redirect(url_for('manageaccount'))

# Edit Account 
@app.route('/editaccount',methods=["POST",'GET'])
@testConn
@authentication
@isAdmin
def editaccount():
    if request.method == "POST":
        acc_id = request.form.get("editaccid")
        fname = request.form.get("editfname").strip()
        lname = request.form.get("editlname").strip()
        email = bsctrl.sanitizeEmail(request.form.get("editemail"))
        role_id = request.form.get("editrole")

        acc = db.selectAccountViaId(acc_id)

        if not acc:
            flash('Account doenst exist!', 'danger')
            return redirect(url_for('manageaccount'))
        
        acc_fname = acc.get("fname")
        acc_lname = acc.get("lname")
        acc_email = acc.get("email")
        acc_role_id = acc.get("role_id")

        #Email
        if email != acc_email:
            if db.selectAccountViaEmail(email):
                flash('Email is already use by other users', 'warning')
                return redirect(url_for('manageaccount'))
            msg = db.updateAccEmail(acc_email,email)
            flash('Account Email Updated! ' +str(msg), 'success')
        #Fname
        if fname != acc_fname:
            msg = db.updateAccFnameById(acc_id,fname)
            flash('Account First Name Updated! ' +str(msg), 'success')
        #Lname
        if lname != acc_lname:
            msg = db.updateAccLnameById(acc_id,lname)
            flash('Account Last Name Updated! ' +str(msg), 'success')
        #Role id
        if str(role_id) != str(acc_role_id):
            msg = db.updateAccRoleIdById(acc_id,role_id)
            flash('Account Role Updated! ' +str(msg), 'success')

    else:
        flash('Invalid Request!', 'warning')
    return redirect(url_for('manageaccount'))

# Delete Account 
@app.route('/deleteaccount',methods=["POST",'GET'])
@testConn
@authentication
@isAdmin
def deleteaccount():
    if request.method == "POST":
        acc_id = request.form.get("deleteaccid")

        acc = db.selectAccountViaId(acc_id)

        if not acc:
            flash('Account doenst exist!', 'danger')
            return redirect(url_for('manageaccount'))

        fullname = (str(acc.get("fname"))+" "+str(acc.get("lname"))).title()
        #Delete the photo if it is not default
        photo = acc.get("photo")
        if acc.get("photo") != app.config["PHOTO_DEFAULT_USER"]:
            try:
                if os.path.exists("static/"+photo):
                    os.remove("static/"+photo)
            except Exception as e:
                flash('Error Occur in Deleting account ! '+str(e), 'warning')
                return redirect(url_for('manageaccount'))
        
        #Delete the account
        msg = db.deleteAccById(acc_id)
        flash(fullname+'\'s account has been deleted! '+str(msg), 'success')
    else:
        flash('Invalid Request!', 'warning')
    return redirect(url_for('manageaccount'))

#================================================== Run APP 
if __name__ == '__main__':
    app.run()
