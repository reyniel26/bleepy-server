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
    VIDEO_UPLOADS = ''
    VIDEO_TRASH = ''

class ProductionConfig(Config):
    pass

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True

    SECRET_KEY = 'bL33py_sE12v3r'

    DB_HOST = 'localhost'
    DB_USER = 'root'
    DB_PWD = ''
    DB_NAME = 'bleepyserverprototype'