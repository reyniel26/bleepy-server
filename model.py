import mysql.connector

class Model:
    def __init__(self,host,user,password,database):
        self.__host =host
        self.__user =user
        self.__password =password
        self.__database =database
        self.__conn = False
    
    def initConn(self):
        try:
            dbconn = mysql.connector.connect(
                host = self.__host,
                user = self.__user,
                password = self.__password,
                database = self.__database
            )
            self.__conn = dbconn
            return True
        except:
            return False
    
    def hasConnection(self):
        if(self.initConn()):
            self.conn.close()
            return True
        return False
    
    @property
    def conn(self):
        return self.__conn
    
    @property
    def cur(self):
        return self.conn.cursor(prepared=True)
    
    def querySelect(self,sql,*args):
        """
        This will only fetchone
        """
        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,args)

                result = cur.fetchone()
                if result:
                    result =dict(zip(cur.column_names, result))
        
                self.conn.close()
                return result
            except Exception as e:
                return "Error: "+ str(e)
        return False

    def querySelectAll(self,sql,*args):
        """
        This will do fetch all
        """
        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,args)

                result = cur.fetchall()
                if result:
                    if len(result) > 1:
                        temp = []
                        for x in result:
                            x = dict(zip(cur.column_names, x))
                            temp.append(x)
                        result = tuple(temp)
                    else:
                        result =dict(zip(cur.column_names, result))
        
                self.conn.close()
                return result
            except Exception as e:
                return "Error: "+ str(e)
        return False
    
    def queryInsert(self,sql,*args):
        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,args)

                self.conn.commit()
                result = cur.rowcount

                self.conn.close()
                return str(result) + " record(s) inserted"
            except Exception as e:
                return e
        return False
    
    #================================================== Selects
    def selectAccounts(self):
        return self.querySelectAll("Select * from accounts")
    
    def selectAccountViaEmail(self,email:str):
        return self.querySelect("call sp_select_account_via_email(%s)",email)
    
    def selectAccountViaId(self,id:str):
        return self.querySelect("call sp_select_account_via_id(%s)",id)
    
    def countVideosUploadedByAcc(self,id:str):
        return self.querySelect("call sp_count_videos_uploadedby_account(%s)",id)
    
    def countBleepVideosUploadedByAcc(self,id:str):
        return self.querySelect("call sp_count_censored_videos_by_accounts(%s)",id)
    
    def countProfanityWordsByAcc(self,id:str):
        return self.querySelect("call sp_count_profanitywords_collected_by_account(%s)",id)
    
    def countUniqueProfanityWordsByAcc(self,id:str):
        return self.querySelect("call sp_count_unique_profanitywords_collected_by_account(%s)",id)

    def selectFeeds(self,id):
        """
        As of now it only return the data for specific user
        Admin Feeds is not yet included
        """
        feeds = []
        stmts = [
            (str(self.countVideosUploadedByAcc(id).get("count")),"Uploaded Videos","info","video-camera","/videos"),
            (str(self.countBleepVideosUploadedByAcc(id).get("count")),"Bleeped Videos","olive","soundcloud","/bleepedvideos"),
            (str(self.countProfanityWordsByAcc(id).get("count")),"Profanities Collected","maroon","comments-o","/profanities"),
            (str(self.countUniqueProfanityWordsByAcc(id).get("count")),"Unique Profanities","purple","commenting-o","/uniqueprofanities")
        ]
        for stmt in stmts:
            feed = {
                "count":stmt[0],
                "title":stmt[1].title(),
                "bgcolor":stmt[2],
                "icon":stmt[3],
                "link":stmt[4]
            }
            feeds.append(feed)
        
        return feeds

    def selectLatestBleep(self,id):
        return self.querySelect("call sp_select_latest_censored_videos_by_account(%s)",id)
    
    def selectUniqueProfanityWordsByVideo(self,pvid:str):
        return self.querySelectAll("call sp_select_unique_profanitywords_of_video(%s)",pvid)
    
    #================================================== Inserts
    def insertRole(self,rolename):
        return self.queryInsert("call sp_add_roles(%s)",rolename)
    
    
    

            
        
    
    
    

        

    









