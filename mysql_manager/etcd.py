from etcd3 import Client
import os
import yaml

class EtcdClient:
    def __init__(self) -> None:
        self.client =  self.create_etcd_client()

    def create_etcd_client(self): 
        etcd_host = os.getenv("ETCD_HOST")
        etcd_port = os.getenv("ETCD_PORT", "2379")
        etcd_username = os.getenv("ETCD_USERNAME")
        etcd_password = os.getenv("ETCD_PASSWORD")
        self.etcd_prefix = os.getenv("ETCD_PREFIX")
        client = Client(
            host=etcd_host, 
            username=etcd_username, 
            password=etcd_password, 
            port=int(etcd_port)
        )
        return client

    def write_cluster_data(self, cluster_data: dict):
        self.write(yaml.safe_dump(cluster_data), path="cluster_data")

    def read_request_failover(self) -> str | None:
        request_failover = self.read(path="request_failover")
        if request_failover is not None:
            return request_failover.decode()

    def write_request_failover(self, source_mysql_name: str) -> None:
        self.write(source_mysql_name, path="request_failover")

    def delete_request_failover(self,) -> None:
        self.delete(path="request_failover")

    def read_cluster_data(self) -> dict: 
        cluster_data = self.read(path="cluster_data")
        if cluster_data is not None:
            return yaml.safe_load(cluster_data.decode())

    def write_spec(self, spec: dict) -> None: 
        self.write(yaml.safe_dump(spec), path="spec")

    def write_status(self, status: dict) -> None: 
        self.write(yaml.safe_dump(status), path="status")

    def read_spec(self) -> dict: 
        spec = self.read(path="spec")
        if spec is not None:
            return yaml.safe_load(spec.decode())
        
    def read_status(self) -> dict: 
        status = self.read(path="status")
        if status is not None: 
            return yaml.safe_load(status.decode())

    def write(self, message: str, path: str) -> None: 
        self.client.auth()
        self.client.put(self.etcd_prefix + path, message)

    def delete(self, path: str) -> None:
        self.client.auth()
        self.client.delete_range(self.etcd_prefix + path)

    def read(self, path: str) -> bytes: 
        self.client.auth()
        values = self.client.range(self.etcd_prefix + path).kvs
        if values is None or len(values) == 0:
            return None
        
        return values[0].value
