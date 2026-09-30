from config import _fix_db_url


def test_normaliza_postgres_a_postgresql():
    assert _fix_db_url("postgres://user:pw@host/db") == "postgresql+psycopg2://user:pw@host/db"


def test_fija_driver_psycopg2_en_url_postgresql_sin_driver():
    assert _fix_db_url("postgresql://user:pw@host/db") == "postgresql+psycopg2://user:pw@host/db"


def test_respeta_driver_ya_especificado():
    assert _fix_db_url("postgresql+psycopg://user:pw@host/db") == "postgresql+psycopg://user:pw@host/db"


def test_url_none_se_mantiene():
    assert _fix_db_url(None) is None
