import pytest
from unittest.mock import MagicMock

from tests.unit.conftest import MockedMysql


def test_clone_success_starts_replication(mocked_cluster):
    mocked_cluster.repl = MockedMysql("s2", role="replica").on_clone_error(
        "Restart server failed (mysqld is not managed by supervisor process)"
    )
    mocked_cluster.is_server_up = MagicMock(return_value=True)
    mocked_cluster.start_mysql_replication = MagicMock()

    mocked_cluster.join_replica_to_source(retry=1)

    mocked_cluster.start_mysql_replication.assert_called_once()


def test_clone_failure_does_not_start_replication_and_must_join_returns_true(
    mocked_cluster,
):
    mocked_cluster.repl = MockedMysql("s2", role="replica").on_clone_raises(
        RuntimeError("clone failed")
    )
    mocked_cluster.is_server_up = MagicMock(return_value=False)
    mocked_cluster.start_mysql_replication = MagicMock()

    with pytest.raises(RuntimeError, match="clone failed"):
        mocked_cluster.join_replica_to_source(retry=1)

    mocked_cluster.start_mysql_replication.assert_not_called()

    mocked_cluster.is_server_up = MagicMock(return_value=True)
    assert (
        mocked_cluster.must_replica_join_source(mocked_cluster.repl, mocked_cluster.src)
        is True
    )
