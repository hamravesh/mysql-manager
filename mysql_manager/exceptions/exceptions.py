from mysql_manager.constants import *


class MysqlClusterConfigError(Exception):
    def __init__(self) -> None:
        super().__init__(
            """
            Mysql cluster config is not correct. At least one mysql and one proxysql is needed
            """
        )

class ProgramKilled(Exception):
    def __init__(self) -> None:
        super().__init__("Got signal from OS to stop")

class MysqlConnectionException(Exception): 
    def __init__(self) -> None:
        super().__init__("Could not connect to MySQL")


class MysqlReplicationException(Exception): 
    def __init__(self) -> None:
        super().__init__("Could not start MySQL replication")


class MysqlAddPITREventException(Exception):
    def __init__(self) -> None:
        super().__init__("Could not add PITR Event to Mysql")

class MysqlNodeDoesNotExist(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Could not remove {name} node")

class MysqlNodeAlreadyExists(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Could not add {name} node")

class SourceDatabaseCannotBeDeleted(Exception):
    def __init__(self) -> None:
        super().__init__("Could not remove master database")

class ReplicaDatabaseCannotBeFailedOver(Exception):
    def __init__(self) -> None:
        super().__init__("Could not failover on replica database")

class VariableIsNotSetInDatabase(Exception):
    def __init__(self, variable_name: str) -> None:
        super().__init__(
            f"Variable {variable_name} is not set in database"
        )

class FailIntervalLessThanMinimumError(Exception):
    def __init__(self) -> None:
        super().__init__(
            f"Variable fail_interval could not be less than {MINIMUM_FAIL_INTERVAL}"
        )
