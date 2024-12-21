import textwrap

import pymysql
from mysql_manager.enums import (
    MysqlConfigProblem,
    MysqlReplicationProblem,
    MysqlStatus,
)
from helpers.query_builder import QueryBuilder
from mysql_manager.dto import MysqlPlugin
from mysql_manager.exceptions import MysqlConnectionException, MysqlReplicationException, MysqlAddPITREventException
from mysql_manager.base import BaseServer
from mysql_manager.constants import DEFAULT_DATABASE

class Mysql(BaseServer):
    def __init__(self, host: str, user: str, password: str, name: str, role: str, port: int=3306) -> None: 
        self.host = host 
        self.port = port
        self.user = user
        self.password = password
        self.name = name
        self.role = role
        self.health_check_failures: int = 0
        self.status: MysqlStatus = MysqlStatus.UP.value 
        self.replicas: list[Mysql] = []
        self.source: Mysql = None
        
        # self.uptime = -1
        # self.server_id: int = -1 
        # self.server_uuid: int = -1 
        # self.is_readonly: bool = False
        # self.is_binlog_enabled: bool = True
        # self.binlog_format: str = "row" 
        # self.binlog_row_image: str = "full"
        # self.is_replica: bool = False 
        # self.is_replica_sql_running: bool = False 
        # self.is_replica_io_running: bool = False
        # self.using_gtid: bool = False
        # self.read_binlog_coordinates = None
        # self.exec_binlog_coordinates = None
        # self.seconds_behind_master: int = 0 
        # self.executed_gtid_set: str = "" 
    
    def user_exists(self, user: str) -> bool: 
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(f"SHOW GRANTS FOR '{user}'")
                    cursor.fetchone()
                except pymysql.err.OperationalError: 
                    return False
                except Exception as e: 
                    self._log(str(e))
                    raise e
        
        return True
    
    def change_user_password(self, user: str, password: str):
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(f"ALTER USER '{user}'@'%' IDENTIFIED BY '{password}'")
                    cursor.execute(f"ALTER USER '{user}'@'localhost' IDENTIFIED BY '{password}'")
                    cursor.execute("FLUSH PRIVILEGES")
                except Exception as e: 
                    self._log(str(e))
                    raise e

    def create_database(self, name: str): 
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()

        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {name}")
                    cursor.fetchone()
                except Exception as e: 
                    self._log(str(e))
                    raise e
        
    def create_monitoring_user(self, password: str):
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
    
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(
                        f"CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED WITH mysql_native_password BY '{password}' WITH MAX_USER_CONNECTIONS 3"
                    )
                    cursor.execute(
                        "GRANT PROCESS, REPLICATION CLIENT ON *.* TO 'exporter'@'%'"
                    )
                    cursor.execute(
                        "GRANT SELECT ON performance_schema.* TO 'exporter'@'%'"
                    )
                    cursor.execute("FLUSH PRIVILEGES")
                except Exception as e: 
                    self._log(str(e))
                    raise e

    def create_nonpriv_user(self, user: str, password: str): 
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()

        access_commands = [
            f"GRANT ALL ON *.* TO `{user}`@`%` WITH GRANT OPTION",
            f"REVOKE REPLICATION_SLAVE_ADMIN, CONNECTION_ADMIN, SUPER ON *.* FROM `{user}`@`%`",
        ]
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(
                        f"CREATE USER IF NOT EXISTS '{user}'@'%' IDENTIFIED WITH mysql_native_password BY '{password}'"
                    )

                    for command in access_commands:
                        cursor.execute(command)
                    cursor.execute("FLUSH PRIVILEGES")
                except Exception as e: 
                    self._log(str(e))
                    raise e

    def create_new_user(self, user: str, password: str, grants: list[str]):
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(
                        f"CREATE USER IF NOT EXISTS '{user}'@'%' IDENTIFIED WITH mysql_native_password BY '{password}'"
                    )
                    grants_command = ",".join(grants)
                    cursor.execute(
                        f"GRANT {grants_command} ON *.* TO '{user}'@'%'"
                    )
                    cursor.execute("FLUSH PRIVILEGES")
                except Exception as e: 
                    self._log(str(e))
                    raise e
    
    def find_config_problems(self) -> list[MysqlConfigProblem]: 
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute('''
select @@global.log_bin, @@global.binlog_format, @@global.gtid_mode, @@global.enforce_gtid_consistency
''')
                    result = cursor.fetchone()
                except Exception as e: 
                    self._log(str(e))
                    raise e
        
        problems = []
        if result["@@global.log_bin"] != 1: 
            problems.append(MysqlConfigProblem.LOGBIN_NOT_ENABLED.value)
        if result["@@global.binlog_format"] != "ROW":
            problems.append(MysqlConfigProblem.LOGBIN_FORMAT.value)
        if result["@@global.gtid_mode"] != "ON": 
            problems.append(MysqlConfigProblem.GTID_NOT_ENABLED.value)
        if result["@@global.enforce_gtid_consistency"] != "ON":
            problems.append(MysqlConfigProblem.GTID_CONSISTENCY_NOT_ENABLED.value)
        
        return problems         

    def is_master_of(self, replica) -> bool:
        status = replica.get_replica_status()
        if status is None:
            return False 
        
        if status["Source_Host"] == self.host:
            return True

        return False 

    def add_replica(self, replica) -> None:
        if replica.is_replica() and not self.is_replica() and self.is_master_of(replica):
            self.replicas.append(replica)

    def get_master_status(self) -> dict:
        return self.run_command("SHOW MASTER STATUS") 

    def get_replica_status(self) -> dict:
        try: 
            return self.run_command("SHOW REPLICA STATUS") 
        except: 
            return None        

    def is_replica(self) -> bool: 
        ## TODO: what if replica is not available?
        return self.get_replica_status() is not None 
    
    def get_gtid_executed(self) -> str: 
        res = self.run_command("select @@global.gtid_executed as gtid")
        return res.get("gtid") 

    def restart_replication(self):
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute("stop replica")
                    cursor.execute("start replica")
                except Exception as e:
                    self._log(str(e)) 
                    raise e
                
    def has_base_gtid_set(self): 
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute("select @@global.server_uuid as uuid")
                    result = cursor.fetchone()
                    uuid = result.get("uuid")

                    cursor.execute("select @@global.gtid_executed as gtid")
                    result = cursor.fetchone()
                    return f"{uuid}:1-6" == result.get("gtid")
                except Exception as e:
                    self._log(str(e)) 
                    raise e

    def get_plugins(
        self, name: str | None = None, status: str | None = None
    ) -> set[MysqlPlugin]:
        """
        Retrieve a list of MySQL plugins with optional filtering by name and status.

        This method constructs a SQL query to fetch plugin information from the
        INFORMATION_SCHEMA.PLUGINS table, with optional conditions for plugin
        name and status. It then executes the query and returns a list of
        MysqlPlugin instances based on the results.

        Args:
            name (str | None): Optional. The name of the plugin to filter by. Default is None.
            status (str | None): Optional. The status of the plugin to filter by. Default is None.

        Returns:
            list[MysqlPlugin]: A list of MysqlPlugin instances representing the plugins
            that match the given filters. If no filters are provided, all plugins are returned.

        Example:
            >>> plugins = mysql.get_plugins(name="example_plugin", status="ACTIVE")
            >>> for plugin in plugins:
            >>>     print(plugin.name, plugin.status, plugin.plugin_type)
        """
        query, args = QueryBuilder.build(
            "SELECT * FROM INFORMATION_SCHEMA.PLUGINS",
            PLUGIN_NAME=name,
            PLUGIN_STATUS=status,
        )

        mysql_plugins = self.fetch(query, args)
        return {
            MysqlPlugin(
                name=_["PLUGIN_NAME"],
                status=_["PLUGIN_STATUS"],
                plugin_type=_["PLUGIN_TYPE"],
            )
            for _ in mysql_plugins
        }

    def install_plugin(self, plugin_name: str, plugin_file: str):
        """
        Installs a MySQL plugin if it is not already installed.

        This method checks if a plugin with the given name is already installed.
        If the plugin is not found, it constructs and runs the SQL command to
        install the plugin using the specified plugin file.

        Args:
            plugin_name (str): The name of the plugin to install.
            plugin_file (str): The name of the shared object file containing the plugin.

        Returns:
            None

        Example:
            >>> mysql.install_plugin("example_plugin", "example_plugin.so")
        """
        plugins = self.get_plugins(name=plugin_name)
        if plugins:
            return
        
        command = f"INSTALL PLUGIN {plugin_name} SONAME '{plugin_file}'"
        self.run_command(command)

    def find_replication_problems(self) -> list[MysqlReplicationProblem]:
        status = self.get_replica_status()
        if status is None: 
            return [MysqlReplicationProblem.NOT_REPLICA.value]
        
        # values of these two can be used in future: 'Replica_IO_State', 'Replica_SQL_Running_State'
        ## TODO: check if keys exist in `status`
        problems = []
        if status["Replica_IO_Running"] != "Yes":
            problems.append(MysqlReplicationProblem.IO_THREAD_NOT_RUNNING.value)
        if status["Replica_SQL_Running"] != "Yes":
            problems.append(MysqlReplicationProblem.SQL_THREAD_NOT_RUNNING.value)
        if status["Last_Errno"] != 0 and status["Last_Error"] != "":
            problems.append(MysqlReplicationProblem.LAST_ERROR.value)
        if status["Last_IO_Errno"] != 0 and status["Last_IO_Error"] != "":
            problems.append(MysqlReplicationProblem.IO_ERROR.value)
        if status["Last_SQL_Errno"] != 0 and status["Last_SQL_Error"] != "":
            problems.append(MysqlReplicationProblem.SQL_ERROR.value)
        if status["Seconds_Behind_Source"] is not None and status["Seconds_Behind_Source"] > 60:
            problems.append(MysqlReplicationProblem.REPLICATION_LAG_HIGH.value)
        if status["Auto_Position"] != 1:
            problems.append(MysqlReplicationProblem.AUTO_POSITION_DISABLED.value)
        
        return problems

    def set_source(self, source):
        if source.is_replica():
            self._log("This server at "+source.host+" is a replica and can not be set as source")
            return
        
        source_cfg_problems = source.find_config_problems()
        if len(source_cfg_problems) != 0:
            self._log("Problem in source at "+source.host+" config: " + str(source_cfg_problems))
            return
        
        self.source = source 
    
    def set_remote_source(self, remote_source): 
        source_cfg_problems = remote_source.find_config_problems()
        if len(source_cfg_problems) != 0:
            self._log("Problem in source at "+remote_source.host+" config: " + str(source_cfg_problems))
            return
        
        self.source = remote_source 

    def _generate_change_master_command(self, repl_user: str, repl_password: str) -> str:
        return f"""
CHANGE REPLICATION SOURCE TO SOURCE_HOST='{self.source.host}', 
    SOURCE_PORT={self.source.port},
    SOURCE_USER='{repl_user}',
    SOURCE_PASSWORD='{repl_password}',
    SOURCE_CONNECT_RETRY = 60,
    SOURCE_RETRY_COUNT = 10,
    SOURCE_AUTO_POSITION = 1; 
"""
    
    def reset_replication(self):
        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute("stop replica")
                    cursor.execute("reset replica all")
                    cursor.execute("set persist read_only=0")
                except Exception as e:
                    self._log(str(e)) 
                    raise e

        self.source = None 

    ## TODO: read orchestrator code 
    ## TODO: check server ids not equal
    def start_replication(self, repl_user: str, repl_password: str): 
        if self.source is None: 
            self._log("No master set for this instance")
            raise MysqlReplicationException()
        
        if not self.source.ping():
            self._log("Master not accesible")
            raise MysqlReplicationException()
        
        cfg_problems = self.find_config_problems()
        if len(cfg_problems) != 0: 
            self._log("Problem in config: " + str(cfg_problems))
            raise MysqlReplicationException()

        repl_status = self.get_replica_status()
        if repl_status is not None and repl_status["Replica_IO_Running"] == "Yes" and repl_status["Replica_SQL_Running"] == "Yes": 
            self._log("Replication is running")
            return

        db = self._get_db()
        if db is None: 
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()
        
        with db: 
            with db.cursor() as cursor:
                try: 
                    cursor.execute(
                        self._generate_change_master_command(repl_user, repl_password)
                    )
                    cursor.execute("SET PERSIST READ_ONLY=1")
                    cursor.execute("START REPLICA")
                except Exception as e:
                    self._log(str(e)) 
                    raise MysqlReplicationException()

    def add_pitr_event(self, minute_intervals: int=15):
        db = self._get_db()
        if db is None:
            self._log("Could not connect to mysql")
            raise MysqlConnectionException()

        with db:
            with db.cursor() as cursor:
                try:
                    cursor.execute("USE mysql;")
                    cursor.execute(
                        f"CREATE EVENT IF NOT EXISTS pitr ON SCHEDULE EVERY {minute_intervals} MINUTE DO FLUSH BINARY LOGS;"
                    )
                except Exception as e:
                    self._log(str(e))
                    raise MysqlAddPITREventException()
