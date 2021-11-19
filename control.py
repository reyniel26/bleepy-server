#JWT
import jwt
#
import subprocess

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

class PagingControl(Controls):
    def generatePagination(self,count,limit):
        return [str(x+1 )for x in range((count//limit)+(1 if count%limit != 0 else 0))]
    
    def generateResultBadge(self,count,limit,offset,search):
        return {
            "start": offset + 1,
            "end":offset+limit if offset+limit < count else count,
            "count":count if count > 0 else None,
            "search":search
        }
    
    def generateOffset(self,page,count,limit):
        offset = 0
        if page:
            try:
                offset = limit*(int(page)-1)
            except:
                if page == "end":
                    offset = limit*(int(count//limit))
        return offset
    
class ProcessControl():
    def runSubprocess(self,stmt):
        process = subprocess.Popen(stmt, stdout=subprocess.PIPE)
        while True:
            data = process.stdout.read(4000)
            if len(data) == 0:
                break
    