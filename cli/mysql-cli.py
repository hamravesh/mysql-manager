import os
from configparser import ConfigParser


import click
import yaml
import logging
import signal

from mysql_manager.etcd import EtcdClient
from mysql_manager.cluster import ClusterManager
from mysql_manager.constants import (
    CLUSTER_STATE_FILE_PATH,
    MINIMUM_FAIL_INTERVAL
)
from mysql_manager.exceptions.exceptions import FailIntervalLessThanMinimumError, ReplicaDatabaseCannotBeFailedOver
from mysql_manager.instance import Mysql
from mysql_manager.cluster_data_handler import ClusterDataHandler
from mysql_manager.proxysql import ProxySQL
from mysql_manager.exceptions import MysqlNodeAlreadyExists, MysqlNodeDoesNotExist, ProgramKilled, SourceDatabaseCannotBeDeleted
from mysql_manager.enums import *

current_dir = os.getcwd()
BASE_DIR = os.path.abspath(os.path.join(current_dir, os.pardir))
etcd_client = EtcdClient()
cluster_data_handler = ClusterDataHandler()
logger = logging.getLogger(__name__)


@click.group()
@click.pass_context
def cli(ctx):
    pass
    # ctx.ensure_object(dict)
    # os.makedirs('/etc/mm', exist_ok=True)
    # ctx.obj['CONFIG'] = read_config_file(DEFAULT_CONFIG_PATH) if DEFAULT_CONFIG_PATH else None


@cli.group()
@click.pass_context
def mysql(ctx):
    pass


@cli.command()
def promote():
    if cluster_data_handler.get_cluster_state() != MysqlClusterState.STANDBY.value:
        logger.error("You can not promote a cluster that is not standby")
        return
    
    cluster_data_handler.update_cluster_state(MysqlClusterState.NEW.value)
        

@cli.command()
@click.option('-f', '--file', help='MySQL cluster spec file', required=False)
@click.option('-s', '--spec', help='MySQL cluster spec', required=False)
@click.option('--standby', is_flag=True, help='Set this flag if you want to replicate from remote server')
def init(file, spec, standby: bool):
    ## TODO: handle inline spec
    ## TODO: validate if remote exists in config
    with open(file, "r") as sf:
        cluster_data = yaml.safe_load(sf.read())
    ## TODO: validate data
    names = list(cluster_data["mysqls"].keys())
    cluster_data["mysqls"][names[0]]["role"] = MysqlRoles.SOURCE.value
    if len(names) == 2:
        cluster_data["mysqls"][names[1]]["role"] = MysqlRoles.REPLICA.value

    if standby:
        cluster_data["remote"]["role"] = MysqlRoles.SOURCE.value
        cluster_data["status"] = {
            "state": MysqlClusterState.STANDBY.value  
        }
    else:
        cluster_data["status"] = {
            "state": MysqlClusterState.NEW.value  
        }
    cluster_data_handler.write_cluster_data_dict(cluster_data)

@cli.command()
@click.argument("fail_interval", type=int)
def set_fail_interval(fail_interval):
    try:
        cluster_data_handler.set_fail_interval(fail_interval)
    except FailIntervalLessThanMinimumError:
        print(f"The value of fail_interval could not be less than {MINIMUM_FAIL_INTERVAL}")

@cli.command()
@click.option('-n', '--name', help='Name for MySQL', required=True)
def request_failover(name):
    try:
        cluster_data_handler.set_request_failover(name)
    except MysqlNodeDoesNotExist:
        print(f"{name} mysql is not in database cluster.")
    except ReplicaDatabaseCannotBeFailedOver:
        print(f"{name} is not source database, for failover please set source database name.")

@cli.command()
@click.option('-h', '--host', help='MySQL host', required=True)
@click.option('-u', '--user', help='Username for MySQL', default='root')
@click.option('-p', '--password', help='Password for MySQL', required=True)
@click.option('-n', '--name', help='Name for MySQL', required=True)
@click.option('--port', help='Port for MySQL', type=int, default=3306)
def add(host, user, password, name, port):
    try:
        cluster_data_handler.add_mysql(
            name=name,
            mysql_data={
                "host": host,
                "user": user,
                "password": password,
                "role": MysqlRoles.REPLICA.value,
            }
        )
    except MysqlNodeAlreadyExists:
        print(f"mysql server with name: {name} can not be added because it already exists.")

@cli.command()
@click.option('-n', '--name', help='Name for MySQL', required=True)
def remove(name):
    try:
        cluster_data_handler.remove_mysql(
            name=name,
        )
    except MysqlNodeDoesNotExist:
        print(f"{name} mysql is not in database cluster.")
    except SourceDatabaseCannotBeDeleted:
        print(f"{name} mysql can not be removed because it is source database.")

@mysql.command()
def get_cluster_status():
    # state = etcd_client.read_status()
    with open(CLUSTER_STATE_FILE_PATH, "r") as sf:
        state = yaml.safe_load(sf)

    print("source="+state.get("source"))
    print("replica="+state.get("replica"))


def signal_handler(signum, frame):
    raise ProgramKilled()


@mysql.command()
def run():
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    # create_config_file_from_env(nodes_count=nodes)
    print("Starting cluster manager...")
    try:
        clm = ClusterManager()
        clm.run()
    except ProgramKilled:
        print("Received termination signal. Exiting...")


if __name__ == '__main__':
    cli()
