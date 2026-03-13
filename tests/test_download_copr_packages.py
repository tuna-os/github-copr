import pytest
from unittest.mock import patch, MagicMock
from scripts.download_copr_packages import download_package

@patch('subprocess.run')
def test_download_package_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    assert download_package("user/project", "pkg", "dest") == True
    mock_run.assert_called_once()

@patch('subprocess.run')
def test_download_package_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    assert download_package("user/project", "pkg", "dest") == False
