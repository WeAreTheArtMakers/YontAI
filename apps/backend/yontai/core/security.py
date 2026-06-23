SECRET_REDACTION_KEYS = {"token", "secret", "password", "api_key", "authorization"}


def redact_mapping(payload: dict[str, object]) -> dict[str, object]:
    return {
        key: "***" if key.lower() in SECRET_REDACTION_KEYS else value
        for key, value in payload.items()
    }
