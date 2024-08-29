from importlib.resources import files


def test_package_contains_inline_typing_marker() -> None:
    assert files("api_pagination_kit").joinpath("py.typed").is_file()
