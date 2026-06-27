from unittest.mock import MagicMock


def test_join_starts_replication_only_when_replica_is_up_after_clone(mocked_cluster):
    mocked_cluster.clone = MagicMock()
    mocked_cluster.is_server_up = MagicMock(return_value=True)
    mocked_cluster.start_mysql_replication = MagicMock()

    mocked_cluster.join_replica_to_source(retry=3)

    mocked_cluster.clone.assert_called_once_with(mocked_cluster.repl, mocked_cluster.src)
    mocked_cluster.is_server_up.assert_called_once_with(mocked_cluster.repl, retry=3)
    mocked_cluster.start_mysql_replication.assert_called_once()


def test_join_does_not_start_replication_when_replica_still_down_after_clone(
    mocked_cluster,
):
    mocked_cluster.clone = MagicMock()
    mocked_cluster.is_server_up = MagicMock(return_value=False)
    mocked_cluster.start_mysql_replication = MagicMock()

    mocked_cluster.join_replica_to_source()

    mocked_cluster.start_mysql_replication.assert_not_called()
