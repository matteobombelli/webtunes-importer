import pytest

from webtunes_importer.core.runtime_deps import _parse_sha256sum

DIGEST = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_parse_coreutils_format():
    raw = f"{DIGEST}  deno-x86_64-unknown-linux-gnu.zip\n".encode()
    assert _parse_sha256sum(raw) == DIGEST


def test_parse_powershell_format_list():
    raw = (
        "\n"
        "Algorithm : SHA256\n"
        f"Hash      : {DIGEST.upper()}\n"
        "Path      : C:\\a\\deno\\deno-x86_64-pc-windows-msvc.zip\n"
        "\n"
    ).encode()
    assert _parse_sha256sum(raw) == DIGEST


def test_parse_powershell_utf16le_bom():
    text = (
        "Algorithm : SHA256\r\n"
        f"Hash      : {DIGEST.upper()}\r\n"
        "Path      : C:\\a\\deno\\deno-x86_64-pc-windows-msvc.zip\r\n"
    )
    raw = b"\xff\xfe" + text.encode("utf-16-le")
    assert _parse_sha256sum(raw) == DIGEST


def test_parse_utf8_bom():
    raw = b"\xef\xbb\xbf" + f"{DIGEST}  deno.zip\n".encode()
    assert _parse_sha256sum(raw) == DIGEST


def test_parse_garbage_raises():
    with pytest.raises(RuntimeError, match="checksum"):
        _parse_sha256sum(b"Algorithm : SHA256\nnope\n")
