from configparser import ConfigParser
import time 

from mysql_manager.instance import MysqlInstance
from mysql_manager.proxysql import ProxySQL
from mysql_manager.enums import (
    MysqlReplicationProblem,
    MysqlStatus,
)
from mysql_manager.constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_DATABASE,
)

class ClusterManager: 
    def __init__(self, config_file: str=DEFAULT_CONFIG_PATH):
        self.src: MysqlInstance = None
        self.repl: MysqlInstance = None
        self.proxysqls: list[ProxySQL] = [] 
        self.users: dict = {} 
        self.config_file = config_file
        self.read_config_file()

    def _log(self, msg) -> None:
        print(msg)
        
    def read_config_file(self):
        config = ConfigParser()
        config.read(self.config_file)

        self.src = MysqlInstance(**config["mysql-s1"])
        self.users = config["users"]
        self.proxysqls.append(
            ProxySQL(
                **config["proxysql-1"], 
                mysql_user=self.users["nonpriv_user"],
                mysql_password=self.users["nonpriv_password"],
                monitor_user="proxysql",
                monitor_password=self.users["proxysql_mon_password"]),
            )
        
        if config.has_section("mysql-s2"): 
            self.repl = MysqlInstance(**config["mysql-s2"])

    def get_cluster_status(self) -> dict: 
        cluster_status = {
            "master": MysqlStatus.UP.value,
            "replica": MysqlStatus.UP.value,
        }

        try: 
            self.src.ping()
        except Exception: 
            cluster_status["master"] = MysqlStatus.DOWN.value

        try:
            self.repl.ping()
            problems = self.repl.find_replication_problems()
            if ( 
                MysqlReplicationProblem.SQL_THREAD_NOT_RUNNING.value in problems 
                or MysqlReplicationProblem.IO_THREAD_NOT_RUNNING.value in problems
            ):
                cluster_status["replica"] = MysqlStatus.DOWN.value
        except:
            cluster_status["replica"] = MysqlStatus.DOWN.value
        
        return cluster_status

    def start_mysql_replication(self):
        ## TODO: reset replication all for both of them 
        self.src.add_replica(self.repl)
        self.repl.set_master(self.src)
        self.repl.start_replication("replica", self.users["repl_password"])
    
    def check_servers_up(self): 
        self.src.ping()
        if self.repl is not None:
            self.repl.ping()
        self.proxysqls[0].ping()

    def start(self):
        self.check_servers_up()
        
        self.src.add_pitr_event(15)
        self.src.create_new_user(
            "replica", self.users["repl_password"], ["REPLICATION SLAVE"]
        )
        self.src.create_database(DEFAULT_DATABASE)
        self.src.create_monitoring_user(self.users["exporter_password"])
        self.src.create_nonpriv_user(self.users["nonpriv_user"], self.users["nonpriv_password"])
        self.src.create_new_user("proxysql", self.users["proxysql_mon_password"], ["USAGE", "REPLICATION CLIENT"])

        

        self.proxysqls[0].initialize_setup()
        self.proxysqls[0].add_backend(self.src, 1, True)
        
        if self.repl is not None: 
            self.start_mysql_replication()
            time.sleep(5)
            self.proxysqls[0].add_backend(self.repl, 1, False)
