import os
from configparser import ConfigParser


import click
import yaml
import logging
import signal

from mysql_manager.etcd import EtcdClient
from mysql_manager.cluster import ClusterManager
from mysql_manager.constants import (
    DEFAULT_CONFIG_PATH,
    CLUSTER_STATE_FILE_PATH,
)
from mysql_manager.instance import Mysql
from mysql_manager.cluster_data_handler import ClusterDataHandler
from mysql_manager.proxysql import ProxySQL
from mysql_manager.exceptions import ProgramKilled, MysqlNodeAlreadyExists
from mysql_manager.enums import *

current_dir = os.getcwd()
BASE_DIR = os.path.abspath(os.path.join(current_dir, os.pardir))
etcd_client = EtcdClient()
cluster_data_handler = ClusterDataHandler()
logger = logging.getLogger(__name__)

def read_config_file(config_file):
    config = ConfigParser()
    config.read(config_file)
    return config


def get_option_or_config(option, config, section, key, default=None):
    if option:
        return option
    if config and config.has_option(section, key):
        return config.get(section, key)
    if default:
        return default
    raise click.BadParameter(f'Missing required parameter: {key}')


def get_instance_from_config(config, name):
    return {
        'host': config.get(name, 'host'),
        'user': config.get(name, 'user'),
        'password': config.get(name, 'password'),
        'port': int(config.get(name, 'port'))
    }


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


@mysql.command()
def get_cluster_status():
    # state = etcd_client.read_status()
    with open(CLUSTER_STATE_FILE_PATH, "r") as sf:
        state = yaml.safe_load(sf)

    print("source="+state.get("source"))
    print("replica="+state.get("replica"))


@mysql.command()
@click.option('-n', '--name', help='MySQL name', required=True)
@click.option('-h', '--host', help='MySQL host', required=True)
@click.option('-u', '--user', help='Username for MySQL', default='root')
@click.option('-p', '--password', help='Password for MySQL', required=True)
@click.option('--port', help='Port for MySQL', type=int, default=3306)
@click.pass_context
def add(ctx, name, host, user, password, port):
    config = ConfigParser()
    config.read(DEFAULT_CONFIG_PATH)

    if not config.has_section(name):
        config.add_section(name)

    config.set(name, 'host', host)
    config.set(name, 'user', user)
    config.set(name, 'password', password)
    config.set(name, 'port', str(port))

    with open(DEFAULT_CONFIG_PATH, 'w') as configfile:
        config.write(configfile)



@mysql.command()
@click.option('-n', '--name', help='MySQL name')
@click.option('-u', '--user', help='Username for new user')
@click.option('-p', '--password', help='Password for new user')
@click.option('--roles', help='Comma-separated roles for the new user')
@click.pass_context
def create_user(ctx, name, user, password, roles):
    config = ctx.obj['CONFIG']

    print(f"Creating user '{user}' with roles {roles.split(',')} on mysql '{name}'")
    ins = Mysql(**get_instance_from_config(config, name))
    ins.create_new_user(user, password, roles.split(','))


def create_config_file_from_env(nodes_count: int):
    filename = "/etc/mm/config.ini"
    # if os.path.isfile(filename):
    #     return
    
    config = ConfigParser()
    config.add_section("mysql-s1")
    config.set("mysql-s1", "host", os.getenv("MYSQL_S1_HOST"))
    config.set("mysql-s1", "user", "root")
    config.set("mysql-s1", "password", os.getenv("MYSQL_ROOT_PASSWORD"))
    if nodes_count == 2:
        config.add_section("mysql-s2")
        config.set("mysql-s2", "host", os.getenv("MYSQL_S2_HOST"))
        config.set("mysql-s2", "user", "root")
        config.set("mysql-s2", "password", os.getenv("MYSQL_ROOT_PASSWORD"))
    
    config.add_section("proxysql-1")
    config.set("proxysql-1", "host", os.getenv("PROXYSQL_HOST"))
    config.set("proxysql-1", "user", "radmin")
    config.set("proxysql-1", "password", os.getenv("PROXYSQL_PASSWORD"))

    config.add_section("users")
    config.set("users", "repl_password", os.getenv("MYSQL_REPL_PASSWORD"))
    config.set("users", "exporter_password", os.getenv("MYSQL_EXPORTER_PASSWORD"))
    config.set("users", "proxysql_mon_password", os.getenv("PROXYSQL_MON_PASSWORD"))
    config.set("users", "nonpriv_user", os.getenv("MYSQL_NONPRIV_USER"))
    config.set("users", "nonpriv_password", os.getenv("MYSQL_NONPRIV_PASSWORD"))

    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w") as configfile:
        config.write(configfile)


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

@cli.group()
@click.pass_context
def proxysql(ctx):
    pass


@proxysql.command()
@click.option('-n', '--name', help='MySQL name', required=True)
@click.option('-h', '--host', help='MySQL host', required=True)
@click.option('-u', '--user', help='Username for MySQL', default='root')
@click.option('-p', '--password', help='Password for MySQL', required=True)
@click.option('--port', help='Port for MySQL', type=int, default=6032)
@click.pass_context
def add(ctx, name, host, user, password, port):
    config = ConfigParser()
    config.read(DEFAULT_CONFIG_PATH)

    if not config.has_section(name):
        config.add_section(name)

    config.set(name, 'host', host)
    config.set(name, 'user', user)
    config.set(name, 'password', password)
    config.set(name, 'port', str(port))

    with open(DEFAULT_CONFIG_PATH, 'w') as configfile:
        config.write(configfile)


@proxysql.command()
@click.option('-n', '--name', help='ProxySQL name')
@click.option('--mysql-user', help='MySQL username')
@click.option('--mysql-password', help='MySQL password')
@click.option('--monitor-user', help='Monitor username')
@click.option('--monitor-password', help='Monitor password')
@click.pass_context
def initialize(ctx, name, mysql_user, mysql_password, monitor_user, monitor_password):
    config = ctx.obj['CONFIG']

    proxysql_ins = get_instance_from_config(config, name)
    proxysql_ins.pop('port')

    print(f"Initializing ProxySQL on proxysql '{name}'")
    px = ProxySQL(
        **proxysql_ins,
        mysql_user=mysql_user,
        mysql_password=mysql_password,
        monitor_user=monitor_user,
        monitor_password=monitor_password,
    )
    px.initialize_setup()


@proxysql.command()
@click.option('--mysql-name', help='MySql name')
@click.option('--proxysql-name', help='MySql name')
@click.option('--read-weight', help='Read weight')
@click.option('--is-writer', is_flag=True, help='Specify if the backend is a writer')
@click.pass_context
def add_backend(ctx, mysql_name, proxysql_name, read_weight, is_writer):
    config = ctx.obj['CONFIG']

    role = 'writer' if is_writer else 'reader'
    print(f"Adding {role} backend to ProxySQL on {proxysql_name}'")

    mysql_ins = get_instance_from_config(config, mysql_name)
    mysql_instance = Mysql(**mysql_ins)
    proxysql_ins = get_instance_from_config(config, proxysql_name)
    proxysql_ins.pop('port')
    px = ProxySQL(
        **proxysql_ins,
        mysql_user=mysql_ins.get('user'),
        mysql_password=mysql_ins.get('password'),
        monitor_user='',
        monitor_password='',
    )
    px.add_backend(mysql_instance, read_weight, is_writer)

if __name__ == '__main__':
    cli()
