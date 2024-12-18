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

class MysqlNodeAlreadyExists(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Could not add {name} node")

class MysqlReplicationException(Exception): 
    def __init__(self) -> None:
        super().__init__("Could not start MySQL replication")


class MysqlAddPITREventException(Exception):
    def __init__(self) -> None:
        super().__init__("Could not add PITR Event to Mysql")
