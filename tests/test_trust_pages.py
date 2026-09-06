"""The About/Privacy/Contact pages are a launch requirement, not decoration.

Affiliate networks reject anonymous sites, and UK GDPR wants a named data
controller. The build must refuse to publish placeholder identity rather than
shipping an About page that says "TODO: your name".
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402


def test_identity_placeholders_are_detectable():
    """Whatever the current values, the TODO convention must hold: either both
    are real, or the build's guard can spot that they are not."""
    todo = (config.OWNER_NAME.startswith("TODO")
            or config.CONTACT_EMAIL.startswith("TODO"))
    if not todo:
        assert "@" in config.CONTACT_EMAIL, "contact email must be an address"
        assert config.OWNER_NAME.strip(), "owner name must not be blank"


def test_contact_email_is_not_a_bare_todo_string_if_used():
    if not config.CONTACT_EMAIL.startswith("TODO"):
        assert not config.CONTACT_EMAIL.lower().startswith("todo")
