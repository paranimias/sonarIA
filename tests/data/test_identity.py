from data.identity import get_by_id, put_user, resolve_by_phone


def test_put_and_get_by_id(table):
    put_user(table, user_id="u1", wa_id="573001111111", full_name="Joel", email="joel@test.com")
    user = get_by_id(table, user_id="u1")
    assert user is not None
    assert user["full_name"] == "Joel"
    assert user["email"] == "joel@test.com"


def test_resolve_by_phone(table):
    put_user(table, user_id="u1", wa_id="573001111111", full_name="Joel")
    results = resolve_by_phone(table, wa_id="573001111111")
    assert len(results) == 1
    assert results[0]["user_id"] == "u1"


def test_resolve_by_phone_unknown(table):
    assert resolve_by_phone(table, wa_id="000000") == []


def test_get_by_id_unknown(table):
    assert get_by_id(table, user_id="nonexistent") is None
