import mysql.connector

class model:
    def __init__(self):
        self.__host ="localhost"
        self.__user ="root"
        self.__password =""
        self.__database ="bleepyserverprototype"
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
    
    @property
    def conn(self):
        return self.__conn
    
    @property
    def cur(self):
        return self.conn.cursor(dictionary=True)
    
    def querySelect(self,sql,vals):
        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,vals)

                result = cur.fetchall()
        
                self.conn.close()
                return result
            except Exception as e:
                return e
        return False

    def querySelectAll(self,sql,*args):
        if(self.initConn()):
            try:
                cur = self.cur
                cur.execute(sql,args)

                result = cur.fetchall()
        
                self.conn.close()
                return result
            except Exception as e:
                return e
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
        return self.querySelect("Select * from accounts")
    
    #================================================== Inserts
    def insertRole(self,rolename):
        return self.queryInsert("call sp_add_roles(%s)",rolename)
    
    
    

            
        
    
    
    

        

    









