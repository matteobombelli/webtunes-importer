import webtunes_importer.config as config
from webtunes_importer.config import AppConfig, Connection, Settings, load_config, save_config


def _use_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")


def test_load_missing_file_gives_defaults(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    cfg = load_config()
    assert cfg.settings == Settings()
    assert cfg.connection is None


def test_round_trip(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    cfg = AppConfig(
        settings=Settings(version_pref="studio", quality="opus", strictness=0.85,
                          server_url="https://example.com/wt"),
        connection=Connection(server_url="https://example.com/wt", token="wtx_abc",
                              user_name="Matteo"),
    )
    save_config(cfg)
    loaded = load_config()
    assert loaded == cfg


def test_corrupt_file_gives_defaults(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text("{not json", encoding="utf-8")
    assert load_config() == AppConfig()


def test_unknown_keys_ignored(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text(
        '{"settings": {"quality": "128", "future_flag": true}, "connection": null}',
        encoding="utf-8",
    )
    cfg = load_config()
    assert cfg.settings.quality == "128"


def test_connection_without_token_dropped(monkeypatch, tmp_path):
    _use_tmp(monkeypatch, tmp_path)
    (tmp_path / "config.json").write_text(
        '{"settings": {}, "connection": {"server_url": "https://x", "token": ""}}',
        encoding="utf-8",
    )
    assert load_config().connection is None
