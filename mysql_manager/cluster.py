import time, datetime, yaml, math
from pymysql.err import OperationalError
from dataclasses import asdict
from prometheus_client import start_http_server

from mysql_manager.helpers.clone_compatibility_checker import CloneCompatibilityChecker
from mysql_manager.instance import Mysql
from mysql_manager.etcd import EtcdClient
from mysql_manager.dto import ClusterData
from mysql_manager.base import BaseServer
# from mysql_manager.proxysql import ProxySQL
from mysql_manager.enums import (
    MysqlReplicationProblem,
    MysqlStatus,
    MysqlClusterState,
    MysqlRoles,
)
from mysql_manager.cluster_data_handler import ClusterDataHandler
from mysql_manager.exceptions import (
    MysqlConnectionException,
    MysqlClusterConfigError,
)
from mysql_manager.constants import *
from mysql_manager.metrics import (
    FAILOVER_ATTEMPTS,
    REPLICATION_RESTARTS,
    CLUSTER_FAILURES,
    MASTER_UP_STATUS,
    REPLICA_UP_STATUS,
)

class ClusterManager: 
    def __init__(self, config_file: str=DEFAULT_CONFIG_PATH):
        self.src: Mysql | None = None
        self.repl: Mysql | None = None
        # self.proxysqls: list[ProxySQL] = [] 
        self.users: dict = {} 
        self.remote: Mysql = None
        self.config_file = config_file
        self.cluster_data_handler = ClusterDataHandler()
        self.etcd_client = EtcdClient()
        self.fail_interval = None
        self.request_failover = None

        # Start Prometheus metrics server on port 8000
        start_http_server(8000)

    @property
    def master_failure_threshold(self) -> int:
        return math.ceil(self.fail_interval / CLUSTER_CHECK_INTERVAL_SECONDS)

    def _log(self, msg) -> None:
        print(str(datetime.datetime.now()) + "  " + msg)

    def _validate_cluster_spec(self, spec: dict):
        if len(spec["mysqls"]) == 0: 
            raise MysqlClusterConfigError()
        
    def _load_cluster_data(self):
        ## TODO: handle mysql servers with ports other than 3306
        self.users = self.cluster_data_handler.get_users()
        self.fail_interval = self.cluster_data_handler.get_fail_interval()
        self.request_failover = self.cluster_data_handler.get_request_failover()
        does_repl_exist = False
        for name, mysql in self.cluster_data_handler.get_mysqls().items():
            if mysql.role == MysqlRoles.SOURCE.value:
                if self.src is None or self.src.name != name: 
                    self.src = Mysql(name=name, **asdict(mysql))
            elif mysql.role ==  MysqlRoles.REPLICA.value:
                does_repl_exist = True
                if self.repl is None or self.repl.name != name:
                    self.repl = Mysql(name=name, **asdict(mysql))
        if not does_repl_exist:
            self.repl = None

        remote_dto = self.cluster_data_handler.get_remote()
        if remote_dto is not None: 
            self.remote = Mysql(name=REMOTE_SOURCE_NAME, **asdict(remote_dto))
        
    def run(self):
        while not self.cluster_data_handler.is_cluster_data_available(): 
            time.sleep(CLUSTER_CHECK_INTERVAL_SECONDS)
            self._log("Cluster data not available. Waiting for it...")

        self._load_cluster_data()

        ## here we assume the remote server is always up because we don't have control over it
        while self.cluster_data_handler.get_cluster_state() == MysqlClusterState.STANDBY.value:
            self._log(f"Cluster is in standby mode. Remote server: {self.remote.host}")
            if self.must_replica_join_source(self.src, self.remote):
                self.join_source_to_remote(retry=10)
            time.sleep(CLUSTER_CHECK_INTERVAL_SECONDS)

        if self.remote is not None: 
            self.src.reset_replication()

        self.start()
        while True: 
            self._log("Checking cluster state...")
            time.sleep(CLUSTER_CHECK_INTERVAL_SECONDS)
            self._load_cluster_data()
            self.reconcile_cluster()

    def must_replica_join_source(self, repl: Mysql|None, src: Mysql) -> bool:
        # in the first two checks, if replica is not available we return True to 
        # prevent useless start replication attempts
        if repl is None:
            return False
        if not self.is_server_up(repl):
            return False

        repl_status = repl.get_replica_status()
        if repl_status is not None and repl_status.get("Source_Host") ==  src.host:
            return False

        return True
    
    def reconcile_cluster(self):
        self._log("Running reconciliation for cluster")

        self.update_cluster_state()
        # self._log(str(self.cluster_status))
        self._set_status_metrics()

        if self.repl is not None:  
            if self.must_replica_join_source(self.repl, self.src): 
                self.join_replica_to_source(retry=10)
            if (
                self.repl.status == MysqlStatus.REPLICATION_THREADS_STOPPED.value
                and self.src.status == MysqlStatus.UP.value
            ):
                self.repl.restart_replication()
                REPLICATION_RESTARTS.inc()
            elif (
                self.src.status == MysqlStatus.DOWN.value
                and self.repl.status == MysqlStatus.DOWN.value
            ):
                CLUSTER_FAILURES.inc()
                self._log("Cluster failure detected: Master and replicas are down.")
            elif (
                # TODO: add more checks for replica: if it was not running sql thread for
                # a long time, if it is behind master for a long time
                self.request_failover is not None or
                (
                    self.src.health_check_failures > self.master_failure_threshold
                    and self.repl.status != MysqlStatus.DOWN.value
                )
            ):
                # Stop failover to occur for second time
                if self.request_failover is not None and self.request_failover != self.src.name:
                    self._log(f"Because source database has changed since last request, failover is not performed.")
                    self.cluster_data_handler.unset_request_failover()
                    return
                self.cluster_data_handler.unset_request_failover()

                self._log("Running failover for cluster")
                FAILOVER_ATTEMPTS.inc()
                ## TODO: what if we restart when running this 
                ## TODO: use etcd txn
                self.cluster_data_handler.set_mysql_role(self.src.name, MysqlRoles.REPLICA.value)
                self.cluster_data_handler.set_mysql_role(self.repl.name, MysqlRoles.SOURCE.value)
                ## TODO: let all relay logs to be applied before resetting replication
                self.repl.reset_replication()
                self.switch_src_and_repl()

        self._log(f"Source is {self.src.host}")
        if self.repl is not None: 
            self._log(f"Replica is {self.repl.host}")

    def _set_status_metrics(self):
        MASTER_UP_STATUS.clear()
        MASTER_UP_STATUS.labels(host=self.src.host).set(
            1 if self.src.status == MysqlStatus.UP.value else 0
        )

        if self.repl is not None: 
            REPLICA_UP_STATUS.clear()
            REPLICA_UP_STATUS.labels(host=self.repl.host).set(
                1 if self.repl.status == MysqlStatus.UP.value else 0
            )

    def switch_src_and_repl(self): 
        self._log(f"Switching src[{self.src.host}] and repl[{self.repl.host}]")
        tmp_src = Mysql(
            self.src.host, 
            self.src.user, 
            self.src.password,
            self.src.name,
            self.src.role,
        )
        self.src = Mysql(
            self.repl.host, 
            self.repl.user, 
            self.repl.password,
            self.repl.name,
            MysqlRoles.SOURCE.value,
        )
        self.repl = Mysql(
            tmp_src.host, 
            tmp_src.user, 
            tmp_src.password,
            tmp_src.name,
            MysqlRoles.REPLICA.value,
        )

    def update_cluster_state(self) -> dict: 
        if self.is_server_up(self.src, retry=1):
            self.src.status = MysqlStatus.UP.value
            self.src.health_check_failures = 0
        else: 
            self.src.status = MysqlStatus.DOWN.value
            self.src.health_check_failures += 1

        if self.repl is not None: 
            if self.is_server_up(self.repl, retry=1):
                self.repl.status = MysqlStatus.UP.value 
                problems = self.repl.find_replication_problems()
                if MysqlReplicationProblem.NOT_REPLICA.value in problems: 
                    self.repl.status = MysqlStatus.NOT_REPLICA.value
                    return
                if ( 
                    MysqlReplicationProblem.SQL_THREAD_NOT_RUNNING.value in problems 
                    or MysqlReplicationProblem.IO_THREAD_NOT_RUNNING.value in problems
                ):
                    self.repl.status = MysqlStatus.REPLICATION_THREADS_STOPPED.value
            else: 
                self.repl.status = MysqlStatus.DOWN.value
        
        self._write_cluster_state()

    def _write_cluster_state(self):
        ## TODO: maybe change this
        with open(CLUSTER_STATE_FILE_PATH, "w") as sf:
            sf.write(yaml.safe_dump(
                {
                    "source": self.src.status,
                    "replica": self.repl.status if self.repl is not None else MysqlStatus.DOWN.value,
                }
            ))

    def start_mysql_replication_from_remote(self):
        ## TODO: reset replication all for both of them 
        self._log(f"Starting replication in {self.src.host} from remote {self.remote.host}")
        self.src.set_remote_source(self.remote)
        ## DOC: remote.user and remote.password must have replication and clone access in remote
        self.src.start_replication(self.remote.user, self.remote.password)

    def start_mysql_replication(self):
        ## TODO: reset replication all for both of them 
        self._log(f"Starting replication in {self.repl.host}")
        self.src.add_replica(self.repl)
        self.repl.set_source(self.src)
        self.repl.start_replication("replica", self.users["replPassword"])
    
    def is_server_up(self, server: BaseServer, retry: int=1) -> bool:
        for i in range(retry):
            try: 
                server.ping()
                return True
            except Exception:
                # do not sleep in last retry
                if i+1 != retry: 
                    time.sleep(RETRY_WAIT_SECONDS)

        return False

    def check_servers_up(self, retry: int=1): 
        # is_ok = False
        for _ in range(retry):
            try: 
                self.src.ping()
                if self.repl is not None:
                    self.repl.ping()
                # self.proxysqls[0].ping()
                return
            except Exception as e:
                time.sleep(RETRY_WAIT_SECONDS)
            # is_ok = True
        
        # if is_ok == False:
        #     raise MysqlConnectionException()

    def config_src_initial_setup(self):
        self._log(f"Initial config of src[{self.src.host}]")
        self.src.add_pitr_event(minute_intervals=15)
        self.src.create_new_user(
            "replica", self.users["replPassword"], ["REPLICATION SLAVE"]
        )
        self.src.create_database(DEFAULT_DATABASE)
        self.src.create_monitoring_user(self.users["exporterPassword"])
        self.src.create_nonpriv_user(self.users["nonprivUser"], self.users["nonprivPassword"])

    def join_source_to_remote(self, retry: int=1):
        ## TODO: check remote server id
        self._log("Joining source to remote")
        
        # TODO: if self.src is in replicating_remote state do not clone remote
        self.src.status = MysqlStatus.CLONING_REMOTE.value
        if self.repl is not None:
            self.repl.status = MysqlStatus.UP.value
        self._write_cluster_state()

        self.src.install_plugin("clone", "mysql_clone.so")
        self.src.run_command(
            f"set persist clone_valid_donor_list='{self.remote.host}:{self.remote.port}'"
        )
        self.src.run_command("set persist read_only=0")

        ## we do not proceed until clone is successful
        while True:
            if not CloneCompatibilityChecker(src=self.src, remote=self.remote).is_clone_possible():
                self._log(f"Cloning is not possible, waiting for {CLONE_COMPATIBILITY_CHECK_INTERVAL_SECONDS} seconds")
                time.sleep(CLONE_COMPATIBILITY_CHECK_INTERVAL_SECONDS)
                continue
            try:
                self._log("Cloning remote server")
                self.src.run_command(
                    f"CLONE INSTANCE FROM '{self.remote.user}'@'{self.remote.host}':{self.remote.port} IDENTIFIED BY '{self.remote.password}'"
                )
            except OperationalError as o:
                self._log(str(o))
                if "Restart server failed (mysqld is not managed by supervisor process)" in str(o):
                    break
                self._log("Failed to clone remote. Trying again...")
                time.sleep(CLUSTER_CHECK_INTERVAL_SECONDS)

        self._log("Waiting for source to become ready")
        src_main_password = self.src.password
        src_main_user = self.src.user
        self.src.password = self.remote.password
        self.src.user = self.remote.user
        if not self.is_server_up(self.src, retry=retry):
            return

        self.src.status = MysqlStatus.REPLICATING_REMOTE.value
        self._write_cluster_state()
        
        if self.src.user_exists(src_main_user):
            self.src.change_user_password(src_main_user, src_main_password)
        else:
            self.src.create_new_user(src_main_user, src_main_password, ["ALL"])

        self.src.password = src_main_password
        self.src.user = src_main_user
        self.start_mysql_replication_from_remote()

    def join_replica_to_source(self, retry: int=1):
        self._log("Joining replica to source")
        # TODO: do not clone if the gtids are in sync
        self.src.install_plugin("clone", "mysql_clone.so")
        self.repl.install_plugin("clone", "mysql_clone.so")

        self.repl.run_command(
            f"set persist clone_valid_donor_list='{self.src.host}:3306'"
        )
        self.repl.run_command("set persist read_only=0")
        try:
            self.repl.run_command(
                f"CLONE INSTANCE FROM '{self.src.user}'@'{self.src.host}':3306 IDENTIFIED BY '{self.src.password}'"
            )
        except OperationalError as o:
            self._log(str(o))

        # TODO: do not continue if this 
        if self.is_server_up(self.repl, retry=retry):
            self.start_mysql_replication()

    def start(self):
        self._log("Starting cluster setup...")
        self.check_servers_up(retry=10)

        self._log("Initializing config of servers...")
        if self.cluster_data_handler.get_cluster_state() == MysqlClusterState.NEW.value:
            self.config_src_initial_setup()
            ## TODO: what if we restart before writing cluster data?
            self.cluster_data_handler.update_cluster_state(MysqlClusterState.CREATED.value)

