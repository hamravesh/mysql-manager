import time
import xmltodict
import logging
from behave import *


logger = logging.getLogger(__name__)

@given('sleep {n:d} seconds')
@when('sleep {n:d} seconds')
@then('sleep {n:d} seconds')
def sleep(context, n):
    time.sleep(n)

@given('setup default proxysql with name: {name:w} and image: {image}')
def start_default_proxysql(context, name, image):
    context.test_env.setup_proxysql(
        {
            "name": name,
            "image": image, 
            "local_username": "admin", 
            "local_password": "pwd", 
            "remote_username": "radmin", 
            "remote_password": "pwd"
        }
    )

@given('setup default mysql with server_id {server_id:d} and name {name}')
def start_mysql_with_name(context, server_id, name):
    context.test_env.setup_mysql_with_name(
        {"server_id": server_id, "image": context.mysql_image},
        name=name,
    )

@given('setup default mysql with config with server_id {server_id:d} and name {name}')
def start_mysql_with_name_and_config(context, server_id, name):
    config = context.text
    context.test_env.setup_mysql_with_name(
        {"server_id": server_id, "image": context.mysql_image},
        name=name,
        config=config
    )

@given('setup default mysql with server_id {server_id:d}')
def start_mysql_with_image(context, server_id):
    context.test_env.setup_mysql(
        {"server_id": server_id, "image": context.mysql_image}
    )

@given('setup mysql with config with server_id {server_id:d}')
def start_mysql_with_config(context, server_id):
    config = context.text
    context.test_env.setup_mysql(
        {"server_id": server_id, "image": context.mysql_image}, config=config
    )

@given('setup mysql_manager with name {name:w} with env ETCD_HOST={etcd_host:w} ETCD_USERNAME={etcd_username:w} ETCD_PASSWORD={etcd_password:w} ETCD_PREFIX={etcd_prefix}')
def start_mysql_manager(context, name, etcd_host, etcd_username, etcd_password, etcd_prefix):
    envs = {
        "ETCD_HOST": etcd_host,
        "ETCD_USERNAME": etcd_username,
        "ETCD_PASSWORD": etcd_password,
        "ETCD_PREFIX": etcd_prefix
    }
    context.test_env.setup_mysql_manager(
        {"name": name, "image": context.mysql_manager_image, "envs": envs}
    )


@given("setup haproxy with name {name} with env ETCD_HOST={etcd_host} ETCD_USERNAME={etcd_username} ETCD_PASSWORD={etcd_password} ETCD_PREFIX={etcd_prefix}")
def start_haproxy(context, name, etcd_host, etcd_username, etcd_password, etcd_prefix):
    envs = {
        "ETCD_HOST": etcd_host,
        "ETCD_USERNAME": etcd_username,
        "ETCD_PASSWORD": etcd_password,
        "ETCD_PREFIX": etcd_prefix
    }
    context.test_env.setup_haproxy(
        {"name": name, "image": context.haproxy_image, "envs": envs}
    )


@given('setup mysql_manager with remote({rhost}, {ruser}, {rpassword}, {rport:d}) with name {name:w} with env ETCD_HOST={etcd_host:w} ETCD_USERNAME={etcd_username:w} ETCD_PASSWORD={etcd_password:w} ETCD_PREFIX={etcd_prefix}')
def start_mysql_manager_with_remote(context, rhost, ruser, rpassword, rport, name, etcd_host, etcd_username, etcd_password, etcd_prefix):
    envs = {
        "ETCD_HOST": etcd_host,
        "ETCD_USERNAME": etcd_username,
        "ETCD_PASSWORD": etcd_password,
        "ETCD_PREFIX": etcd_prefix
    }
    context.test_env.setup_mysql_manager(
        {"name": name, "image": context.mysql_manager_image, "envs": envs},
        remote={
            "host": rhost,
            "user": ruser,
            "password": rpassword,
            "port": rport,
        }
    )

@given('setup etcd with name {name:w} and image: {image}')
def start_etcd(context, name, image):
    context.test_env.setup_etcd(
        {"name": name, "image": image}
    )

@given('setup user root with password: {password} for etcd')
def setup_root_user_for_etcd(context, password):
    context.test_env.etcd.exec(
        f'etcdctl user add root --new-user-password=f"{password}"',
    )
    context.test_env.etcd.exec(
        'etcdctl user grant-role root root'
    )

@given('setup user {name:w} for etcd with password: {password} access to path {path}')
def setup_user_for_etcd(context, name, password, path):
    context.test_env.etcd.exec(
        f'etcdctl user add {name} --new-user-password="{password}"'
    )
    
    context.test_env.etcd.exec(
        f'etcdctl role add {name}'
    )
    
    context.test_env.etcd.exec(
        f'etcdctl role grant-permission {name} --prefix=true readwrite {path}'
    )
    
    context.test_env.etcd.exec(
        f'etcdctl user grant-role {name} {name}'
    )
    
    context.test_env.etcd.exec(
        f'etcdctl auth enable'
    )

@given('init mysql cluster spec')
def init_mysql_cluster_spec(context,):
    context.test_env.mysql_manager.exec(
        f'python cli/mysql-cli.py init -f /etc/mm/cluster-spec.yaml'
    )

@given('init mysql cluster spec standby of remote mysql')
def init_mysql_cluster_spec_with_remote(context,):
    context.test_env.mysql_manager.exec(
        f'python cli/mysql-cli.py init -f /etc/mm/cluster-spec.yaml --standby'
    )

@given('promote mysql cluster')
def promote_mysql_cluster(context,):
    context.test_env.mysql_manager.exec(
        f'python cli/mysql-cli.py promote'
    )

@given('change fail interval to {n:d} seconds')
def change_file_interval(context, n):
    context.test_env.mysql_manager.exec(
        f'python cli/mysql-cli.py set-fail-interval {n}'
    )

@given('add mysql to cluster with host: {host} and name: {name} and user: {user} and password: {password}')
def add_mysql_to_cluster(context, host, user, password, name):
    context.test_env.mysql_manager.exec(
        f"python cli/mysql-cli.py add -h {host} -u {user} -p {password} -n {name}"
    )

@given('remove mysql with name: {name}')
def remove_mysql_from_cluster(context, name):
    context.test_env.mysql_manager.exec(
        f"python cli/mysql-cli.py remove -n {name}"
    )

@given('stop mysql with server_id {server_id:d}')
def stop_mysql(context, server_id):
    context.test_env.stop_mysql(server_id)

@given('start mysql with server_id {server_id:d}')
def start_mysql(context, server_id):
    context.test_env.start_mysql(server_id)

@given('restart mysql manager with env ETCD_HOST={etcd_host:w} ETCD_USERNAME={etcd_username:w} ETCD_PASSWORD={etcd_password:w} ETCD_PREFIX={etcd_prefix}')
def restart_mysql_manager(context, etcd_host, etcd_username, etcd_password, etcd_prefix):
    envs = {
        "ETCD_HOST": etcd_host,
        "ETCD_USERNAME": etcd_username,
        "ETCD_PASSWORD": etcd_password,
        "ETCD_PREFIX": etcd_prefix,
    }
    context.test_env.restart_mysql_manager(envs)

@step('execute mysql query with user: {user:w}, password: {password:w}, host: {host} and port: {port} query: {query}')
def exec_query(context, user, password, host, port, query):
    mysql = context.test_env.get_one_up_mysql()
    command = f"""mysql -u{user} -p{password} -h {host} -P {port} -e "{query}"
"""
    mysql.exec(command)

@then('result of query: "{query}" with user: {user:w} and password: {password: w} on host: {host} and port: {port} should be')
def evaluate_query_result(context, query, user, password, host, port):
    expected_result = context.text
    mysql = context.test_env.get_one_up_mysql()
    command = f"""mysql -u{user} -p{password} -h {host} -P {port} -X -e "{query}"
"""
    output = mysql.exec(command).output.decode()
    logger.log(level=1, msg=output)
    output = output.split("mysql: [Warning] Using a password on the command line interface can be insecure.\n")
    output = output[1]
    assert xmltodict.parse(output) == xmltodict.parse(expected_result)


@then('cluster status must be')
def evaluate_cluster_status(context):
    expected_result = context.text
    output = context.test_env.mysql_manager.exec(
        "python cli/mysql-cli.py mysql get-cluster-status"
    ).output.decode()
    logger.log(level=1, msg=output)
    assert output == expected_result

@then('logs of mm must contain')
def search_for_logs_in_mm(context,):
    error_text = context.text
    assert error_text in context.test_env.mysql_manager.logs()

@then('replication should be running on mysql with server_id {server_id:d}')
def replication_running_on_mysql(context, server_id):
    mysql = context.test_env.get_mysql_by_server_id(server_id)
    command = (
        f"mysql -u{mysql.root_username} -p{mysql.root_password} "
        f"-h {mysql.name} -P 3306 -e 'SHOW REPLICA STATUS\\G'"
    )
    output = mysql.exec(command).output.decode()
    logger.log(level=1, msg=output)
    assert "Replica_IO_Running: Yes" in output, "Replica IO thread is not running"
    assert "Replica_SQL_Running: Yes" in output, "Replica SQL thread is not running"

@then('logs of mm must not contain')
def search_for_logs_not_in_mm(context,):
    error_text = context.text
    logs = context.test_env.mysql_manager.logs()
    assert error_text not in logs, f"Found unwanted text in logs: {error_text}"

@when('execute password rotation command: {command}')
def execute_password_rotation_command(context, command):
    print(context.test_env.mysql_manager.exec(command).output.decode())


@then('user {user} with password {password} should {ability} connect')
@then('user {user} with password {password} should {ability} connect to {target}')
def user_connection_test(context, user, password, ability, target="source"):
    mysql = context.test_env.get_one_up_mysql()
    should_connect = ability == "be able to"
    host = "mysql-s1" if target == "source" else "mysql-s2"
    
    command = f"mysql -u{user} -p{password} -h {host} -P 3306 -e 'SELECT 1'"
    result = mysql.exec(command)
    
    output = result.output.decode()
    print(output)
    
    # Check if connection failed by looking for "Access denied" in output
    connection_failed = "Access denied" in output
    connection_succeeded = not connection_failed
    
    if should_connect:
        if connection_succeeded:
            print(f"User {user} connection test passed with password {password} on {target}")
        else:
            raise AssertionError(f"User {user} cannot connect with password {password} to {target}. Output: {output}")
    else:
        if connection_succeeded:
            raise AssertionError(f"User {user} should NOT be able to connect with password {password} to {target}, but connection succeeded")
        else:
            print(f"User {user} correctly cannot connect with password {password} to {target}")

@then('replication should be working with new replica password. check with {password} root password')
def replication_should_be_working_with_new_replica_password(context, password):
    mysql = context.test_env.get_one_up_mysql()
    
    command = f"mysql -uroot -p{password} -h mysql-s2 -P 3306 -e 'SHOW REPLICA STATUS\\G'"
    output = mysql.exec(command).output.decode()
    
    print(output)
    
    io_running = "Replica_IO_Running: Yes" in output
    sql_running = "Replica_SQL_Running: Yes" in output
    
    assert io_running, f"IO thread not running"
    assert sql_running, f"SQL thread not running"
