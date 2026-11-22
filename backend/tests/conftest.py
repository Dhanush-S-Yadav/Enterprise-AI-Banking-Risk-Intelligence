import pytest
from pathlib import Path

@pytest.fixture
def local_store(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config,'DATA_DIR',tmp_path)
    monkeypatch.setattr(config,'DOC_DIR',tmp_path/'documents')
    monkeypatch.setattr(config,'REPORT_DIR',tmp_path/'reports')
    monkeypatch.setattr(config,'VECTOR_DIR',tmp_path/'vectors')
    for name in ['documents','reports','vectors']:(tmp_path/name).mkdir()
    return tmp_path
