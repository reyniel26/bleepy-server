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
    
    #================================================== Inserts
    def insertRole(self,rolename):
        return self.queryInsert("call sp_add_roles(%s)",rolename)
    
    
    

            
        
    
    
    

        

    









