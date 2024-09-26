from guacamole_user_sync import version


class TestAbout:
    """Test about.py."""

    def test_version(self) -> None:
        assert version == "0.6.0"
