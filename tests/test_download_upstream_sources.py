import pytest
from unittest.mock import patch, MagicMock
from scripts.download_upstream_sources import download_source

@patch('subprocess.run')
def test_download_source_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    assert download_source("http://example.com/src.tar.xz", "dest") == True
    mock_run.assert_called_once()

@patch('subprocess.run')
def test_download_source_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    assert download_source("http://example.com/src.tar.xz", "dest") == False
