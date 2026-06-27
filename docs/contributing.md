First off, thanks for your support. Feel free to open issues if you have seen
any bugs or you need more features. If you want to contribute bug fixes
or features to this project please read below.

## installation

You should create your own python virtual environment and install packages in it:

```sh
pip3 install -r requirements.txt
```

Then you can start working on the project. To run project please follow instructions in
[getting started doc](./getting-started.md). To run tests see [unit tests](./contributing.md#test-with-pytest) and [integration tests with behave](./contributing.md#test-with-behave).

## build

Run this to build docker image:

```sh
VERSION=<version>
docker build -t registry.hamdocker.ir/public/mysql-manager:$VERSION -t registry.hamdocker.ir/public/mysql-manager:latest .
docker push registry.hamdocker.ir/public/mysql-manager:$VERSION
docker push registry.hamdocker.ir/public/mysql-manager:latest
```

## generate requirements.txt

This is needed when you add new python package using `poetry add`

```sh
pip install poetry
poetry add <package-name>
## or
poetry update <package-name>
poetry export --without-hashes --format=requirements.txt > requirements.txt
```

## test with pytest

Unit tests live under `tests/unit/`. They use mocks and do not require Docker.

Install dependencies (if you use Poetry):

```sh
poetry install
poetry add --group dev pytest
```

Or with pip:

```sh
pip install -r requirements.txt
pip install pytest
```

Run all unit tests:

```sh
poetry run pytest tests/unit -v
```

Run a single file or test:

```sh
poetry run pytest tests/unit/test_clone.py -v
poetry run pytest tests/unit/test_clone.py::test_clone_exits_on_supervisor_restart_error -v
```

## test with behave

First install behave:

```sh
pip install behave testcontainers
behave tests/features
## if you want to build image
BUILD_IMAGE=true behave tests/features
## if you want to test specific feature
behave tests/features/<feature-name>.feature
## to test a specific scenario at line LINENO
behave tests/features/<feature-name>.feature:LINENO
```

## design and scenarios

when the cluster manager is created it creates src and repl based on s1 and s2, respectively.
scenarios:

- mm is up during failover and startup of cluster, one proxysql, one master and one repl
  - on startup with 2 nodes:
    - wait for all to become up
    - check if proxysql is configured:
      - if not, initialize proxysql setup
    - find src and repl
      - if both have gtid base (only 5 transactions from their own server_uuid) and proxysql is not configured: s1 is master and s2 is repl, config users and stuff in src, add_replica_to_master, add backends to proxysql
      - if repl.is_replica and repl.master is src do nothing
      - if src.is_replica and src.master is repl: switch src and repl
  - on startup with 1 node:
    - wait for all nodes to become up
    - check if proxysql is configured:
      - if not, initialize proxysql setup
    - if src has base gtid set and proxysql is not configured: config users and stuff in src, add src to proxysql
  - reconcile:
    - if `old_master_joined` is false
      - try to connect to repl:
        - make it a replica of src
        - clone src data
        - enable readonly
        - add it to proxysql
    - ping repl and src
      - if src is not up and repl is up:
        - update cluster state
        - increase `master_failure_count` by 1
        - if `master_failure_count` > `MASTER_FAILURE_THRESHOLD`
          - set the variable `old_master_joined` to false
          - shun src in proxysql
          - stop replication, reset replica and disable read_only in repl (repl will be new master)
          - switch repl and src
          - try to connect to old master:
            - make it a replica of new master
            - clone its data
            - enable readonly
      - if both are down
        - update cluster state
        - increase `master_failure_count` by 1
        - increase metric `cluster_connection_failure` (we will get alert)
      - if replica is down
        - update cluster state
      - if replica is up but has replication problem:
        - restart its replication
    - wait for 5 seconds
  - fails:
    - new master fails when old master is not ready yet
    - mm is restarted before old master is joined to new master
    - master disk is full or read-only
    - replica has problem syncing with master
    - mm starts when replica has problem connecting to master
    - mm is restarted when adding initial user and stuff in src
    - crashes when src or repl are not available

metrics:

- `total_cluster_connection_failure`
- `total_successful_failover`
- current server roles

failover test scenarios:

- 2 mysql servers up, 1 proxysql up:
  - master fails. tests:
    - deleted in proxysql
    - old replica must be master:
      - read_only = 0
      - super_read_only = 0
      - no replication config
      - added as a writeable host in proxysql
      - deleted old master
    - old master must join the cluster
      - read_only = 1
      - super_readonly = 0
      - replicating from new master
      - gtid executed set must match that of new master's
  - new master fails
  - after failover mm restarts
  - after initial setup mm restarts
  - master fails and becomes running before failure threshold
