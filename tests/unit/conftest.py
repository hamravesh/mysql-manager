import pytest
from unittest.mock import MagicMock

from pymysql.err import OperationalError

from mysql_manager.cluster import ClusterManager


class MockedMysql:
    def __init__(self, name="s1", host=None, role="source"):
        self.name = name
        self.host = host or name
        self.role = role
        self.port = 3306
        self.user = "root"
        self.password = "root"
        self.status = "up"
        self.health_check_failures = 0
        self.install_plugin = MagicMock()
        self.get_replica_status = MagicMock(return_value=None)
        self.run_command = MagicMock(return_value=None)

    def on_clone_error(self, message: str):
        def side_effect(command):
            if "CLONE INSTANCE" in command:
                raise OperationalError(message)
            return None

        self.run_command = MagicMock(side_effect=side_effect)
        return self

    def on_clone_raises(self, error: Exception):
        def side_effect(command):
            if "CLONE INSTANCE" in command:
                raise error
            return None

        self.run_command = MagicMock(side_effect=side_effect)
        return self

    def on_clone_sequence(self, errors: list[Exception]):
        def side_effect(command):
            if "CLONE INSTANCE" in command:
                if not errors:
                    return None
                raise errors.pop(0)
            return None

        self.run_command = MagicMock(side_effect=side_effect)
        return self


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("mysql_manager.cluster.time.sleep", lambda *_: None)


@pytest.fixture
def mocked_cluster():
    mgr = ClusterManager.__new__(ClusterManager)
    mgr.cluster_data_handler = MagicMock()
    mgr.etcd_client = MagicMock()
    mgr.fail_interval = 15
    mgr.src = MockedMysql("s1", role="source")
    mgr.repl = MockedMysql("s2", role="replica")
    mgr.remote = None
    mgr.users = {"replPassword": "password"}
    return mgr
