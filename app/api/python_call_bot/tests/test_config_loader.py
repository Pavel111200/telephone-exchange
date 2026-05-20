import pytest
from config_loader import load_config, format_message

def test_load_config_returns_dict():
    config = load_config("config.yaml")
    assert isinstance(config, dict)
    assert "pbx" in config
    assert "call" in config
    assert "messages" in config

def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")

def test_format_message_substitutes_placeholders():
    template = "Обява за {position} в {company} от {platform}"
    job = {"position": "Продавач", "company": "Пепко", "platform": "Джобии"}
    result = format_message(template, job)
    assert result == "Обява за Продавач в Пепко от Джобии"
