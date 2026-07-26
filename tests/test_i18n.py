from flask_babel import get_locale


def test_default_locale_is_spanish(app):
    with app.test_request_context("/"):
        locale = get_locale()
        assert str(locale) == "es"
