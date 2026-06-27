from pymysql.err import OperationalError

from tests.unit.conftest import MockedMysql


def test_clone_exits_on_supervisor_restart_error(mocked_cluster):
    repl = MockedMysql("s2").on_clone_error(
        "Restart server failed (mysqld is not managed by supervisor process)"
    )
    src = MockedMysql("s1")

    mocked_cluster.clone(repl, src)

    repl.run_command.assert_called_once()


def test_clone_retries_on_transient_operational_error(mocked_cluster):
    repl = MockedMysql("s2").on_clone_sequence(
        [
            OperationalError("Lock wait timeout"),
            OperationalError(
                "Restart server failed (mysqld is not managed by supervisor process)"
            ),
        ]
    )
    src = MockedMysql("s1")

    mocked_cluster.clone(repl, src)

    assert repl.run_command.call_count == 2
