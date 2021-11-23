class Config(object):
    DEBUG = False
    TESTING = False

    SECRET_KEY = 'bL33py_sE12v3r'
    AUTH_TOKEN_NAME = 'blpytkn'
    AUTH_MAX_AGE = (60*60*24*30) #30days
    AUTH_MIN_AGE = (60*5) #5mins

    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PWD = ''
    DB_NAME = 'bleepyserverprototype'

    #ROLES
    ROLE_ADMIN = 'admin'
    ROLE_EDITOR = 'editor'
    ROLE_USER= 'user'

    #PATHS
    VIDEO_UPLOADS_TEMP = ''
    VIDEO_UPLOADS = 'media/Storage/Videos/Uploads'
    VIDEO_PROCESSED = 'media/Storage/Videos/Uploads/Processed'
    VIDEO_TRASH = ''

    AUDIO_UPLOADS_ORIG = 'media/Storage/Audios/orig'
    AUDIO_UPLOADS_LONG = 'media/Storage/Audios/long'

    PHOTO_DEFAULT = 'media/Defaults/Images'
    PHOTO_DEFAULT_USER = PHOTO_DEFAULT+'/default.jpg'
    PHOTO_UPLOADS = 'media/Storage/Images'

    SIZE_GB = (1024*1024*1024)
    SIZE_MB = (1024*1024)
    MAX_VIDEO_FILESIZE = SIZE_GB*1 #In Bytes : (1024*1024*1024) = 1GB
    MAX_AUDIO_FILESIZE = SIZE_MB*25
    MAX_PHOTO_FILESIZE = SIZE_MB*5 #In bytes: (1024*1024) = 1MB

    #Defaults
    DEFAULT_ACC_PWD = 'Password1234'
    DEFAULT_MAX_LIMIT = 10
    DEFAULT_ATLEAST_LIMIT = 10

    DEFAULT_LANG  = 'tagalog-english'
    LANGS = ["tagalog-english","english","tagalog"]



class ProductionConfig(Config):
    pass

class DevelopmentConfig(Config):
    """
    Development ENV , the flask server always restart in every changes
    because of DEBUG = True
    """
    DEBUG = True

    SECRET_KEY = 'bL33py_sE12v3r'

    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PWD = ''
    DB_NAME = 'bleepyserverprototype'

class TestingConfig(Config):
    TESTING = True

    SECRET_KEY = 'bL33py_sE12v3r'

    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PWD = ''
    DB_NAME = 'bleepyserverprototype'