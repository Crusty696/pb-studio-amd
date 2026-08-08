from __future__ import annotations

import sqlite3
from unittest.mock import Mock, call

from pb_studio.data.database_core import DatabaseCore


def test_configure_connection_enables_normal_synchronous_after_wal() -> None:
    database = object.__new__(DatabaseCore)
    database._register_sql_functions = Mock()
    connection = Mock()

    database._configure_connection(connection)

    assert connection.row_factory is sqlite3.Row
    assert connection.execute.call_args_list == [
        call("PRAGMA journal_mode=WAL;"),
        call("PRAGMA synchronous=NORMAL;"),
        call("PRAGMA foreign_keys=ON;"),
        call("PRAGMA busy_timeout=30000;"),
    ]
    database._register_sql_functions.assert_called_once_with(connection)
