from app.main import app


def test_member_and_specialist_json_success_responses_are_structured() -> None:
    loose: list[str] = []
    for path, item in app.openapi()["paths"].items():
        if not path.startswith("/api/v1/") or "/admin/" in path:
            continue
        for method, operation in item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            for status_code, response in operation.get("responses", {}).items():
                if not str(status_code).startswith("2"):
                    continue
                schema = response.get("content", {}).get("application/json", {}).get("schema")
                if schema and schema.get("additionalProperties") is True:
                    loose.append(f"{method.upper()} {path}")
    assert loose == []


def test_openapi_publishes_native_bearer_security() -> None:
    document = app.openapi()
    scheme = document["components"]["securitySchemes"]["HTTPBearer"]

    assert scheme == {"type": "http", "scheme": "bearer"}
    assert document["paths"]["/api/v1/auth/mobile/logout"]["post"]["security"] == [
        {"HTTPBearer": []}
    ]


def test_openapi_keeps_mobile_account_and_specialist_boundaries_explicit() -> None:
    paths = app.openapi()["paths"]

    assert paths["/api/v1/account-deletion"]["get"]["security"] == [{"HTTPBearer": []}]
    assert paths["/api/v1/account-deletion"]["post"]["security"] == [{"HTTPBearer": []}]
    assert paths["/api/v1/account-deletion/cancel"]["post"]["security"] == [
        {"HTTPBearer": []}
    ]
    assert paths["/api/v1/coach/workout-reviews/access"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
    assert paths["/api/v1/nutrition/physician/access"]["get"]["security"] == [
        {"HTTPBearer": []}
    ]
