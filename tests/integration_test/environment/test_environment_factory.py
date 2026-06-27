import yaml
from testcontainers.core.container import Network
from tests.integration_test.environment.etcd.etcd_container_provider import EtcdContainerProvider
from tests.integration_test.environment.mysql.mysql_container_provider import MysqlContainerProvider
from tests.integration_test.environment.mysql_manager.mysql_manager_container_provider import MysqlManagerContainerProvider
from tests.integration_test.environment.proxysql.proxysql_container_provider import ProxysqlContainerProvider
from tests.integration_test.environment.haproxy.haproxy_container_provider import (
    HAProxyContainerProvider
)


class TestEnvironmentFactory:
    def __init__(
        self,
    ) -> None:
        self.mysqls = []
        self.proxysqls = []
        self.mysql_manager = None
        self.etcd = None
        self.haproxys = []
        self.remote = None
        self.network = Network().create()

    def _get_default_mysql_config_template(self):
        return """[mysqld]
server-id = {}
gtid-mode = ON
enforce-gtid-consistency = ON
log-bin = binlog
relay-log = relaylog
datadir = /var/lib/mysql
binlog_expire_logs_seconds = 259200
binlog_expire_logs_auto_purge = ON
max_binlog_size = 104857600
slow_query_log = 1
long_query_time = 1
slow_query_log_file = /var/lib/mysql/slow.log
max_connections = 1000
"""

    def _get_mysql_manager_config(self, remote: dict=None):
        config = {
            "mysqls": {}
        }
        for i, mysql in enumerate(self.mysqls):
            config["mysqls"]["s"+str(i+1)] = {
                "host": mysql.name, 
                "user": mysql.root_username, 
                "password": mysql.root_password
            }
        
        config["users"] = {
            "replPassword": "password",
            "exporterPassword": "exporter",
            "nonprivPassword": "password",
            "nonprivUser": "hamadmin",
        }

        if remote is not None: 
            config["remote"] = remote

        return yaml.safe_dump(config)

    def get_one_up_mysql(self):
        for mysql in self.mysqls:
            if mysql.is_up:
                return mysql

    def get_mysql_by_server_id(self, server_id: int):
        for mysql in self.mysqls:
            if mysql.server_id == server_id:
                return mysql
        raise ValueError(f"No mysql container with server_id {server_id}")

    def setup_mysql(self, mysql: dict, config: str | None = None):
        self.setup_mysql_with_name(mysql, f"mysql-s{mysql['server_id']}", config)

    def setup_mysql_with_name(self, mysql, name: str, config: str | None = None):
        if config is None:
            config = self._get_default_mysql_config_template().format(mysql["server_id"])
        component = MysqlContainerProvider(
            server_id=mysql["server_id"],
            name=name,
            network=self.network,
            image=mysql["image"],
            config=config
        )
        if name == "remote":
            self.remote = component
        else:
            self.mysqls.append(
                component 
            ) 
        
        component.setup()
        component.start()

    def setup_proxysql(self, proxysql):
        component = ProxysqlContainerProvider(
            name=proxysql["name"],
            network=self.network,
            image=proxysql["image"],
            local_username=proxysql["local_username"],
            local_password=proxysql["local_password"],
            remote_username=proxysql["remote_username"],
            remote_password=proxysql["remote_password"],
            config=self._get_default_proxysql_config_template().format(
                proxysql["local_username"], 
                proxysql["local_password"],
                proxysql["remote_username"], 
                proxysql["remote_password"],
            )
        )
        self.proxysqls.append(
            component 
        )
        component.setup()
        component.start()

    def setup_mysql_manager(self, mysql_manager, remote: dict=None):
        self.mysql_manager = MysqlManagerContainerProvider(
            name=mysql_manager["name"],
            network=self.network,
            image=mysql_manager["image"],
            config=self._get_mysql_manager_config(remote)
        )
        self.mysql_manager.set_env(mysql_manager["envs"])
        self.mysql_manager.setup()
        self.mysql_manager.start()
    
    def setup_haproxy(self, haproxy):
        component = HAProxyContainerProvider(
            name=haproxy["name"],
            network=self.network,
            image=haproxy["image"],
        )
        component.set_env(haproxy["envs"])
        self.haproxys.append(component)
        component.setup()
        component.start()
    
    def setup_etcd(self, etcd):
        self.etcd = EtcdContainerProvider(
            name=etcd["name"],
            network=self.network,
            image=etcd["image"],
        )
        self.etcd.setup()
        self.etcd.start()

    def stop(self):
        for mysql in self.mysqls:
            mysql.destroy()
        for haproxy in self.haproxys:
            haproxy.destroy()
        self.mysql_manager.destroy()
        self.etcd.destroy()
        if self.remote is not None:
            self.remote.destroy()
        self.network.remove()

    def stop_mysql(self, server_id: int):
        for mysql in self.mysqls:
            if mysql.server_id == server_id:
                mysql.destroy()
    
    def start_mysql(self, server_id: int):
        for mysql in self.mysqls:
            if mysql.server_id == server_id:
                mysql.setup()
                mysql.start()
    
    def restart_mysql_manager(self, envs):
        self.mysql_manager.destroy()
        self.setup_mysql_manager(
            {
                "name": self.mysql_manager.name, 
                "image": self.mysql_manager.image, 
                "envs": envs,
            }
        )
