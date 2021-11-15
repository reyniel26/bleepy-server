from typing import Dict
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
                return {"error":e}
        return {"error": "There is no connection"}

    def querySelectAll(self,sql,*args):
        """
        This will do fetch all
        """
        error = {"error":"There is no connection"}
        temp = []
        temp.append(error)
        error = tuple(temp)

        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,args)

                result = cur.fetchall()
                if result:
                    temp = []
                    for x in result:
                        x = dict(zip(cur.column_names, x))
                        temp.append(x)
                    result = tuple(temp)

                self.conn.close()
                return result
            except Exception as e:
                error["error"] = e
                temp = []
                temp.append(error)
                return tuple(temp)

        return error
    
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
                return str(e)
        return "Error: There is no connection"
    
    def queryInsertMany(self,sql,vals:list):
        if(self.initConn()):
            try:
                cur = self.cur
                cur.executemany(sql,vals)

                self.conn.commit()
                result = cur.rowcount

                self.conn.close()
                return str(result) + " record(s) inserted"
            except Exception as e:
                return str(e)
        return "Error: There is no connection"
    
    def queryUpdate(self,sql,*args):
        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,args)

                self.conn.commit()
                result = cur.rowcount

                self.conn.close()
                return str(result) + " record(s) updated"
            except Exception as e:
                return str(e)
        return "Error: There is no connection"

    def queryDelete(self,sql,*args):
        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,args)

                self.conn.commit()
                result = cur.rowcount

                self.conn.close()
                return str(result) + " record(s) deleted"
            except Exception as e:
                return str(e)
        return "Error: There is no connection"

    #================================================== Selects
    def selectAccounts(self):
        return self.querySelectAll("Select * from accounts")
    
    def selectAccountViaEmail(self,email:str):
        return self.querySelect("call sp_select_account_via_email(%s)",email)
    
    def selectAccountViaId(self,id:str):
        return self.querySelect("call sp_select_account_via_id(%s)",id)
    
    def selectFeeds(self,id:str):
        """
        As of now it only return the data for specific user
        Admin Feeds is not yet included
        """
        feeds = []
        stmts = [
            (str(self.countVideosUploadedByAcc(id).get("count")),"Uploaded Videos","info","video-camera","/videolist"),
            (str(self.countBleepVideosUploadedByAcc(id).get("count")),"Bleeped Videos","olive","soundcloud","/bleepvideolist"),
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
    
    def selectLatestBleepSound(self):
        return self.querySelect("call sp_select_latest_bleep_sound()")

    def selectLatestBleep(self,id:str):
        return self.querySelect("call sp_select_latest_censored_videos_by_account(%s)",id)
    
    def selectLatestBleepAll(self):
        return self.querySelect("call sp_select_latest_censored_videos_all()")
    
    def selectLatestUploadedVideo(self,id:str):
        return self.querySelect("call sp_select_latest_video_by_account(%s)",id)
    
    def selectLatestUploadedVideoAll(self):
        return self.querySelect("call sp_select_latest_video_all()")
    
    def selectLatestBleepDataBuilder(self,latestbleep:dict):
        latestbleep_data = {}
        if latestbleep:
            latestbleep_data ={
                "latestbleep":latestbleep,
                "uniqueprofanities":self.selectUniqueProfanityWordsByVideo(latestbleep.get("pvideo_id")),
                "uniqueprofanitycount":self.countUniqueProfanityWordsByBleepedVideo(latestbleep.get("pvideo_id")).get("count"),
                "mostfrequentword":self.selectMostFrequentProfanityWordByVideo(latestbleep.get("pvideo_id")).get("word")
            }
        return latestbleep_data

    def selectLatestBleepSummaryData(self,id:str):
        latestbleep = self.selectLatestBleep(id)
        return self.selectLatestBleepDataBuilder(latestbleep)
    
    def selectLatestBleepSummaryDataAll(self):
        latestbleep = self.selectLatestBleepAll()
        return self.selectLatestBleepDataBuilder(latestbleep)
    
    def selectBleepInfoDataBuilder(self,bleepinfo:Dict):
        #bleepinfo should be a query
        bleepinfo_data = {}
        if bleepinfo:
            bleepinfo_data ={
                "bleepinfo":bleepinfo,
                "uniqueprofanities":self.selectUniqueProfanityWordsByVideo(bleepinfo.get("pvideo_id")),
                "uniqueprofanitiesall":self.selectUniqueProfanityWordsByVideoAll(bleepinfo.get("pvideo_id")),
                "profanitiesall":self.selectProfanitiesOfVideoAll(bleepinfo.get("pvideo_id")),
                "uniqueprofanitycount":self.countUniqueProfanityWordsByBleepedVideo(bleepinfo.get("pvideo_id")).get("count"),
                "profanitycount":self.countProfanityWordsByBleepedVideo(bleepinfo.get("pvideo_id")).get("count"),
                "mostfrequentword":self.selectMostFrequentProfanityWordByVideo(bleepinfo.get("pvideo_id")).get("word"),
                "top10profanities":self.selectTop10ProfanitiesByVideo(bleepinfo.get("pvideo_id")),
                "uploadedby":bleepinfo.get("uploadedby")
            }
        return bleepinfo_data

    def selectBleepedVideoFullInfoById(self,id:str,pvid:str):
        bleepinfo = self.selectBleepedVideosByAccountAndPvid(id,pvid)
        return self.selectBleepInfoDataBuilder(bleepinfo)

    def selectBleepedVideoFullInfo(self,pvid:str):
        bleepinfo = self.selectBleepedVideoByPvid(pvid)
        return self.selectBleepInfoDataBuilder(bleepinfo)

    def selectUniqueProfanityWordsByVideo(self,pvid:str):
        return self.querySelectAll("call sp_select_unique_profanitywords_of_video(%s)",pvid)
    
    def selectUniqueProfanityWordsByVideoAll(self,pvid:str):
        return self.querySelectAll("call sp_select_unique_profanitywords_of_video_All(%s)",pvid)

    def selectMostFrequentProfanityWordByVideo(self,pvid:str):
        return self.querySelect("call sp_select_most_frequent_profanity_word_of_video(%s)",pvid)
    
    def selectProfanitiesOfVideo(self,pvid:str):
        return self.querySelectAll("call sp_select_profanitywords_of_video(%s)",pvid)
    
    def selectProfanitiesOfVideoAll(self,pvid:str):
        return self.querySelectAll("call sp_select_profanitywords_of_video_all(%s)",pvid)

    def selectUniqueProfanityWordsByAccount(self,id:str):
        return self.querySelectAll("call sp_select_unique_profanitywords_by_account(%s)",id)
    
    def selectBleepedVideosByAccount(self,id:str):
        return self.querySelectAll("call sp_select_censored_videos_by_account(%s)",id)

    def selectBleepedVideosByAccountAndPvid(self,id:str,pvid:str):
        return self.querySelect("call sp_select_censored_videos_by_acc_pvid(%s,%s)",id,pvid)
    
    def selectBleepedVideosAll(self):
        return self.querySelectAll("call sp_select_censored_videos_all()")

    def selectBleepedVideoByPvid(self,pvid):
        return self.querySelect("call sp_select_censored_videos_by_pvid(%s)",pvid)

    def selectVideosUploadedByAccount(self,id:str):
        return self.querySelectAll("call sp_select_videos_uploadedby_account(%s)",id)

    def selectVideoByAccountAndVidId(self,id:str,vidid:str):
        return self.querySelect("call sp_select_videos_by_account_vid_id(%s,%s)",id,vidid)
    
    def selectVideoByUniqueFilename(self,uniquefilename):
        return self.querySelect("call sp_select_video_by_uniquefilename(%s)",uniquefilename)
    
    def selectVideoByVidId(self,vid_id):
        return self.querySelect("call sp_select_video_by_id(%s)",vid_id)

    def selectVideosAll(self):
        return self.querySelectAll("call sp_select_videos_all()")
    
    def selectBleepSounds(self):
        return self.querySelectAll("call sp_select_bleep_sounds_all()")
    
    def selectBleepSoundById(self, bleepsoundid):
        return self.querySelect("call sp_select_bleep_sound_by_bleepid(%s)",bleepsoundid)
    
    def selectBleepVideoByFileName(self,pfilename):
        return self.querySelect("call sp_select_pvideo_by_filename(%s)",pfilename)
    
    def selectTop10ProfanitiesByVideo(self,pvid):
        return self.querySelectAll("call sp_select_top_10_profanities_by_video(%s)",pvid)
    
    def selectTop10ProfanitiesAll(self):
        return self.querySelectAll("call sp_select_top_10_profanities_all()")

    def selectNavOfRole(self,role_id):
        return self.querySelectAll("call sp_select_navs_of_role(%s)",role_id)
    
    def selectAccRole(self,id):
        return self.querySelect("call sp_select_account_role(%s)",id)
    
    def selectAdminFeeds(self):
        feeds = []
        stmts = [
            (str(self.countVideos().get("count")),"Overall Uploaded Videos","info","video-camera","/videos"),
            (str(self.countBleepVideos().get("count")),"Overall Bleeped Videos","olive","soundcloud","/bleepedvideos"),
            (str(self.countProfanityWords().get("count")),"Overall Profanities Collected","maroon","comments-o","/profanities"),
            (str(self.countUniqueProfanityWords().get("count")),"Overall Unique Profanities","purple","commenting-o","/uniqueprofanities")
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

    def selectRoles(self):
        return self.querySelectAll("call sp_select_roles()")
    
    def selectAccountCountsByRole(self):
        feeds = []
        icons = ["user-secret","user-circle-o","user","users"]
        bgcolors =["info","olive","success","purple"]
        stmts = []
        for role in self.selectRoles():
            stmts.append([str(self.countAccountByRoles(role.get("name")).get("count")), role.get("name")])
        
        #add total
        stmts.append([str(self.countAccounts().get("count")),"Total"])
        
        i = 0
        for stmt in stmts:
            feed = {
                "count":stmt[0],
                "title":stmt[1].title(),
                "bgcolor":bgcolors[i],
                "icon":icons[i]
            }
            i+=1
            feeds.append(feed)
        
        return feeds

    def selectLatestUsers(self):
        return self.querySelectAll("call sp_select_latest_users()")
    
    def selectAccountRegTrend(self):
        return self.querySelectAll("call sp_select_trend_account_reg()")
    
    def selectUploadVideoTrend(self):
        return self.querySelectAll("call sp_select_trend_upload_video()")
    
    def selectBleepVideoTrend(self):
        return self.querySelectAll("call sp_select_trend_bleep_video()")
    
    def selectTrendFeed(self):
        dates = []
        registration = []
        videouploads = []
        bleepvideos = []

        for items in self.selectAccountRegTrend():
            registration.append(items.get("count"))
            dates.append(items.get("date"))

        for items in self.selectUploadVideoTrend():
            videouploads.append(items.get("count"))
        
        for items in self.selectBleepVideoTrend():
            bleepvideos.append(items.get("count"))
        
        trends = [
            {"Registration ": registration},
            {"Video Uploads ": videouploads},
            {"Bleep Video ": bleepvideos},
        ]

        
        feeds = {
            "trends":trends,
            "dates":dates
        }

        return feeds

    def selectAccountsAll(self):
        return self.querySelectAll("call sp_select_accounts_all()")
    
    def selectAccountsAllLimitOffset(self,limit,offset):
        return self.querySelectAll("call sp_select_accounts_all_limit_offset(%s,%s)",limit,offset)
    
    def selectAccountAllSearchLimitOffset(self,search,limit,offset):
        return self.querySelectAll("call sp_select_accounts_all_search_limit_offset(%s,%s,%s)",search,limit,offset)
    #================================================== Counts
    def countVideosUploadedByAcc(self,id:str):
        return self.querySelect("call sp_count_videos_uploadedby_account(%s)",id)
    
    def countBleepVideosUploadedByAcc(self,id:str):
        return self.querySelect("call sp_count_censored_videos_by_accounts(%s)",id)
    
    def countProfanityWordsByAcc(self,id:str):
        return self.querySelect("call sp_count_profanitywords_collected_by_account(%s)",id)
    
    def countUniqueProfanityWordsByAcc(self,id:str):
        return self.querySelect("call sp_count_unique_profanitywords_collected_by_account(%s)",id)

    def countProfanityWordsByBleepedVideo(self,pvid_id:str):
        return self.querySelect("call sp_count_profanitywords_collected_by_video(%s)",pvid_id)

    def countUniqueProfanityWordsByBleepedVideo(self,id:str):
        return self.querySelect("call sp_count_unique_profanitywords_collected_by_video(%s)",id)

    def countVideos(self):
        return self.querySelect("call sp_count_videos()")
    
    def countBleepVideos(self):
        return self.querySelect("call sp_count_censored_videos()")
    
    def countProfanityWords(self):
        return self.querySelect("call sp_count_profanitywords_collected()")
    
    def countUniqueProfanityWords(self):
        return self.querySelect("call sp_count_unique_profanitywords_collected()")
    
    def countAccountByRoles(self,role):
        return self.querySelect("call sp_count_accounts_by_roles(%s)",role)

    def countAccounts(self):
        return self.querySelect("call sp_count_accounts()")
    
    def countAccountsSearch(self,search):
        return self.querySelect("call sp_count_accounts_search(%s)",search)
    
    #================================================== Inserts
    def insertRole(self,rolename):
        return self.queryInsert("call sp_add_roles(%s)",rolename)
    
    def insertVideo(self,filename,uniquefilename,filelocation,savedirectory):
        return self.queryInsert("call sp_add_video(%s, %s, %s, %s)",filename,uniquefilename,filelocation,savedirectory)
    
    def insertUploadedBy(self,vidid,id):
        return self.queryInsert("call sp_add_uploadedby(%s, %s)",vidid,id)

    def insertBleepedVideo(self,vid_id,bleepsound_id,pfilename,pfilelocation,psavedirectory):
        return self.queryInsert("call sp_add_profanityvideo(%s,%s, %s, %s, %s)",vid_id,bleepsound_id,pfilename,pfilelocation,psavedirectory)
    
    def insertProfanities(self,vals:list):
        return self.queryInsertMany("call sp_add_profanityword(%s, %s,%s,%s)",vals)
    
    def insertUser(self,email:str,fname:str,lname:str,pwd):
        return self.queryInsert("call sp_add_user(%s, %s, %s, %s)",email,fname,lname,pwd)
    
    def insertAccount(self,email,fname,lname,pwd,role_id):
        return self.queryInsert("call sp_add_account(%s,%s,%s,%s,%s)",email,fname,lname,pwd,role_id)
    
    #================================================== Update
    def updateAccFname(self,email,fname):
        return self.queryUpdate("call sp_update_account_fname(%s,%s)",email,fname)
    
    def updateAccLname(self,email,lname):
        return self.queryUpdate("call sp_update_account_lname(%s,%s)",email,lname)

    def updateAccPwd(self,email,pwd):
        return self.queryUpdate("call sp_update_account_pwd(%s,%s)",email,pwd)
    
    def updateAccEmail(self,oldemail,newemail):
        return self.queryUpdate("call sp_update_account_email(%s,%s)",oldemail,newemail)
    
    def updateAccPhoto(self,email,photo):
        return self.queryUpdate("call sp_update_account_photo(%s,%s)",email,photo)
    
    def updateAccFnameById(self,id,fname):
        return self.queryUpdate("call sp_update_account_fname_by_id(%s,%s)",id,fname)

    def updateAccLnameById(self,id,lname):
        return self.queryUpdate("call sp_update_account_lname_by_id(%s,%s)",id,lname)  

    def updateAccRoleIdById(self,id,role_id):
        return self.queryUpdate("call sp_update_account_role_id_by_id(%s,%s)",id,role_id)       
    
    #================================================== Delete
    def deleteAccById(self,id):
        return self.queryDelete("call sp_delete_account_by_id(%s)",id)
    
    def deleteUploadedById(self,id):
        return self.queryDelete("call sp_delete_uploadedby_id(%s)",id)
    
    def deleteVideoByVidId(self,vid_id):
        return self.queryDelete("call sp_delete_video_by_vid_id(%s)",vid_id)
    
    def deleteBleepVideoByVidId(self,pvid_id):
        return self.queryDelete("call sp_delete_pvideo_by_pvid_id(%s)",pvid_id)
    
    def deleteProfanityWordsByVidId(self,pvid_id):
        return self.queryDelete("call sp_delete_pword_by_pvid_id(%s)",pvid_id)

    
    
    

        

    









