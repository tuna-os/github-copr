import pytest
from unittest.mock import patch, MagicMock
import os
from scripts.download_copr_packages import download_srpm

@patch('subprocess.run')
@patch('os.walk')
@patch('os.rename')
@patch('os.path.exists')
@patch('shutil.rmtree')
def test_download_srpm_success(mock_rmtree, mock_exists, mock_rename, mock_walk, mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    mock_walk.return_value = [('/dest/epel-10-x86_64/123-pkg', [], ['pkg.src.rpm'])]
    mock_exists.return_value = True
    
    assert download_srpm("123", "/dest") == True
    mock_run.assert_called_once()

@patch('subprocess.run')
def test_download_srpm_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1)
    assert download_srpm("123", "/dest") == False
