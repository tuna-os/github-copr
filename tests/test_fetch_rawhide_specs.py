import pytest
from unittest.mock import patch, MagicMock
from scripts.fetch_rawhide_specs import clone_package

@patch('subprocess.run')
def test_clone_package_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    assert clone_package("pkg", "dest") == True
    mock_run.assert_called_once()

@patch('subprocess.run')
def test_clone_package_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    assert clone_package("pkg", "dest") == False
