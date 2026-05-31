from config.settings import SENTRY_DSN


SENSITIVE_KEYS = {"post_text", "ocr_text", "git_diff", "screenshot_path", "api_key", "key"}


def _strip_sensitive(value):
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if key in SENSITIVE_KEYS else _strip_sensitive(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_strip_sensitive(item) for item in value]
    return value


def init_sentry() -> None:
    if not SENTRY_DSN:
        print("[Monitoring] Sentry not configured - skipping")
        return

    try:
        import sentry_sdk

        def before_send(event, hint):
            return _strip_sensitive(event)

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            environment="production",
            before_send=before_send,
        )
        print("[Monitoring] Sentry configured")
    except Exception as e:
        print(f"[Monitoring] Sentry init failed: {e}")


def capture_error(error: Exception, context: dict = {}) -> None:
    safe_context = _strip_sensitive(context or {})
    print(f"[Error] {error}")
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            for key, value in safe_context.items():
                scope.set_context(key, value if isinstance(value, dict) else {"value": value})
            sentry_sdk.capture_exception(error)
    except Exception:
        return


if __name__ == "__main__":
    init_sentry()
