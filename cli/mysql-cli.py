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
from mysql_manager.exceptions.exceptions import FailIntervalLessThanMinimumError
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



@cli.command()
@click.option('--repl', 'repl_pwd', help='New replication user password')
@click.option('--exporter', 'exporter_pwd', help='New exporter user password')
@click.option('--nonpriv', 'nonpriv_pwd', help='New non-privileged user password')
@click.option('--root', 'root_pwd', help='New password for each MySQL node root user')
def rotate_passwords(repl_pwd, exporter_pwd, nonpriv_pwd, root_pwd):
    cd = cluster_data_handler.get_cluster_data()
    src = None
    repl_instance = None
    for name, m in cd.mysqls.items():
        if m.role == MysqlRoles.SOURCE.value:
            src = Mysql(m.host, m.user, m.password, name, m.role, m.port)
        elif m.role == MysqlRoles.REPLICA.value:
            repl_instance = Mysql(m.host, m.user, m.password, name, m.role, m.port)
            
    # first check if replication is fine and can propagate password changes
    if repl_instance:
        repl_status = repl_instance.get_replica_status()
        if repl_status is None:
            print("Error: Replica is not configured for replication. Cannot safely change passwords.")
            return
        if repl_status.get("Replica_IO_Running") != "Yes":
            print("Error: Replica IO thread is not running. Cannot safely change passwords.")
            return
        if repl_status.get("Replica_SQL_Running") != "Yes":
            print("Error: Replica SQL thread is not running. Cannot safely change passwords.")
            return
        if int(repl_status.get("Seconds_Behind_Source")) >=  60:
            print("Error: Replica is lagging behind source. Cannot safely change passwords.")
            return
        print("Replication is healthy. Proceeding with password change.")
        

    if repl_pwd:
        if not _validate_password(repl_pwd, "Replication"):
            return
        cd.users['replPassword'] = repl_pwd
        if src:
            try:
                src.change_user_password('replica', repl_pwd)
                print(f"Changed replication user on source {src.host}")
            except Exception as e:
                print(f"Failed to alter replication user on source: {e}")
        # we need to restart replication to use new password
        if repl_instance:
            try:
                repl_instance.run_command("STOP REPLICA")
                repl_instance.run_command(f"CHANGE REPLICATION SOURCE TO SOURCE_PASSWORD='{repl_pwd}'")
                repl_instance.run_command("START REPLICA")
                print(f"Updated replica configuration on {repl_instance.host}")
                
            except Exception as e:
                print(f"Failed to update replica configuration: {e}")

    if exporter_pwd:
        if not _validate_password(exporter_pwd, "Exporter"):
            return
        cd.users['exporterPassword'] = exporter_pwd
        if src:
            try:
                src.change_user_password('exporter', exporter_pwd)
                print(f"Changed exporter user on source {src.host}")
            except Exception as e:
                print(f"Failed to alter exporter user on source: {e}")

    if nonpriv_pwd:
        if not _validate_password(nonpriv_pwd, "Non-privileged"):
            return
        cd.users['nonprivPassword'] = nonpriv_pwd
        nonpriv_user = cd.users.get('nonprivUser')
        if nonpriv_user and src:
            try:
                src.change_user_password(nonpriv_user, nonpriv_pwd)
                print(f"Changed nonpriv user '{nonpriv_user}' on source {src.host}")
            except Exception as e:
                print(f"Failed to alter nonpriv user on source: {e}")

    if root_pwd:
        if not _validate_password(root_pwd, "Root"):
            return
        
        if src:
            try:
                src.change_user_password(src.user, root_pwd)
                src.password = root_pwd
                cd.mysqls[src.name].password = root_pwd
                print(f"Changed root user '{src.user}' on master {src.host}")
            except Exception as e:
                print(f"Failed to change root user on master {src.host}: {e}")
                return
        
        if repl_instance:
            repl_instance.password = root_pwd
            cd.mysqls[repl_instance.name].password = root_pwd
            print(f"Updated replica instance password for {repl_instance.host}")
            

    cluster_data_handler.write_cluster_data(cd)

    print("Password rotation completed")
    print("WARNING: please restart MySQL manager to force it to use new passwords!")

    
    

def _validate_password(password, password_type):
    if password and len(password) > 32:
        print(f"Error: {password_type} password exceeds 32 character limit (length: {len(password)})")
        return False
    return True


if __name__ == '__main__':
    cli()
