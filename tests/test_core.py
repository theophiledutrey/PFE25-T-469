import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from manager import core

@pytest.fixture
def mock_ini_file(tmp_path):
    return tmp_path / "hosts.ini"

def test_update_ini_inventory_creates_file(mock_ini_file):
    # Patch the HOSTS_INI_FILE constant in manager.core
    with patch('manager.core.HOSTS_INI_FILE', mock_ini_file):
        manager_ip = "192.168.1.100"
        manager_user = "admin"
        manager_password = "password123"
        agents_data = [
            {'ip': '10.0.0.1', 'user': 'user1', 'password': 'p1'},
            {'ip': '10.0.0.2', 'user': 'user2', 'password': 'p2'}
        ]
        
        result = core.update_ini_inventory(manager_ip, manager_user, manager_password, agents_data)
        
        assert result is True
        assert mock_ini_file.exists()
        
        content = mock_ini_file.read_text()
        assert "[security_server]" in content
        assert "192.168.1.100 ansible_user=admin ansible_password=password123 ansible_become_password=password123" in content
        assert "[agents]" in content
        assert "10.0.0.1 ansible_user=user1 ansible_password=p1 ansible_become_password=p1" in content
        assert "10.0.0.2 ansible_user=user2 ansible_password=p2 ansible_become_password=p2" in content

def test_get_inventory_hosts_reads_correctly(mock_ini_file):
    # Create a sample INI file
    ini_content = """
[security_server]
192.168.1.100 = ansible_user=admin ansible_password=pass

[agents]
10.0.0.1 = ansible_user=user1
10.0.0.2 = ansible_user=user2 ansible_password=pass2
"""
    mock_ini_file.write_text(ini_content)

    with patch('manager.core.HOSTS_INI_FILE', mock_ini_file):
        hosts = core.get_inventory_hosts()
        
        assert len(hosts) == 3
        
        # Check Security Server
        server = next(h for h in hosts if h['ip'] == '192.168.1.100')
        assert server['user'] == 'admin'
        
        # Check Agents
        agent1 = next(h for h in hosts if h['ip'] == '10.0.0.1')
        assert agent1['user'] == 'user1'
        
        agent2 = next(h for h in hosts if h['ip'] == '10.0.0.2')
        assert agent2['user'] == 'user2'

def test_update_ini_inventory_rewrites_existing(mock_ini_file):
    # Create initial file
    mock_ini_file.write_text("[agents]\n1.1.1.1 = ansible_user=old")
    
    with patch('manager.core.HOSTS_INI_FILE', mock_ini_file):
        agents_data = [{'ip': '2.2.2.2', 'user': 'new', 'password': ''}]
        
        core.update_ini_inventory("1.1.1.1", "root", "", agents_data)
        
        content = mock_ini_file.read_text()
        assert "2.2.2.2" in content
        assert "1.1.1.1" in content # Manager IP
        assert "ansible_user=old" not in content # Should be overwritten
