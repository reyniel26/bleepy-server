#JWT
import jwt

class Controls:
    pass

class TokenControls(Controls):
    def __init__(self,secret_key):
        self.__secret_key = secret_key

    def generateToken(self,**kwargs:str):
        """
        To generate token, specify the key and values
        Example: key_one="the value_one",key_two="value_two" 
        """
        token = jwt.encode(kwargs,self.__secret_key,algorithm="HS256")
        return token
    
    def getTokenValues(self,token:str):
        """
        Return Dict value of JWT or return None if the token is invalid
        """
        try:
            values = jwt.decode(token,self.__secret_key,algorithms=["HS256"])
            return values
        except:
            return None


class BasicControls(Controls):

    def sanitizeEmail(self,email:str):
        """
        Sanitize email by removing invalid characters
        """
        invalids = [" ","\"","\\", "/", "<", ">","|","\t",":"]
        for x in invalids:
            email = email.strip(x)
        return email.strip()
    
    def bytesToGb(self,bytesize):
        return bytesize / (1024*1024*1024)

    def bytesToMb(self,bytesize):
        return bytesize / (1024*1024)

    def removeStaticDirectory(self,directory):
        "This remove static"
        filelocation = ""
        if "static" in directory:
            for i in directory.split("/")[1:]:
                filelocation+=i+"/"
            filelocation = filelocation[:-1]
        else:
            filelocation = directory
        return filelocation

    def getFileNameFromDirectory(self,directory):
        directory = self.removeStaticDirectory(directory)
        return directory.split("/")[-1]
    