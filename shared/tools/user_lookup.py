def handle(tool_input: dict, *, ctx: dict) -> dict:
    identity = ctx.get("user_identity")
    if not identity:
        return {"ok": True, "user": None, "anonymous": True}
    return {
        "ok": True,
        "anonymous": False,
        "user": {
            "user_id": identity.get("user_id"),
            "full_name": identity.get("full_name"),
            "email": identity.get("email"),
            "role_name": identity.get("role_name", "user"),
        },
    }
