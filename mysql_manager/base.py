import pymysql
import datetime
from mysql_manager.exceptions import MysqlConnectionException

class BaseServer: 
    def __init__(self, host: str, user: str, password: str, port: int=3306) -> None:
        self.host = host 
        self.port = port
        self.user = user
        self.password = password
    
    def _log(self, msg) -> None:
        print(str(datetime.datetime.now()) + "  " + "[" + self.host + "] " + msg)
    
    # TODO: use single connection
    def _get_db(self):
        db = None 
        try:
            db = pymysql.Connection(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                cursorclass=pymysql.cursors.DictCursor,
            )
        except Exception as e: 
            self._log(str(e))
            return None
        return db 

    def fetch(self, query: str, args: list) -> dict:
        db = self._get_db()
        if db is None:
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()

        result = None
        with db:
            with db.cursor() as cursor:
                try:
                    cursor.execute(query, args=args)
                    result = cursor.fetchall()
                except Exception as e:
                    self._log(str(e))
                    raise e
        return result

    def run_command(self, command: str) -> dict: 
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        result = None 
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(command)
                    result = cursor.fetchone()
                except Exception as e:
                    self._log(str(e)) 
                    raise e
                
        return result
        
    def ping(self) -> bool:
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to server")
            raise MysqlConnectionException()
        
        with db:
            try: 
                db.ping(reconnect=True)
            except Exception as e: 
                self._log(str(e))
                raise e 
        return True 

