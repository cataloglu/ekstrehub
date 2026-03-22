from app.addon_version import read_addon_version


def test_read_addon_version_from_repo_config() -> None:
    v = read_addon_version()
    assert v is not None
    parts = v.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)
