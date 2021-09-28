class Config(object):
    DEBUG = False
    TESTING = False

    SECRET_KEY = 'bL33py_sE12v3r'
    AUTH_TOKEN_NAME = 'blpytkn'

    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PWD = ''
    DB_NAME = 'bleepyserverprototype'

    #PATHS
    VIDEO_UPLOADS_TEMP = ''
    VIDEO_UPLOADS = 'media/Storage/Videos/Uploads'
    VIDEO_PROCESSED = 'media/Storage/Videos/Uploads/Processed'
    VIDEO_TRASH = ''

    MAX_VIDEO_FILESIZE = (1024*1024*1024)*1 #In Bytes : (1024*1024*1024) = 1GB
    MAX_FILESIZE_GB = MAX_VIDEO_FILESIZE / (1024*1024*1024)

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