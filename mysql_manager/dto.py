from dataclasses import dataclass
from mysql_manager.enums import MysqlClusterState, MysqlRoles


@dataclass
class MysqlData:
    role: MysqlRoles
    host: str 
    user: str 
    password: str
    port: int = 3306


@dataclass
class ClusterStatus:
    state: MysqlClusterState


## TODO: define exact dtos for dicts
@dataclass
class ClusterData:
    mysqls: dict[str: MysqlData]
    remote: MysqlData | None 
    status: ClusterStatus
    users: dict[str: str]

@dataclass
class MysqlPlugin:
    name: str
    status: str
    plugin_type: str

    def __eq__(self, other) -> bool:
        return isinstance(other, MysqlPlugin) and self.name == other.name

    def __hash__(self) -> int:
        return hash(self.name)

