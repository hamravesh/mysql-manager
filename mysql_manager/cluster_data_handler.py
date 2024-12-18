from mysql_manager.dto import (
    MysqlClusterState,
    ClusterStatus,
    MysqlData,
    ClusterData,
)
from mysql_manager.enums import MysqlRoles
from mysql_manager.etcd import EtcdClient
from dataclasses import asdict
from mysql_manager.exceptions import MysqlNodeAlreadyExists


class ClusterDataHandler:
    def __init__(self) -> None:
        self.etcd_client = EtcdClient()

    def validate_cluster_data(self): 
        ## TODO: no more than one source mysqls 
        ## TODO: more than one mysqls
        ## TODO: no more than one replica mysqls
        pass 
    
    def is_cluster_data_available(self):
        cluster_data = self.etcd_client.read_cluster_data()
        return cluster_data is not None

    def write_cluster_data(self, cluster_data: ClusterData):
        self.etcd_client.write_cluster_data(asdict(cluster_data))

    def write_cluster_data_dict(self, cluster_data: dict):
        self.etcd_client.write_cluster_data(cluster_data)

    def get_mysqls(self) -> dict:
        cluster_data = self.get_cluster_data()
        return cluster_data.mysqls
    
    def add_mysql(self, name: str, mysql_data: dict) -> None: 
        cluster_data = self.get_cluster_data()
        if name in cluster_data.mysqls:
            raise MysqlNodeAlreadyExists(name)
        cluster_data.mysqls[name] = MysqlData(**mysql_data)
        self.write_cluster_data(cluster_data)

    def get_users(self) -> dict:
        cluster_data = self.get_cluster_data()
        return cluster_data.users
    
    def get_remote(self) -> MysqlData:
        cluster_data = self.get_cluster_data()
        return cluster_data.remote

    def get_proxysql(self) -> dict:
        cluster_data = self.get_cluster_data()
        return cluster_data.proxysqls[0]
    
    def get_cluster_state(self) -> MysqlClusterState:
        cluster_data = self.get_cluster_data()
        return cluster_data.status.state
    
    def set_mysql_role(self, name: str, role: MysqlRoles): 
        cluster_data = self.get_cluster_data()
        cluster_data.mysqls[name].role = role
        self.write_cluster_data(cluster_data)

    def update_cluster_state(self, state: MysqlClusterState) -> None:
        cluster_data = self.get_cluster_data()
        cluster_data.status.state = state
        self.write_cluster_data(cluster_data)
           
    def get_cluster_data(self) -> ClusterData:
        ## TODO: handle null value of cluster
        cluster_data_dict = self.etcd_client.read_cluster_data()
        mysqls = {}
        for name, mysql in cluster_data_dict["mysqls"].items(): 
            mysqls[name] = MysqlData(**mysql)

        remote_dict = cluster_data_dict.get("remote")
        remote = MysqlData(**remote_dict) if remote_dict is not None else None

        cluster_data = ClusterData(
            mysqls=mysqls,
            proxysqls=cluster_data_dict["proxysqls"],
            users=cluster_data_dict["users"],
            status=ClusterStatus(state=cluster_data_dict["status"]["state"]),
            remote=remote,
        )

        return cluster_data
