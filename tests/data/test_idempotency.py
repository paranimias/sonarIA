from data.idempotency import check_and_set


def test_first_call_returns_true(table):
    assert check_and_set(table, wamid="wamid.ABC") is True


def test_duplicate_returns_false(table):
    check_and_set(table, wamid="wamid.DUP")
    assert check_and_set(table, wamid="wamid.DUP") is False


def test_different_wamids_are_independent(table):
    assert check_and_set(table, wamid="wamid.X") is True
    assert check_and_set(table, wamid="wamid.Y") is True
    assert check_and_set(table, wamid="wamid.X") is False
