from data.conversations import append_turn, get_turns

WA_ID = "573009876543"


def test_append_and_get_single_turn(table):
    append_turn(table, wa_id=WA_ID, index=0, role="user", content="Hola")
    turns = get_turns(table, wa_id=WA_ID, n=10)
    assert len(turns) == 1
    assert turns[0]["role"] == "user"
    assert turns[0]["content"] == "Hola"


def test_get_turns_returns_oldest_first(table):
    turns_data = [("user", "Hola"), ("assistant", "Buenas"), ("user", "Qué hay?")]
    for i, (role, text) in enumerate(turns_data):
        append_turn(table, wa_id=WA_ID, index=i, role=role, content=text)

    turns = get_turns(table, wa_id=WA_ID, n=10)
    assert [t["role"] for t in turns] == ["user", "assistant", "user"]
    assert turns[0]["content"] == "Hola"


def test_get_turns_respects_limit(table):
    for i in range(5):
        append_turn(table, wa_id=WA_ID, index=i, role="user", content=f"msg{i}")

    turns = get_turns(table, wa_id=WA_ID, n=3)
    assert len(turns) == 3
    # Should be the last 3 (oldest-first within that window)
    assert turns[-1]["content"] == "msg4"


def test_get_turns_empty(table):
    assert get_turns(table, wa_id="unknown", n=10) == []


def test_append_turn_with_meta(table):
    meta = {"tools_used": ["recommend_events"], "usage": {"input_tokens": 100}}
    append_turn(table, wa_id=WA_ID, index=0, role="assistant", content="Aquí tienes", meta=meta)
    turns = get_turns(table, wa_id=WA_ID, n=1)
    assert turns[0]["meta"]["tools_used"] == ["recommend_events"]
