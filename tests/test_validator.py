"""SQL 安全校验测试。运行: python tests/test_validator.py 或 pytest"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sqlbot.validator import SQLRejected, validate_sql


def test_select_gets_limit():
    assert validate_sql("select * from wip").endswith("LIMIT 200")


def test_existing_limit_kept():
    assert "LIMIT 10" in validate_sql("SELECT * FROM alarms LIMIT 10")


def test_limit_clamped():
    sql = validate_sql("SELECT * FROM alarms LIMIT 5000", max_rows=200)
    assert "LIMIT 200" in sql


def test_with_select_allowed():
    assert validate_sql("WITH t AS (SELECT 1 AS x) SELECT x FROM t").startswith("WITH")


def _expect_reject(sql):
    try:
        validate_sql(sql)
    except SQLRejected:
        return
    raise AssertionError(f"应当被拒绝: {sql}")


def test_update_rejected():
    _expect_reject("UPDATE wip SET qty = 0")


def test_delete_rejected():
    _expect_reject("DELETE FROM alarms")


def test_multi_statement_rejected():
    _expect_reject("SELECT 1; SELECT 2")


def test_comment_rejected():
    _expect_reject("SELECT 1 -- 注释")


def test_pragma_rejected():
    _expect_reject("PRAGMA journal_mode=WAL")


def test_string_literal_keyword_ok():
    sql = validate_sql("SELECT * FROM wip WHERE lot_id = 'DELETE_ME'")
    assert "DELETE_ME" in sql  # 字符串里的关键字不应误判


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("全部通过")
