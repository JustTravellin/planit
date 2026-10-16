from p1s_controller import config


def test_roundtrip_without_keyring(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_keyring", lambda: None)
    cfg = config.PrinterConfig("192.168.1.50", "01P00A000000000", "12345678")
    config.save(cfg, tmp_path)
    assert config.load(tmp_path) == cfg


def test_load_missing(tmp_path):
    assert config.load(tmp_path) is None
