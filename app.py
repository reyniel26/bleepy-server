#================================================== Imports
#Flask
from re import search
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
from control import *
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

tokenControl = TokenControls(app.secret_key)
basicControl = BasicControls()
pagingControl = PagingControl()
processControl = ProcessControl()

class BleepyControl():
    def customBleepVideo(self,bleepsound:AudioFile, video:VideoFile, lang:str, model:str):

        #Set up
        stt = SpeechToText(model)
        extractor = ProfanityExtractor(lang)
        blocker = ProfanityBlocker()
        blocker.setClipsDirectory("static/media/Trash/Videos")
        blocker.setSaveDirectory("static/media/Storage/Videos/Processed")
        
        #run stt
        stt.run(video)

        #run profanity extractor
        extractor.setProfanities([]) #Reset Profanities
        extractor.run(stt.getResults())
        profanities = extractor.getProfanities()

        #run blocker if has profanity
        block_directory = ''
        if len(profanities) > 0:
                blocker.run(video,bleepsound,profanities)
                block_directory = blocker.getFileLocation()

        #return bleepvideo directory and profanities
        return {"profanities":profanities,"block_directory":block_directory}
    
    def englishBleepVideo(self,bleepsound:AudioFile, video:VideoFile):
        return self.customBleepVideo(bleepsound,video,"english","stt-language-models/model-en")
    
    def tagalogBleepVideo(self,bleepsound:AudioFile, video:VideoFile):
        return self.customBleepVideo(bleepsound,video,"tagalog","stt-language-models/model-ph")


#================================================== App Control Methods
def getIdViaAuth():
    try:
        cookies = request.cookies
        token = cookies.get(app.config["AUTH_TOKEN_NAME"])
        tokenvalues = tokenControl.getTokenValues(token)
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
            value = tokenControl.generateToken(authid=kwargs.get("acc_id"),validuntil=kwargs.get("max_age")),
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
    #Paging
    page = request.args.get("page")
    if not page:
        page = '1'
    viewdata["active_page"] = {
            page:True
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

            viewdata["page_name"] = db.selectNavByLocation(request.path).get('name') if db.selectNavByLocation(request.path) else ""
        
        

    viewdata.update(**kwargs)
    return viewdata

def allowedVideoFileSize(filesize) ->bool:
    return float(filesize) <= app.config['MAX_VIDEO_FILESIZE']

def allowedAudioFileSize(filesize) ->bool:
    return float(filesize) <= app.config['MAX_AUDIO_FILESIZE']

def allowedPhotoFileSize(filesize) ->bool:
    return float(filesize) <= basicControl.bytesToMb(app.config['MAX_PHOTO_FILESIZE'])

def flashPrintsforAdmin(msg,msgname=""):
    acc_id = getIdViaAuth() 
    acc_role = db.selectAccRole(acc_id).get("name")
    if acc_role.lower() == str(app.config["ROLE_ADMIN"]).lower():
        flash(msgname+" Message: "+str(msg), 'info')

def generateLongBleepSound(audio:AudioFile):
    savedirectory = "static/"+app.config['AUDIO_UPLOADS_LONG']
    #Trim the audio
    trimname = "trim"+str(uuid.uuid4()) +"."+audio.getFileExtension()
    trimaudio = "ffmpeg -i {} -af \"silenceremove=start_periods=1:start_duration=1:start_threshold=-60dB:detection=peak,aformat=dblp,areverse,silenceremove=start_periods=1:start_duration=1:start_threshold=-60dB:detection=peak,aformat=dblp,areverse\" {}"
    trimaudio = trimaudio.format(audio.getFile(),savedirectory+"/"+trimname)
    processControl.runSubprocess(trimaudio)
    
    #Save to text file
    txtfilename = savedirectory+"/"+str(uuid.uuid4()) +".txt"
    try:
        f = open(txtfilename, "a")
        for x in range(5):
            f.write("file "+trimname+"\n")
    finally:
        f.close()

    #Create long version
    longname = "long"+str(uuid.uuid4()) +"."+audio.getFileExtension()
    longaudio = "ffmpeg -safe 0 -f concat -i {} -c copy {}"
    longaudio = longaudio.format(txtfilename,savedirectory+"/"+longname)
    processControl.runSubprocess(longaudio)
    

    #Delete trim version
    if os.path.exists(savedirectory+"/"+trimname):
        os.remove(savedirectory+"/"+trimname)

    #Delete the text file
    if os.path.exists(txtfilename):
        os.remove(txtfilename)
    
    #If the long version is created or not
    if os.path.exists(savedirectory+"/"+longname):
        flashPrintsforAdmin("Passed","Making long version of audio: ")
        return longname
    else:
        flashPrintsforAdmin("Failed","Making long version of audio: ")
        #Delete the audio file
        if os.path.exists(audio.getFile()):
            os.remove(audio.getFile())
        return ''

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
    try:
        file.save(os.path.join("static/"+savefolder, uniquefilename))
    except Exception as e:
        flashPrintsforAdmin(e,"Error in saving file: ")

    #SaveToDB
    filelocation = savefolder+"/"+uniquefilename
    savedirectory = "static/"+filelocation
    msg = db.insertVideo(filename,uniquefilename,filelocation,savedirectory)
    flashPrintsforAdmin(msg,"Insert Video")
    vid_id = db.selectVideoByUniqueFilename(uniquefilename).get("video_id")
    msg = db.insertUploadedBy(vid_id,acc_id)
    flashPrintsforAdmin(msg,"Insert Uploaded by")

    fileinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)

    return fileinfo

def saveBleepSound(file,title,uniquefilename):
    
    # Save the file in directory
    savefolder = app.config['AUDIO_UPLOADS_ORIG']
    
    try:
        file.save(os.path.join("static/"+savefolder, uniquefilename))
    except Exception as e:
        flashPrintsforAdmin(e,"Error in saving file: ")
    
    audio = AudioFile()
    audio.setFile("static/"+savefolder+"/"+uniquefilename)

    # Make longer version of the file
    longversion = generateLongBleepSound(audio)
    if longversion:
        # Save to db the data
        filename = title
        filelocation = app.config['AUDIO_UPLOADS_ORIG']+"/"+uniquefilename
        longversion = app.config['AUDIO_UPLOADS_LONG']+"/"+longversion
        msg = db.insertBleepSound(filename,uniquefilename,filelocation,longversion)
        flashPrintsforAdmin(msg,"Insert Bleep sound")

        return True
    else:
        flash('The audio file is not acceptable because the sound volume is too low, try to upload other audio file with higher sound volume', 'danger')
        return False

def updateBleepSound(bleepsound_id,file,title,uniquefilename):
    
    # Save the file in directory
    savefolder = app.config['AUDIO_UPLOADS_ORIG']
    
    try:
        file.save(os.path.join("static/"+savefolder, uniquefilename))
    except Exception as e:
        flashPrintsforAdmin(e,"Error in saving file: ")
    
    audio = AudioFile()
    audio.setFile("static/"+savefolder+"/"+uniquefilename)

    # Make longer version of the file
    longversion = generateLongBleepSound(audio)
    if longversion:
        bleepsound_data = db.selectBleepSoundById(bleepsound_id)
        #Delete the previous data
        #Delete orig version
        if os.path.exists("static/"+bleepsound_data.get("filelocation")):
            os.remove("static/"+bleepsound_data.get("filelocation"))
            flashPrintsforAdmin("Success","Deleted Previous original file: ")

        #Delete long version
        if os.path.exists("static/"+bleepsound_data.get("longversion")):
            os.remove("static/"+bleepsound_data.get("longversion"))
            flashPrintsforAdmin("Success","Deleted Previous longversion file: ")

        # Save to db the data
        filename = title
        filelocation = app.config['AUDIO_UPLOADS_ORIG']+"/"+uniquefilename
        longversion = app.config['AUDIO_UPLOADS_LONG']+"/"+longversion
        msg = db.updateBleepSoundById(bleepsound_id,filename,uniquefilename,filelocation,longversion)
        flashPrintsforAdmin(msg,"Update Bleep sound")

        return True
    else:
        flash('The audio file is not acceptable because the sound volume is too low, try to upload other audio file with higher sound volume', 'danger')
        return False
    
def saveBleepedVideo(vid_id,bleepsound_id,pfilename,pfilelocation,psavedirectory,profanities:list):
    bleepedvideoinfo = {
        "filename":"NaN",
        "filelocation":"NaN"
    }

    try:
        msg = db.insertBleepedVideo(vid_id,bleepsound_id,pfilename,pfilelocation,psavedirectory)
        flashPrintsforAdmin(msg,"Insert Bleeped Video")
        
        bleepedvideoinfo = db.selectBleepVideoByFileName(pfilename)
        pvid_id = bleepedvideoinfo.get("pvideo_id")
        vals = []

        for profanity in profanities:
            item = (profanity["word"],profanity["start"],profanity["end"],profanity.get("lang"),pvid_id)
            vals.append(item)
        
        msg = db.insertProfanities(vals)
        flashPrintsforAdmin(msg,"Insert Profanities")

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
        
        tokenvalues = tokenControl.getTokenValues(token)

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
    page = request.args.get("page")
    search = request.args.get("search") if request.args.get("search") else ""

    #Default
    count = 0    
    limit = app.config['DEFAULT_MAX_LIMIT']
    offset = 0 

    #Count first the search
    count = db.countBleepSoundSearch(search).get('count') if db.countBleepSoundSearch(search) else 0
    
    #Arrange the offset and limit
    offset = pagingControl.generateOffset(page,count,limit)
    
    #Query
    bleepsounds = db.selectBleepSoundsSearchLimitOffset(search,limit,offset)
    latest_bleepsound = db.selectLatestBleepSoundSearch(search)

    resultbadge = pagingControl.generateResultBadge(count,limit,offset,search)
    pagination = pagingControl.generatePagination(count,limit)
    

    return render_template('bleepsoundlist.html', 
    viewdata = viewData(bleepsounds=bleepsounds, 
                        latest_bleepsound = latest_bleepsound,
                        resultbadge=resultbadge,
                        pagination=pagination
                        ) 
    )

#Signup Page
@app.route('/signup', methods=["POST",'GET'])
@testConn
@isAlreadyLoggedin
def signup():
    if request.method == "POST":

        fname = request.form.get("fname").strip()
        lname = request.form.get("lname").strip()
        email = basicControl.sanitizeEmail(request.form.get("email"))
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
        email = basicControl.sanitizeEmail(request.form.get("email"))
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

    widgets_data = {
        "mostfrequentprofanities":db.selectUniqueProfanityWordsByAccount(acc_id),
        "bleepedvideos":db.selectBleepedVideosByAccountSearchLimitOffset(acc_id,"",app.config['DEFAULT_ATLEAST_LIMIT'],0),
        "datetoday":now.strftime("%B %d %Y")+", "+now.strftime("%A")
    }

    feeds = db.selectFeeds(acc_id) if acc_role != app.config["ROLE_ADMIN"] else db.selectAdminFeeds()
    latestbleep_data = db.selectLatestBleepSummaryDataSearch(acc_id,"")

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
        #Update widgets here
        widgets_data["has_uploadedby"] = True
        widgets_data["mostfrequentprofanities"]=db.selectTop10ProfanitiesAll()
        widgets_data["bleepedvideos"]=db.selectBleepedVideosAllSearchLimitOffset("",app.config['DEFAULT_ATLEAST_LIMIT'],0)
        #Update latest bleep
        latestbleep_data = db.selectLatestBleepSummaryDataAllSearch("")
    
    
    return render_template('dashboard.html', 
                        viewdata = viewData( 
                            widgets_data=widgets_data, 
                            admin_data=admin_data, 
                            editor_data=editor_data,
                            feeds=feeds, 
                            latestbleep_data=latestbleep_data 
                            )
    )

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
    max_photo_filesize = basicControl.bytesToMb(app.config["MAX_PHOTO_FILESIZE"])
    
    return render_template('profile.html', 
            viewdata = viewData( user_data = user_data,
            max_photo_filesize=max_photo_filesize
            )
    )

#Video List route
@app.route('/videolist')
@app.route('/videos')
@testConn
@authentication
def videolist():
    page = request.args.get("page")
    search = request.args.get("search") if request.args.get("search") else ""

    #Default
    count = 0    
    limit = app.config['DEFAULT_MAX_LIMIT']
    offset = 0 

    acc_id = getIdViaAuth()
    acc_role = db.selectAccRole(acc_id).get("name")
    videos = {}
    latest_video = {}
    has_uploadedby = False

    if acc_role == app.config["ROLE_ADMIN"]:
        has_uploadedby = True

        #Count first the search
        count = db.countVideosSearch(search).get('count') if db.countVideosSearch(search) else 0
        
        #Arrange the offset and limit
        offset = pagingControl.generateOffset(page,count,limit)

        #Query
        videos = db.selectVideosAllSearchLimitOffset(search,limit,offset)
        latest_video = db.selectLatestUploadedVideoAllSearch(search)
    else:
        #Count first the search
        count = db.countVideosUploadedByAccSearch(acc_id,search).get('count') if db.countVideosUploadedByAccSearch(acc_id,search) else 0
        #Arrange the offset and limit
        offset = pagingControl.generateOffset(page,count,limit)
        
        #Query
        videos = db.selectVideosUploadedByAccountSearchLimitOffset(acc_id,search,limit,offset)
        latest_video = db.selectLatestUploadedVideoSearch(acc_id,search)
    
    resultbadge = pagingControl.generateResultBadge(count,limit,offset,search)
    pagination = pagingControl.generatePagination(count,limit)

    
    return render_template('videolist.html', 
    viewdata = viewData(videolist=True,
                        videos=videos,
                        latest_video=latest_video,
                        has_uploadedby=has_uploadedby,
                        resultbadge=resultbadge,
                        pagination=pagination
                        )
    )

#Bleep Video List route
@app.route('/bleepvideolist')
@app.route('/bleepvideos')
@app.route('/bleepedvideos')
@testConn
@authentication
def bleepvideolist():
    page = request.args.get("page")
    search = request.args.get("search") if request.args.get("search") else ""

    #Default
    count = 0    
    limit = app.config['DEFAULT_MAX_LIMIT']
    offset = 0 
    
    acc_id = getIdViaAuth()
    acc_role = db.selectAccRole(acc_id).get("name")
    bleepedvideos = {}
    latestbleep_data = {}
    has_uploadedby = False

    if acc_role == app.config["ROLE_ADMIN"]:
        has_uploadedby = True

        #Count first the search
        count = db.countBleepVideosSearch(search).get('count') if db.countBleepVideosSearch(search) else 0

        #Arrange the offset and limit
        offset = pagingControl.generateOffset(page,count,limit)

        #Query
        bleepedvideos = db.selectBleepedVideosAllSearchLimitOffset(search,limit,offset)
        latestbleep_data = db.selectLatestBleepSummaryDataAllSearch(search)

    else:
        #Count first the search
        count = db.countBleepVideosUploadedByAccSearch(acc_id,search).get('count') if db.countBleepVideosUploadedByAccSearch(acc_id,search) else 0

        #Arrange the offset and limit
        offset = pagingControl.generateOffset(page,count,limit)
        
        #Query
        bleepedvideos = db.selectBleepedVideosByAccountSearchLimitOffset(acc_id,search,limit,offset)
        latestbleep_data = db.selectLatestBleepSummaryDataSearch(acc_id,search)
    
    resultbadge = pagingControl.generateResultBadge(count,limit,offset,search)
    pagination = pagingControl.generatePagination(count,limit)
    
    return render_template('bleepvideolist.html', 
    viewdata = viewData(bleepvideolist=True,
                        bleepedvideos=bleepedvideos,
                        latestbleep_data=latestbleep_data,
                        has_uploadedby=has_uploadedby,
                        resultbadge = resultbadge,
                        pagination = pagination
                        )
    )

#Bleep Video Info route
@app.route('/bleepvideoinfo/<path>',methods=["POST",'GET'])
@testConn
@authentication
def bleepvideoinfo(path):
    acc_id = getIdViaAuth()
    acc_role = db.selectAccRole(acc_id).get("name")
    bleepinfo_data = {}
    has_uploadedby = False
    if path:
        bleepvideo_id = path
        if acc_role == app.config["ROLE_ADMIN"]:
            has_uploadedby = True
            bleepinfo_data = db.selectBleepedVideoFullInfo(bleepvideo_id)
        else:
            bleepinfo_data = db.selectBleepedVideoFullInfoById(acc_id,bleepvideo_id)

    return render_template('bleepvideoinfo.html', viewdata = viewData(bleepvideolist=True,bleepinfo_data=bleepinfo_data,has_uploadedby=has_uploadedby))

#Bleep Video Page
@app.route('/bleepvideo')
@testConn
@authentication
def bleepvideo():
    acc_id = getIdViaAuth() 

    videos = db.selectVideosUploadedByAccount(acc_id)
    
    return render_template('bleepvideo.html', viewdata = viewData(videos=videos))

#Delete Files
#Delete Video
@app.route('/deletevideo', methods=["POST",'GET'])
@testConn
@authentication
def deletevideo():
    acc_id = getIdViaAuth()
    acc_role = db.selectAccRole(acc_id).get("name")
    video_id = request.form.get("path")
    videoinfo ={}
    if request.method == 'POST':
        if acc_role == app.config["ROLE_ADMIN"]:
            videoinfo = db.selectVideoByVidId(video_id)
        else:
            videoinfo = db.selectVideoByAccountAndVidId(acc_id,video_id)

        if not videoinfo:
            flash("The video is not exist",'danger')
            return redirect(url_for('videolist'))
        
        #Delete Video
        try:
            if os.path.exists("static/"+videoinfo.get('filelocation')):
                os.remove("static/"+videoinfo.get('filelocation'))
        except Exception as e:
            flash("Problem occur while deleting the video. "+str(e),'danger')
            return redirect(url_for('videolist'))

        #Delete Record
        msg = db.deleteVideoByVidId(video_id)
        flashPrintsforAdmin(msg,"Delete Video: ")
        flash(videoinfo.get('filename')+" is now deleted. ",'success')
        return redirect(url_for('videolist'))
    else:
        flash("Invalid Request",'danger')
        return redirect(url_for('videolist'))

#Delete Bleep Video
@app.route('/deletebleepvideo', methods=["POST",'GET'])
@testConn
@authentication
def deletebleepvideo():
    acc_id = getIdViaAuth()
    acc_role = db.selectAccRole(acc_id).get("name")
    bleepvideo_id = request.form.get("path")
    bleepvideoinfo ={}
    if request.method == 'POST':
        if acc_role == app.config["ROLE_ADMIN"]:
            bleepvideoinfo = db.selectBleepedVideoByPvid(bleepvideo_id)
        else:
            bleepvideoinfo = db.selectBleepedVideosByAccountAndPvid(acc_id,bleepvideo_id)

        if not bleepvideoinfo:
            flash("The video is not exist",'danger')
            return redirect(url_for('bleepvideolist'))
        
        #Delete Video
        try:
            if os.path.exists("static/"+bleepvideoinfo.get('pfilelocation')):
                os.remove("static/"+bleepvideoinfo.get('pfilelocation'))
        except Exception as e:
            flash("Problem occur while deleting the video. "+str(e),'danger')
            return redirect(url_for('bleepvideolist'))
        
        #Delete Pword records
        msg = db.deleteProfanityWordsByVidId(bleepvideo_id)
        flashPrintsforAdmin(msg,"Delete Profanities from bleep video: ")
        flash(" Profanity records of the video is also deleted. ",'success')
        #Delete Record of Video
        msg = db.deleteBleepVideoByVidId(bleepvideo_id)
        flashPrintsforAdmin(msg,"Delete Bleep Video: ")
        flash(bleepvideoinfo.get('filename')+" Bleep Version is now deleted. ",'success')
        return redirect(url_for('bleepvideolist'))
    else:
        flash("Invalid Request",'danger')
        return redirect(url_for('bleepvideolist'))

#================Get files JSON
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
    
        filelocation = url_for('static', filename=bleepsoundinfo.get("filelocation") )  if bleepsoundinfo else ""
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
        acc_role = db.selectAccRole(acc_id).get("name")
        vid_id = request.form.get("vid_id")
        videoinfo = {}

        #videoinfo contains = filelocation, filename, see db
        if acc_role == app.config["ROLE_ADMIN"]:
            videoinfo = db.selectVideoByVidId(vid_id)
        else:
            videoinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)
        
        
        filelocation = url_for('static', filename=videoinfo.get("filelocation") ) if videoinfo  else ""
        filename = videoinfo.get("filename")
        upload_time= videoinfo.get("upload_time")
        uploadedby=videoinfo.get("uploadedby")

        return jsonify({
            "filelocation":filelocation,
            "filename":filename,
            "upload_time":upload_time,
            "uploadedby":uploadedby
        })

    return jsonify('')

#Get bleep video info json
@app.route('/getbleepvideoinfo', methods=["POST",'GET'])
@testConn
@authentication
def getbleepvideoinfo():
    if request.method == "POST":
        acc_id = getIdViaAuth() 
        acc_role = db.selectAccRole(acc_id).get("name")
        bleepinfo_data = {}
        bleepvideo_id = request.form.get("vid_id")

        #videoinfo contains = filelocation, filename, see db
        if acc_role == app.config["ROLE_ADMIN"]:
            bleepinfo_data = db.selectBleepedVideoFullInfo(bleepvideo_id)
        else:
            bleepinfo_data = db.selectBleepedVideoFullInfoById(acc_id,bleepvideo_id)
        
        pvideo_id ="/bleepvideoinfo/"+str(bleepinfo_data.get("bleepinfo").get("pvideo_id")) 
        filelocation = url_for('static', filename=bleepinfo_data.get("bleepinfo").get("filelocation") ) if bleepinfo_data else ""
        filename = bleepinfo_data.get("bleepinfo").get("filename")
        upload_time= bleepinfo_data.get("bleepinfo").get("upload_time")
        bfilename=bleepinfo_data.get("bleepinfo").get("bfilename")
        process_time=bleepinfo_data.get("bleepinfo").get("process_time")
        pfilelocation = url_for('static', filename=bleepinfo_data.get("bleepinfo").get("pfilelocation") )if bleepinfo_data else ""

        uploadedby=bleepinfo_data.get("uploadedby")
        uniqueprofanitycount =bleepinfo_data.get("uniqueprofanitycount")
        mostfrequentword=bleepinfo_data.get("mostfrequentword")

        return jsonify({
            "pvideo_id":pvideo_id,
            "filelocation":filelocation,
            "filename":filename,
            "upload_time":upload_time,
            "uploadedby":uploadedby,
            "bfilename":bfilename,
            "uniqueprofanitycount":uniqueprofanitycount,
            "mostfrequentword":mostfrequentword,
            "process_time":process_time,
            "pfilelocation":pfilelocation
        })

    return jsonify('')

#================Download Files
#Download bleep video
@app.route('/downloadbleeped/<path>', methods=["POST",'GET'])
@testConn
@authentication
def downloadbleeped(path):
    acc_id = getIdViaAuth()
    acc_role = db.selectAccRole(acc_id).get("name")
    bleepvideo_id = path
    try:
        if acc_role == app.config["ROLE_ADMIN"]:
            bleepedvideoinfo = db.selectBleepedVideoByPvid(bleepvideo_id)
        else:
            bleepedvideoinfo = db.selectBleepedVideosByAccountAndPvid(acc_id,bleepvideo_id)
        file_path = "static/"+bleepedvideoinfo.get("pfilelocation")
        filename = "bleepedversion"+bleepedvideoinfo.get("filename")
        return send_file(file_path,as_attachment=True,attachment_filename=filename)
    except Exception as e:
        errormsg = "Request has been denied"+str(e)
        return render_template('includes/_messages.html', error=errormsg)
 
#Download Video
@app.route('/downloadvideo/<path>', methods=["POST",'GET'])
@testConn
@authentication
def downloadvideo(path):
    acc_id = getIdViaAuth()
    acc_role = db.selectAccRole(acc_id).get("name")
    video_id = path
    videoinfo = {}
    try:
        if acc_role == app.config["ROLE_ADMIN"]:
            videoinfo = db.selectVideoByVidId(video_id)
        else:
            videoinfo = db.selectVideoByAccountAndVidId(acc_id,video_id)
        file_path = "static/"+videoinfo.get("filelocation")
        filename = videoinfo.get("filename")
        return send_file(file_path,as_attachment=True,attachment_filename=filename)
    except Exception as e:
        errormsg = "Request has been denied "+str(e)
        return render_template('includes/_messages.html', error=errormsg)

#Download Bleep Sounds
#Doenst need auth
@app.route('/downloadbleepsound/<path>', methods=["POST",'GET'])
@testConn
@authentication
def downloadbleepsound(path):
    bleepsound_id = path
    bleepsound = {}
    try:
        bleepsound = db.selectBleepSoundById(bleepsound_id)
        file_path = "static/"+bleepsound.get("filelocation")
        filename = bleepsound.get("filename")
        return send_file(file_path,as_attachment=True,attachment_filename=filename)
    except Exception as e:
        errormsg = "Request has been denied "+str(e)
        return render_template('includes/_messages.html', error=errormsg)


#================Bleep Steps
#Routes for Bleep Steps
#@authentication

#BleepStep1 
@app.route('/bleepstep1', methods=["POST",'GET'])
@testConn
@authentication
def bleepstep1():
    if request.method == "POST":
        acc_id = getIdViaAuth() 
        video = VideoFile()

        videoinfo = {
            "filename":"Error",
            "filelocation":"Error"
        }

        bleepsounds = db.selectBleepSounds()
        langs = app.config['LANGS']
        defaultLang = app.config['DEFAULT_LANG']
        est_multiplier = app.config['DEFAULT_EST_MULTIPLIER']
        video_duration = 0.0

        #If choose video
        if request.form.get("choosevideo"):

            vid_id = request.form.get("vid_id")
            videoinfo = db.selectVideoByAccountAndVidId(acc_id,vid_id)

            video.setFile("static/"+videoinfo.get('filelocation'))
            video_duration = video.getDuration()

            msg = str(videoinfo.get("filename"))+" has been choosen"

        elif request.files.get("uploadFile"):
            file = request.files.get("uploadFile")
            # print(request.cookies.get('filesize'))

            # if not allowedVideoFileSize(request.cookies.get('filesize')):
            if not allowedVideoFileSize(request.form.get('uploadfilesize')):
                errormsg = "File too large. Maximum File size allowed is "+str(basicControl.bytesToGb(app.config["MAX_VIDEO_FILESIZE"]))+" gb"
                return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })

            
            
            if not video.isAllowedExt(video.getExtension(file.filename)):
                errormsg = "File type is not allowed. Allowed file extension are: "+str(video.getAllowedExts())
                return jsonify({'responsemsg': render_template('includes/_messages.html', error=errormsg) })
            
            #Save Video
            filename = file.filename
            uniquefilename = str(uuid.uuid4()) +"."+video.getExtension(file.filename)

            videoinfo = saveVideo(file,filename,uniquefilename,acc_id)

            video.setFile("static/"+videoinfo.get('filelocation'))
            video_duration = video.getDuration()

            msg = "File Uploaded Successfully"

        return jsonify({ 'bleepstep1response': render_template('includes/bleepstep/_bleepstep2.html', 
                            viewdata = viewData(videoinfo=videoinfo,
                                bleepsounds=bleepsounds, 
                                langs=langs,
                                defaultLang=defaultLang,
                                video_duration=video_duration,
                                est_multiplier = est_multiplier 
                            )
                        ) ,
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
        lang = request.form.get('lang')
        flashPrintsforAdmin(lang,"Language")

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
        
        video.setFile("static/"+video_filelocation) #Set up the original video
        audio.setFile("static/"+bleep_longversion)
        

        try:
            bleepyinfo = {}
            profanities = []
            bleepyControl = BleepyControl()

            #Choose language
            if lang.lower() == 'english':
                flashPrintsforAdmin("English","Language")
                bleepyinfo = bleepyControl.englishBleepVideo(audio,video)
                profanities.extend(bleepyinfo.get("profanities"))
            elif lang.lower() == 'tagalog':
                flashPrintsforAdmin("Tagalog","Language")
                bleepyinfo = bleepyControl.tagalogBleepVideo(audio,video)
                profanities.extend(bleepyinfo.get("profanities"))
            elif lang.lower() == 'tagalog-english':
                flashPrintsforAdmin("Tagalog-English","Language")
                #Tagalog first
                bleepyinfo = bleepyControl.tagalogBleepVideo(audio,video)
                profanities.extend(bleepyinfo.get("profanities"))

                tagalogOnlyBleepDir = bleepyinfo.get("block_directory") if bleepyinfo.get("block_directory") else ""
                if bleepyinfo.get("block_directory"):
                    video.setFile(bleepyinfo.get("block_directory"))

                #then english
                bleepyinfo = bleepyControl.englishBleepVideo(audio,video)
                profanities.extend(bleepyinfo.get("profanities"))

                #delete tagalog only bleep
                if tagalogOnlyBleepDir:
                    if os.path.exists(tagalogOnlyBleepDir):
                        os.remove(tagalogOnlyBleepDir)
                        flashPrintsforAdmin("Deleted","Delete tagalog only bleep")
            else:
                flash('Invalid language', 'danger')
            
            #Save to db
            if len(profanities) > 0:
                block_directory = bleepyinfo.get("block_directory")
                block_filelocation = basicControl.removeStaticDirectory(block_directory)
                block_filename = basicControl.getFileNameFromDirectory(block_filelocation)
                bleepedvideoinfo = saveBleepedVideo(vid_id,bleepsound_id,block_filename,block_filelocation,block_directory,profanities)
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

        newemail = basicControl.sanitizeEmail(request.form.get("email"))
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
                flash("File too large. Maximum File size allowed is "+str(basicControl.bytesToMb(app.config["MAX_PHOTO_FILESIZE"]))+" mb", 'warning')
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
    page = request.args.get("page")
    search = request.args.get("search") if request.args.get("search") else ""

    #Default
    count = 0    
    limit = app.config['DEFAULT_MAX_LIMIT']
    offset = 0 

    #Count first the search
    count = db.countAccountsSearch(search).get('count') if db.countAccountsSearch(search) else 0

    #Arrange the offset and limit
    offset = pagingControl.generateOffset(page,count,limit)

    #Query the data
    accounts = db.selectAccountAllSearchLimitOffset(search,limit,offset)

    roles = db.selectRoles()

    resultbadge = pagingControl.generateResultBadge(count,limit,offset,search)
    pagination = pagingControl.generatePagination(count,limit)

    defaultpwd = app.config["DEFAULT_ACC_PWD"]
    return render_template('admin/manageaccount.html', 
    viewdata = viewData(accounts=accounts,
                        roles=roles, 
                        defaultpwd=defaultpwd, 
                        pagination=pagination,
                        resultbadge = resultbadge
                        )
    )

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
        email = basicControl.sanitizeEmail(request.form.get("addemail"))
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
        email = basicControl.sanitizeEmail(request.form.get("editemail"))
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
        
        #Delete uploaded by record
        msg = db.deleteUploadedById(acc_id)
        flashPrintsforAdmin(msg,"Uploaded Records are also deleted:")
        #Delete the account
        msg = db.deleteAccById(acc_id)
        
        flash(fullname+'\'s account has been deleted! '+str(msg), 'success')
    else:
        flash('Invalid Request!', 'warning')
    return redirect(url_for('manageaccount'))

#==============Editor Pages
# Manage Bleep Sounds
@app.route('/managebleepsounds')
@testConn
@authentication
@isEditor
def managebleepsounds():
    page = request.args.get("page")
    search = request.args.get("search") if request.args.get("search") else ""

    #Default
    count = 0    
    limit = app.config['DEFAULT_MAX_LIMIT']
    offset = 0 

    #Count first the search
    count = db.countBleepSoundSearch(search).get('count') if db.countBleepSoundSearch(search) else 0
    
    #Arrange the offset and limit
    offset = pagingControl.generateOffset(page,count,limit)
    
    #Query
    bleepsounds = db.selectBleepSoundsSearchLimitOffset(search,limit,offset)
    latest_bleepsound = db.selectLatestBleepSoundSearch(search)

    resultbadge = pagingControl.generateResultBadge(count,limit,offset,search)
    pagination = pagingControl.generatePagination(count,limit)


    return render_template('editor/managebleepsounds.html', 
    viewdata = viewData(bleepsounds=bleepsounds, 
                        latest_bleepsound = latest_bleepsound,
                        resultbadge=resultbadge,
                        pagination=pagination
                        )
    )

# View Bleep sound
@app.route('/viewbleepsound',methods=["POST",'GET'])
@testConn
@authentication
@isEditor
def viewbleepsound():
    data = {}
    if request.method == "POST":
        if request.form.get("bleepsound_id"):
            data = db.selectBleepSoundById(request.form.get("bleepsound_id"))

    bleepsound = {
        "bleep_sound_id":data.get('bleep_sound_id'),
        "filename":data.get('filename'),
        "filelocation":url_for('static', filename=data.get("filelocation") )  if data else "",
        "longversion":data.get('longversion'),
        "upload_time":data.get('upload_time')
    }
    return jsonify(bleepsound)

# Add Bleep sound
@app.route('/addbleepsound',methods=["POST",'GET'])
@testConn
@authentication
@isEditor
def addbleepsound():
    if request.method == "POST":
        # Post request 
        file = request.files.get("addfile")
        title = request.form.get("addtitle")
        filesize = request.form.get("addfilesize")

        if not (file and filesize and title):
            #If the fields are null
            flash('Invalid! Empty Fields!', 'danger')
            return redirect(url_for('managebleepsounds'))
        
        if not allowedAudioFileSize(filesize):
            #If the filesize exceeds
            errormsg = "File too large. Maximum File size allowed is "+str(basicControl.bytesToMb(app.config["MAX_AUDIO_FILESIZE"]))+" mb"
            flash(errormsg, 'danger')
            return redirect(url_for('managebleepsounds'))

        # Validate the file
        audio = AudioFile()

        if not audio.isAllowedExt(audio.getExtension(file.filename)):
            #If the file ext is not allowed
            errormsg = "File type is not allowed. Allowed file extension are: "+str(audio.getAllowedExts())
            flash(errormsg, 'danger')
            return redirect(url_for('managebleepsounds'))
        
        #Save Bleep sound
        uniquefilename = str(uuid.uuid4()) +"."+audio.getExtension(file.filename)
        if saveBleepSound(file,title,uniquefilename):
            flash('New bleep sound is added!', 'success')
    else:
        flash('Invalid Request!', 'warning')
    return redirect(url_for('managebleepsounds'))

# Edit Bleep sound
@app.route('/editbleepsound',methods=["POST",'GET'])
@testConn
@authentication
@isEditor
def editbleepsound():
    if request.method == "POST":
        bleepsound_id =  request.form.get("editbleepsoundid")
        title = request.form.get("edittitle")
        if not (bleepsound_id and title):
            flash('Empty fields', 'danger')
            return redirect(url_for('managebleepsounds'))
        
        file = request.files.get("editfile")

        if file:
            filesize = request.form.get("editfilesize")

            if not filesize:
                flash('Empty fields', 'danger')
                return redirect(url_for('managebleepsounds'))
            
            if not allowedAudioFileSize(filesize):
                #If the filesize exceeds
                errormsg = "File too large. Maximum File size allowed is "+str(basicControl.bytesToMb(app.config["MAX_AUDIO_FILESIZE"]))+" mb"
                flash(errormsg, 'danger')
                return redirect(url_for('managebleepsounds'))

            # Validate the file
            audio = AudioFile()

            if not audio.isAllowedExt(audio.getExtension(file.filename)):
                #If the file ext is not allowed
                errormsg = "File type is not allowed. Allowed file extension are: "+str(audio.getAllowedExts())
                flash(errormsg, 'danger')
                return redirect(url_for('managebleepsounds'))
            
            # Update file
            uniquefilename = str(uuid.uuid4()) +"."+audio.getExtension(file.filename)
            if updateBleepSound(bleepsound_id,file,title,uniquefilename):
                flash('Bleep sound has been updated!', 'success')
        else:
            msg = db.updateBleepSoundFilenameById(bleepsound_id,title)
            flashPrintsforAdmin(msg,"Update Bleep sound")
            flash('Bleep sound title has been updated!', 'success')
    else:
        flash('Invalid Request!', 'warning')
    return redirect(url_for('managebleepsounds'))

# Delete Bleep sound
@app.route('/deletebleepsound',methods=["POST",'GET'])
@testConn
@authentication
@isEditor
def deletebleepsound():
    if request.method == "POST":
        # Post request 
        bleepsound_id =  request.form.get("deletebleepsoundid")
        if not bleepsound_id:
            flash('Empty fields', 'danger')
            return redirect(url_for('managebleepsounds'))

        bleepsound_data = db.selectBleepSoundById(bleepsound_id)

        if not bleepsound_data:
            flash('Bleep sound not exist', 'danger')
            return redirect(url_for('managebleepsounds'))

        # Delete original sound
        try:
            if os.path.exists("static/"+bleepsound_data.get('filelocation')):
                os.remove("static/"+bleepsound_data.get('filelocation'))
                msg = bleepsound_data.get('filename')+" original version bleep sound  deleted with a file name "+bleepsound_data.get('filelocation')
                flashPrintsforAdmin(msg,"Delete Bleep sound:")
        except Exception as e:
            flash("Problem occur while deleting the bleepsound. "+str(e),'danger')
        

        # Delete long version
        try:
            if os.path.exists("static/"+bleepsound_data.get('longversion')):
                os.remove("static/"+bleepsound_data.get('longversion'))
                msg = bleepsound_data.get('filename')+" original version bleep sound  deleted with a file name "+bleepsound_data.get('longversion')
                flashPrintsforAdmin(msg,"Delete Bleep sound:")
        except Exception as e:
            flash("Problem occur while deleting the bleepsound. "+str(e),'danger')

        # Delete data
        msg = db.deleteBleepSoundById(bleepsound_id)
        flashPrintsforAdmin(msg,"Delete Bleep sound:")

        flash('Bleep sound succesfully deleted', 'success')
    else:
        flash('Invalid Request!', 'warning')
    return redirect(url_for('managebleepsounds'))

#================================================== Run APP 
if __name__ == '__main__':
    app.run()
