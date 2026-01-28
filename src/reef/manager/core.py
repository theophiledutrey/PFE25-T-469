import os
import subprocess
import sys
import re
import urllib.parse
from pathlib import Path
from ruamel.yaml import YAML
from rich.console import Console

# Initialize Rich Console (Needed for logging in legacy functions)
console = Console()
VERBOSE_MODE = False

BASE_DIR = Path(__file__).parent.parent.resolve()
ANSIBLE_DIR = BASE_DIR / "ansible"
TERRAFORM_DIR = BASE_DIR / "terraform"
INVENTORY_DIR = ANSIBLE_DIR / "inventory"
GROUP_VARS_FILE = INVENTORY_DIR / "group_vars" / "all.yml"
HOSTS_INI_FILE = INVENTORY_DIR / "hosts.ini"
SCRIPTS_DIR = BASE_DIR / "scripts"

def run_command(command, cwd=BASE_DIR, quiet=False):
    """
    Run a shell command.
    If quiet is True, output is hidden (suppressed) and only shown on error.
    """
    try:
        # If quiet check global verbose override
        if VERBOSE_MODE:
            quiet = False

        env = os.environ.copy()
        env['ANSIBLE_CONFIG'] = str(BASE_DIR / "ansible.cfg")
        env['ANSIBLE_ROLES_PATH'] = str(ANSIBLE_DIR / "roles")

        if quiet:
            with console.status(f"[bold blue]Running:[/bold blue] {command} ..."):
                result = subprocess.run(
                    command, 
                    shell=True, 
                    check=True, 
                    cwd=cwd, 
                    executable='/bin/bash',
                    capture_output=True,
                    text=True,
                    env=env
                )
        else:
            console.print(f"[bold blue]Running:[/bold blue] {command}")
            result = subprocess.run(
                command, 
                shell=True, 
                check=True, 
                cwd=cwd,
                executable='/bin/bash',
                env=env
            )
        return True
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Command cancelled by user.[/bold yellow]")
        return False
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error running command:[/bold red] {command}")
        # Always show output on error if it was hidden
        if quiet:
            if e.stdout:
                console.print(f"[dim]Stdout:[/dim]\n{e.stdout}")
            if e.stderr:
                console.print(f"[bold red]Stderr:[/bold red]\n{e.stderr}")
        return False
        
# Schema Configuration
SCHEMA_FILE = BASE_DIR / "config.schema.yml"

class SchemaManager:
    def __init__(self, schema_path):
        self.schema_path = schema_path
        self.schema = self._load_schema()

    def _load_schema(self):
        if not self.schema_path.exists():
            console.print(f"[bold red]Error:[/bold red] Schema file not found at {self.schema_path}")
            sys.exit(1)
        
        yaml = YAML()
        try:
            with open(self.schema_path, 'r') as f:
                return yaml.load(f)
        except Exception as e:
            console.print(f"[bold red]Error loading schema:[/bold red] {e}")
            sys.exit(1)

    def get_variables(self):
        return self.schema.get('variables', [])

    def get_categories(self):
        variables = self.get_variables()
        categories = {}
        for var in variables:
            cat = var.get('category', 'Uncategorized')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(var)
        return categories

    def validate(self, var_def, value):
        var_type = var_def.get('type')
        validation = var_def.get('validation', {})
        
        # Type conversion and basic check
        try:
            if var_type == 'integer':
                value = int(value)
            elif var_type == 'boolean':
                if isinstance(value, str):
                    value = value.lower() in ('true', 'yes', '1', 'y')
            elif var_type == 'list':
                if isinstance(value, str):
                    # quick safe parse for list input if needed, though Prompt might return string
                    # For simplicty in this interactive CLI, we might expect comma separated or JSON
                    if value.startswith('[') and value.endswith(']'):
                        import ast
                        value = ast.literal_eval(value)
                    else:
                        value = [x.strip() for x in value.split(',')]
        except ValueError:
            return False, f"Invalid type. Expected {var_type}."

        # Allowed values
        allowed = var_def.get('allowed_values')
        if allowed and value not in allowed:
            return False, f"Value must be one of: {', '.join(allowed)}"

        # Numeric validation
        if var_type == 'integer':
            min_val = validation.get('min')
            max_val = validation.get('max')
            if min_val is not None and value < min_val:
                return False, f"Value must be >= {min_val}"
            if max_val is not None and value > max_val:
                return False, f"Value must be <= {max_val}"

        # Regex validation
        regex_pattern = validation.get('regex')
        if regex_pattern and var_type == 'string':
            if not re.match(regex_pattern, value):
                return False, f"Value does not match required pattern: {regex_pattern}"

        return True, value

def load_current_config():
    """Load current values from group_vars/all.yml"""
    yaml = YAML()
    if GROUP_VARS_FILE.exists():
        try:
            with open(GROUP_VARS_FILE, 'r') as f:
                return yaml.load(f) or {}
        except:
            pass
    return {}

def get_manager_credentials_from_inventory():
    """Extract Manager IP, SSH user, and SSH password from hosts.ini [security_server] section"""
    if not HOSTS_INI_FILE.exists():
        return None, None, None
    
    try:
        content = HOSTS_INI_FILE.read_text()
        lines = content.splitlines()
        in_security_server = False
        manager_ip = None
        manager_user = 'ubuntu'
        manager_password = None
        
        for line in lines:
            line = line.strip()
            
            # Check for section header
            if line.startswith('['):
                in_security_server = line.strip('[]') == 'security_server'
                continue
            
            # Parse lines in security_server section
            if in_security_server and line and not line.startswith('#'):
                parts = line.split()
                if parts:
                    # First part is IP address
                    manager_ip = parts[0]
                    
                    # Parse ansible variables
                    for part in parts[1:]:
                        if part.startswith('ansible_user='):
                            manager_user = part.split('=', 1)[1]
                        elif part.startswith('ansible_password='):
                            manager_password = part.split('=', 1)[1]
        
        return manager_ip, manager_user, manager_password
    except Exception as e:
        console.print(f"[bold red]Error parsing hosts.ini:[/bold red] {e}")
        return None, None, None

def update_yaml_config_from_schema(config_data):
    """Update ansible/inventory/group_vars/all.yml preserving comments."""
    yaml = YAML()
    yaml.preserve_quotes = True
    
    if not GROUP_VARS_FILE.exists():
        # Create parent dir if not exists
        GROUP_VARS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Create empty file if not exists
        with open(GROUP_VARS_FILE, 'w') as f:
            f.write("---\n")

    try:
        with open(GROUP_VARS_FILE, 'r') as f:
            data = yaml.load(f) or {}

        # Update values
        for key, value in config_data.items():
            data[key] = value

        with open(GROUP_VARS_FILE, 'w') as f:
            yaml.dump(data, f)
        
        console.print(f"[green]Successfully updated {GROUP_VARS_FILE}[/green]")
        return True
    except Exception as e:
        console.print(f"[bold red]Failed to update YAML config:[/bold red] {e}")
        return False

import configparser

def update_ini_inventory(manager_ip, manager_user, manager_password, manager_key, agents_data):
    """Update ansible/inventory/hosts.ini using configparser with space delimiter."""
    # Use space as delimiter so "ip vars" is parsed as Key: "ip", Value: "vars"
    config = configparser.ConfigParser(delimiters=(' '), allow_no_value=True)
    
    # We will build exactly what we need.
    config.add_section('security_server')
    
    manager_entry_values = []
    if manager_user:
        manager_entry_values.append(f"ansible_user={manager_user}")
    else:
        # If no user specified, defaults might be used, but for clarity let's set root or nothing
        # The original code set root.
        manager_entry_values.append("ansible_user=root")
        
    if manager_password:
        manager_entry_values.append(f"ansible_password={manager_password}")
        manager_entry_values.append(f"ansible_become_password={manager_password}")

    if manager_key:
        manager_entry_values.append(f"ansible_ssh_private_key_file={manager_key}")
    
    val_str = " ".join(manager_entry_values)
    config.set('security_server', manager_ip, val_str)

    config.add_section('agents')
    for agent in agents_data:
        agent_values = []
        if agent['user']:
            agent_values.append(f"ansible_user={agent['user']}")
        if agent['password']:
            agent_values.append(f"ansible_password={agent['password']}")
            agent_values.append(f"ansible_become_password={agent['password']}")
        if agent.get('key'):
             agent_values.append(f"ansible_ssh_private_key_file={agent['key']}")
        
        val_str = " ".join(agent_values) if agent_values else None
        config.set('agents', agent['ip'], val_str)

    try:
        # Ensure parent directory exists
        if not HOSTS_INI_FILE.parent.exists():
            HOSTS_INI_FILE.parent.mkdir(parents=True, exist_ok=True)
            
        with open(HOSTS_INI_FILE, 'w') as f:
            config.write(f, space_around_delimiters=False)
            
        console.print(f"[green]Successfully updated {HOSTS_INI_FILE}[/green]")
        return True
    except Exception as e:
        console.print(f"[bold red]Failed to update INI inventory:[/bold red] {e}")
        return False

def get_inventory_hosts():
    """
    Parse hosts.ini to find all configured hosts.
    Returns a list of dicts: [{'ip': '...', 'user': '...'}]
    """
    if not HOSTS_INI_FILE.exists():
        return []

    # Use space delimiter
    config = configparser.ConfigParser(delimiters=(' '), allow_no_value=True)
    hosts = []
    
    try:
        config.read(HOSTS_INI_FILE)
        
        def parse_section(section_name):
            if section_name not in config:
                return
            
            for ip in config[section_name]:
                # ip is the key
                # vars is the value
                vars_str = config[section_name][ip]
                
                user = "root"
                key = ""
                password = ""
                
                if vars_str:
                    match_user = re.search(r'ansible_user=(\S+)', vars_str)
                    if match_user:
                        user = match_user.group(1)
                    
                    match_key = re.search(r'ansible_ssh_private_key_file=(\S+)', vars_str)
                    if match_key:
                        key = match_key.group(1)

                    match_pass = re.search(r'ansible_password=(\S+)', vars_str)
                    if match_pass:
                        password = match_pass.group(1)

                
                hosts.append({'ip': ip, 'user': user, 'key': key, 'password': password})

        parse_section('security_server')
        parse_section('agents')

    except Exception as e:
        console.print(f"[red]Error parsing inventory:[/red] {e}")
        return []

    return hosts

def generate_terraform_vm_config(vm_specs, manager_ip=None, manager_ssh_user=None, manager_ssh_password=None):
    """
    Generate Terraform configuration files (main.tf and terraform.tfvars) for the specified VMs.
    
    vm_specs: list of dicts with keys:
      - name: VM name (e.g., "vm-01")
      - ssh_password: plaintext SSH password (will be hashed)
      - os: OS choice (e.g., "ubuntu-22.04")
    
    manager_ip: IP of the manager (required)
    manager_ssh_user: SSH user for manager (default: ubuntu)
    manager_ssh_password: SSH password for manager (required for password auth)
    
    Returns: {'success': True/False, 'terraform_dir': path, 'message': str}
    """
    import crypt
    import time
    
    try:
        terraform_dir = TERRAFORM_DIR
        terraform_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique suffix with timestamp to avoid conflicts with existing cloud-init ISOs
        timestamp_suffix = str(int(time.time() * 1000))[-8:]  # Last 8 digits of milliseconds
        
        # If manager_ip not provided, try to load from config
        if not manager_ip:
            cfg = load_current_config()
            manager_ip = cfg.get('wazuh_manager_ip')
            manager_ssh_user = manager_ssh_user or cfg.get('manager_ssh_user', 'ubuntu')
            manager_ssh_password = manager_ssh_password or cfg.get('manager_ssh_password')
        
        if not manager_ip:
            return {'success': False, 'message': "Manager IP not provided and not found in configuration"}
        
        if not manager_ssh_password:
            return {'success': False, 'message': "Manager SSH password not found in configuration. Please set it in Configuration tab."}
        
        manager_ssh_user = manager_ssh_user or 'ubuntu'
        
        # Prepare VM data: hash passwords and derive a safe Linux username from VM name
        vms_data = []
        for spec in vm_specs:
            plain_pwd = spec.get('ssh_password', 'ubuntu')
            hashed = crypt.crypt(plain_pwd, crypt.METHOD_SHA512)
            vm_name_raw = spec.get('name', 'vm-unknown')
            # Derive a safe username: lowercase, keep alnum and dashes only; fallback to 'ubuntu' if empty
            import re
            linux_user = re.sub(r'[^a-z0-9-]', '', vm_name_raw.lower())
            linux_user = linux_user if linux_user else 'ubuntu'
            
            vms_data.append({
                'name': vm_name_raw,
                'ssh_password_hash': hashed,
                'os': spec.get('os', 'ubuntu-22.04'),
                'linux_user': linux_user
            })
        
        # Build main.tf dynamically with SSH password embedded in URI
        # Note: The libvirt provider supports passing credentials via URI query parameters
        # Format: qemu+ssh://user:password@host/system
        main_tf_content = f"""terraform {{
  required_providers {{
    libvirt = {{
      source  = "dmacvicar/libvirt"
      version = "0.7.6"
    }}
  }}
}}

variable "libvirt_uri" {{
  description = "URI of the libvirt daemon on the manager (with SSH credentials)"
  type        = string
  default     = "qemu:///system"
}}

provider "libvirt" {{
  uri = var.libvirt_uri
}}

# Image Ubuntu de base
resource "libvirt_volume" "ubuntu_base" {{
  name   = "ubuntu-base.qcow2"
  pool   = "default"
  source = "https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
  format = "qcow2"
}}

"""
        
        # Add VM resources dynamically
        for vm in vms_data:
            vm_name = vm['name']
            cloudinit_name = f"cloudinit-{vm_name}-{timestamp_suffix}.iso"
            main_tf_content += f"""
# Disque pour VM: {vm_name}
resource "libvirt_volume" "{vm_name}_disk" {{
  name           = "{vm_name}.qcow2"
  pool           = "default"
  base_volume_id = libvirt_volume.ubuntu_base.id
  format         = "qcow2"
}}

# Cloud-init pour VM: {vm_name}
resource "libvirt_cloudinit_disk" "{vm_name}_init" {{
  name = "{cloudinit_name}"
  pool = "default"

  user_data = templatefile(
    "${{path.module}}/cloud_init.cfg",
    {{
      hostname    = "{vm_name}"
            user_name   = "{linux_user}"
      user_passwd = "{vm['ssh_password_hash']}"
    }}
  )
}}

# VM: {vm_name}
resource "libvirt_domain" "{vm_name}" {{
  name      = "{vm_name}"
    memory    = 512
  vcpu      = 1
  machine   = "pc"
  arch      = "x86_64"
  type      = "qemu"
    qemu_agent  = true

  disk {{
    volume_id = libvirt_volume.{vm_name}_disk.id
  }}

  network_interface {{
    network_name  = "default"
    wait_for_lease = true
  }}

  cloudinit = libvirt_cloudinit_disk.{vm_name}_init.id

  depends_on = [libvirt_volume.ubuntu_base]
}}
"""
        
        # Add outputs
        main_tf_content += "\n# Outputs: IP addresses for each VM\n"
        for vm in vms_data:
            vm_name = vm['name']
            main_tf_content += f"""
output "{vm_name}_ip" {{
  value       = libvirt_domain.{vm_name}.network_interface[0].addresses[0]
  description = "IP address of {vm_name}"
}}
"""
        
        # Write main.tf
        main_tf_path = terraform_dir / "main.tf"
        with open(main_tf_path, 'w') as f:
            f.write(main_tf_content)
        
        # Write terraform.tfvars with libvirt URI (including password for SSH auth)
        tfvars_path = terraform_dir / "terraform.tfvars"
        # Format: qemu+ssh://user:password@host/system (password will be percent-encoded if needed)
        encoded_password = urllib.parse.quote(manager_ssh_password, safe='')
        libvirt_uri = f"qemu+ssh://{manager_ssh_user}:{encoded_password}@{manager_ip}/system"
        tfvars_content = f'libvirt_uri = "{libvirt_uri}"\n'
        with open(tfvars_path, 'w') as f:
            f.write(tfvars_content)
        
        console.print(f"[green]Generated {main_tf_path} with {len(vms_data)} VMs[/green]")
        console.print(f"[green]libvirt_uri: qemu+ssh://{manager_ssh_user}:***@{manager_ip}/system (SSH password embedded)[/green]")
        
        return {
            'success': True,
            'terraform_dir': str(terraform_dir),
            'message': f'Generated Terraform config for {len(vms_data)} VMs on manager {manager_ip}',
            'vms': vms_data,
            'manager_ip': manager_ip,
            'manager_ssh_user': manager_ssh_user,
            'manager_ssh_password': manager_ssh_password,  # Will be used for sshpass
            'libvirt_uri': libvirt_uri
        }
    except Exception as e:
        console.print(f"[bold red]Error generating Terraform config:[/bold red] {e}")
        return {'success': False, 'message': str(e)}


def run_terraform_apply(terraform_dir, log_callback=None, ssh_password=None, manager_ip=None, manager_user=None):
    """
    Execute terraform init, plan, and apply on the manager machine via SSH.
    
    This approach runs Terraform ON THE MANAGER (local libvirt connection), not from the client.
    This avoids SSH authentication issues with remote libvirt connections.
    
    terraform_dir: path to directory containing main.tf (local)
    log_callback: optional callable to log messages (e.g., for UI)
    ssh_password: SSH password for the manager
    manager_ip: IP of the manager machine
    manager_user: SSH user for the manager
    
    Returns: {'success': True/False, 'message': str, 'output': str}
    """
    try:
        terraform_dir = Path(terraform_dir)
        if not terraform_dir.exists():
            return {'success': False, 'message': f"Terraform dir not found: {terraform_dir}"}
        
        if not manager_ip or not manager_user or not ssh_password:
            return {'success': False, 'message': "Manager IP, user, and password required"}
        
        if log_callback:
            log_callback(f"[TF] Connecting to manager via SSH: {manager_user}@{manager_ip}\n")
        
        # Create a temporary directory on the manager for Terraform
        remote_tf_dir = f"/tmp/reef-terraform-{os.getpid()}"
        
        # Step 0: Verify/Install Terraform and dependencies on manager
        if log_callback:
            log_callback("[TF] Checking dependencies on manager...\n")
        
        # Check if terraform is installed
        check_tf_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'which terraform'"
        result = subprocess.run(check_tf_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            if log_callback:
                log_callback("[TF] Terraform not found on manager, installing...\n")
            
            # Install Terraform
            install_tf_cmd = f"""sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo apt-get update && sudo apt-get install -y unzip && wget https://releases.hashicorp.com/terraform/1.5.7/terraform_1.5.7_linux_amd64.zip && unzip terraform_1.5.7_linux_amd64.zip && sudo mv terraform /usr/local/bin/ && rm terraform_1.5.7_linux_amd64.zip'"""
            
            result = subprocess.run(install_tf_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                if log_callback:
                    log_callback(f"[TF] Warning: Failed to install Terraform: {result.stderr}\n")
                    log_callback("[TF] Continuing anyway, Terraform may already be installed or in PATH\n")
        else:
            if log_callback:
                log_callback(f"[TF] Terraform found: {result.stdout.strip()}\n")
        
        # Repair apt/dpkg state before installing anything
        if log_callback:
            log_callback("[TF] Repairing apt/dpkg state on manager...\n")
        
        repair_dpkg_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo dpkg --configure -a && sudo rm -f /var/lib/apt/lists/* && sudo apt-get update || true'"
        result = subprocess.run(repair_dpkg_cmd, shell=True, capture_output=True, text=True)
        if log_callback:
            log_callback("[TF] apt/dpkg repair completed\n")
        
        # Check if libvirt daemon service exists (not just the binary)
        if log_callback:
            log_callback("[TF] Checking libvirt daemon installation...\n")
        
        check_service_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'systemctl list-unit-files | grep libvirtd'"
        result = subprocess.run(check_service_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0 or "libvirtd" not in result.stdout:
            if log_callback:
                log_callback("[TF] libvirt daemon service not found, installing complete libvirt package...\n")
            
            # Install libvirt with all dependencies
            install_libvirt_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo apt-get update && sudo apt-get install -y libvirt-daemon libvirt-daemon-system libvirt-clients qemu-system-x86 qemu-kvm libvirt-daemon-driver-qemu virt-manager --no-install-recommends'"
            result = subprocess.run(install_libvirt_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                if log_callback:
                    log_callback(f"[TF] Failed to install libvirt: {result.stderr}\n")
                return {'success': False, 'message': f"Failed to install libvirt: {result.stderr}"}
            else:
                if log_callback:
                    log_callback("[TF] libvirt installed successfully\n")
        else:
            if log_callback:
                log_callback("[TF] libvirt daemon service found on manager\n")
        
        # Check if libvirt daemon is running
        check_daemon_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo systemctl is-active libvirtd'"
        result = subprocess.run(check_daemon_cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0 or "active" not in result.stdout:
            if log_callback:
                log_callback("[TF] libvirt daemon not running, starting...\n")
            
            # Start libvirt daemon
            start_daemon_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo systemctl start libvirtd && sudo systemctl enable libvirtd'"
            result = subprocess.run(start_daemon_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                if log_callback:
                    log_callback(f"[TF] Warning: Failed to start libvirt daemon: {result.stderr}\n")
            else:
                if log_callback:
                    log_callback("[TF] libvirt daemon started\n")
        else:
            if log_callback:
                log_callback("[TF] libvirt daemon is running\n")
        
        # Add user to libvirt group for socket access
        if log_callback:
            log_callback(f"[TF] Ensuring {manager_user} has libvirt socket access...\n")
        
        add_group_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo usermod -a -G libvirt {manager_user} && sudo usermod -a -G kvm {manager_user}'"
        result = subprocess.run(add_group_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            if log_callback:
                log_callback(f"[TF] Warning: Failed to add user to groups: {result.stderr}\n")
        
        # Restart libvirt daemon to ensure socket permissions are updated
        if log_callback:
            log_callback("[TF] Restarting libvirt daemon to apply group changes...\n")
        
        restart_daemon_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo systemctl restart libvirtd && sleep 2'"
        result = subprocess.run(restart_daemon_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            if log_callback:
                log_callback(f"[TF] Warning: Failed to restart libvirt daemon: {result.stderr}\n")
        else:
            if log_callback:
                log_callback("[TF] libvirt daemon restarted\n")
        
        # Verify socket exists and is accessible
        if log_callback:
            log_callback("[TF] Verifying libvirt socket accessibility...\n")
        
        verify_socket_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'test -S /var/run/libvirt/libvirt-sock && echo \"Socket accessible\" || (ls -la /var/run/libvirt/ && id)'"
        result = subprocess.run(verify_socket_cmd, shell=True, capture_output=True, text=True)
        if log_callback:
            log_callback(f"[TF] Socket check: {result.stdout}\n")
        
        # Install genisoimage (mkisofs) for cloud-init ISO creation
        if log_callback:
            log_callback("[TF] Installing genisoimage for cloud-init...\n")
        
        install_genisoimage_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo apt-get update -qq && sudo apt-get install -y genisoimage && which mkisofs'"
        result = subprocess.run(install_genisoimage_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0 or "mkisofs" not in result.stdout:
            if log_callback:
                log_callback(f"[TF] Error: Failed to install genisoimage. stdout: {result.stdout} stderr: {result.stderr}\n")
            return {'success': False, 'message': f"Failed to install genisoimage (mkisofs): {result.stderr}"}
        else:
            if log_callback:
                log_callback("[TF] genisoimage installed successfully\n")
        
        # ========== COMPREHENSIVE LIBVIRT SETUP VIA SCRIPT ==========
        if log_callback:
            log_callback("[TF] Running comprehensive libvirt setup on manager...\n")
        
        # Create a setup script for Ubuntu/Debian systems
        setup_script = """#!/bin/bash
set -e
echo "[LIBVIRT SETUP] Starting comprehensive Ubuntu libvirt setup"

# Install packages
echo "[LIBVIRT SETUP] Installing libvirt packages..."
sudo apt-get update -qq > /dev/null 2>&1
sudo apt-get install -y libvirt-daemon libvirt-daemon-system libvirt-clients qemu-system-x86 qemu-kvm > /dev/null 2>&1 || true
sudo apt-get install -y qemu-utils > /dev/null 2>&1 || true
sudo apt-get install -y dnsmasq > /dev/null 2>&1 || true

# Disable libvirt security driver to avoid AppArmor denials on images
echo "[LIBVIRT SETUP] Configuring libvirt security driver (none)..."
if [ -f /etc/libvirt/qemu.conf ]; then
    sudo cp -n /etc/libvirt/qemu.conf /etc/libvirt/qemu.conf.bak 2>/dev/null || true
    sudo sed -i 's/^\s*#\?\s*security_driver\s*=\s*.*/security_driver = "none"/g' /etc/libvirt/qemu.conf
    if ! grep -q '^\s*security_driver\s*=\s*"none"' /etc/libvirt/qemu.conf; then
        echo 'security_driver = "none"' | sudo tee -a /etc/libvirt/qemu.conf >/dev/null
    fi
fi

# Start libvirtd
echo "[LIBVIRT SETUP] Starting libvirtd..."
sudo systemctl start libvirtd
sudo systemctl enable libvirtd
sleep 2

# Create symlink
echo "[LIBVIRT SETUP] Setting up symlink..."
sudo ln -sf /run/libvirt /var/run/libvirt

# Setup storage pool
echo "[LIBVIRT SETUP] Setting up storage pool..."
sudo mkdir -p /var/lib/libvirt/images
sudo virsh -c qemu:///system pool-define-as default dir - - - - "/var/lib/libvirt/images" 2>/dev/null || true
sudo virsh -c qemu:///system pool-start default 2>/dev/null || true
sudo virsh -c qemu:///system pool-autostart default

# Setup network - CRITICAL PART
echo "[LIBVIRT SETUP] Destroying old network if exists..."
sudo virsh -c qemu:///system net-destroy default 2>/dev/null || true
sudo virsh -c qemu:///system net-undefine default 2>/dev/null || true
sleep 2

# AGGRESSIVE BRIDGE CLEANUP - Handle ens3 conflicts
echo "[LIBVIRT SETUP] Performing aggressive bridge cleanup..."
# Check if ens3 is enslaved to any bridge
if sudo ip link show ens3 | grep -q "master"; then
  echo "[LIBVIRT SETUP] ens3 is enslaved to a bridge, freeing it..."
  BRIDGE=$(sudo ip link show ens3 | grep master | awk '{print $NF}')
  echo "[LIBVIRT SETUP] ens3 is enslaved to $BRIDGE, removing..."
  sudo ip link set ens3 nomaster 2>/dev/null || true
  sleep 1
fi

# Delete virbr0 if it exists and is not used by libvirtd
echo "[LIBVIRT SETUP] Removing old virbr0 bridge if exists..."
if sudo ip link show virbr0 >/dev/null 2>&1; then
  echo "[LIBVIRT SETUP] Found virbr0, deleting..."
  sudo ip link set virbr0 down 2>/dev/null || true
  sudo ip link delete virbr0 2>/dev/null || true
  sleep 2
fi

echo "[LIBVIRT SETUP] Creating fresh network XML..."
cat > /tmp/libvirt-default-net.xml << 'XMLEOF'
<network>
  <name>default</name>
  <forward mode='nat'/>
  <bridge name='virbr0' stp='on' delay='0'/>
  <ip address='192.168.122.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='192.168.122.100' end='192.168.122.254'/>
    </dhcp>
  </ip>
</network>
XMLEOF

echo "[LIBVIRT SETUP] Defining network..."
sudo virsh -c qemu:///system net-define /tmp/libvirt-default-net.xml
sleep 2

echo "[LIBVIRT SETUP] Starting network..."
if sudo virsh -c qemu:///system net-start default; then
    echo "[LIBVIRT SETUP] Default network started"
    sudo virsh -c qemu:///system net-autostart default
else
    echo "[LIBVIRT SETUP] Default network failed to start, creating isolated reef network..."
    # Create an isolated fallback network to avoid conflicts with ens3
    # If an old reef network exists, destroy and undefine it first
    sudo virsh -c qemu:///system net-destroy reef 2>/dev/null || true
    sudo virsh -c qemu:///system net-undefine reef 2>/dev/null || true
    cat > /tmp/libvirt-reef-net.xml << 'XMLEOF'
<network>
    <name>reef</name>
    <forward mode='nat'/>
    <bridge name='virbr1' stp='on' delay='0'/>
    <ip address='192.168.200.1' netmask='255.255.255.0'>
        <dhcp>
            <range start='192.168.200.100' end='192.168.200.254'/>
        </dhcp>
    </ip>
</network>
XMLEOF
    echo "[LIBVIRT SETUP] Defining fallback network reef..."
    sudo virsh -c qemu:///system net-define /tmp/libvirt-reef-net.xml
    sleep 2
    echo "[LIBVIRT SETUP] Starting fallback network reef..."
    sudo virsh -c qemu:///system net-start reef
    sudo virsh -c qemu:///system net-autostart reef
    echo "FALLBACK_REEF_NETWORK"
fi

# Verify
echo "[LIBVIRT SETUP] Verification results:"
echo "=== Pools ==="
sudo virsh -c qemu:///system pool-list --all
echo "=== Networks ==="
sudo virsh -c qemu:///system net-list --all
echo "=== Network Details ==="
sudo virsh -c qemu:///system net-info default || echo "Network info not available"
echo "[LIBVIRT SETUP] Complete"
"""
        
        setup_script_local = f"/tmp/libvirt-setup-{os.getpid()}.sh"
        Path(setup_script_local).write_text(setup_script)
        Path(setup_script_local).chmod(0o755)
        
        # Copy and execute setup script on manager
        scp_script_cmd = f"sshpass -p '{ssh_password}' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {setup_script_local} {manager_user}@{manager_ip}:/tmp/libvirt-setup.sh"
        result = subprocess.run(scp_script_cmd, shell=True, capture_output=True, text=True)
        
        exec_script_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'bash /tmp/libvirt-setup.sh && sudo systemctl restart libvirtd && sleep 2'"
        result = subprocess.run(exec_script_cmd, shell=True, capture_output=True, text=True)
        if log_callback:
            log_callback(f"[TF] Setup script output:\n{result.stdout}\n")
        if result.stderr:
            if log_callback:
                log_callback(f"[TF] Setup script stderr:\n{result.stderr}\n")
                # Note whether the setup created the reef network
                created_reef_network = "FALLBACK_REEF_NETWORK" in (result.stdout or "")
        
        # ========== COPY TERRAFORM FILES ==========
        # Step 1: Create remote directory via SSH
        if log_callback:
            log_callback(f"[TF] Creating remote directory: {remote_tf_dir}\n")
        
        mkdir_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} mkdir -p {remote_tf_dir}"
        result = subprocess.run(mkdir_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            if log_callback:
                log_callback(f"[TF] Failed to create remote directory: {result.stderr}\n")
            return {'success': False, 'message': f"Failed to create remote directory: {result.stderr}"}
        
        # Step 2: Copy Terraform files to manager via SCP
        if log_callback:
            log_callback(f"[TF] Copying Terraform files to manager...\n")
        
        scp_cmd = f"sshpass -p '{ssh_password}' scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r {terraform_dir}/* {manager_user}@{manager_ip}:{remote_tf_dir}/"
        result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            if log_callback:
                log_callback(f"[TF] Failed to copy files: {result.stderr}\n")
            return {'success': False, 'message': f"Failed to copy Terraform files: {result.stderr}"}
        
        # If reef network exists (or was created), update Terraform to use it instead of 'default'
        try:
            use_reef = created_reef_network
            if not use_reef:
                check_reef_cmd = (
                    f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"{manager_user}@{manager_ip} 'sudo virsh -c qemu:///system net-info reef 2>/dev/null | grep -q \"Active:.*yes\"'"
                )
                reef_status = subprocess.run(check_reef_cmd, shell=True)
                use_reef = (reef_status.returncode == 0)
            if use_reef:
                if log_callback:
                    log_callback("[TF] Switching Terraform network to 'reef' (avoid default)\n")
                replace_net_cmd = (
                    f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                    f"{manager_user}@{manager_ip} 'sed -i \"s/network_name\\s*=\\s*\\\"default\\\"/network_name = \\\"reef\\\"/g\" {remote_tf_dir}/main.tf'"
                )
                _ = subprocess.run(replace_net_cmd, shell=True)
        except Exception:
            pass
        
        # Step 3: Modify terraform.tfvars on remote to use local libvirt URI
        if log_callback:
            log_callback(f"[TF] Configuring local libvirt connection on manager\n")
        
        tfvars_update = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'printf \"libvirt_uri = \\\"qemu:///system\\\"\\n\" > {remote_tf_dir}/terraform.tfvars'"
        result = subprocess.run(tfvars_update, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            if log_callback:
                log_callback(f"[TF] Warning: Failed to update tfvars: {result.stderr}\n")
        
        # ========== PRE-TERRAFORM VERIFICATION & CLEANUP ==========
        if log_callback:
            log_callback("[TF] Waiting for libvirt services to stabilize (5 seconds)...\n")
        import time
        time.sleep(5)
        
        # Verify network is truly active with detailed check
        if log_callback:
            log_callback("[TF] Final network verification before Terraform...\n")
        
        detailed_net_check = (
            f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"{manager_user}@{manager_ip} 'sudo virsh -c qemu:///system net-info default 2>&1 || true; echo \"---\"; "
            f"sudo virsh -c qemu:///system net-info reef 2>&1 || true; echo \"---\"; sudo virsh -c qemu:///system net-list --all; echo \"---\"; "
            f"ip addr show virbr0 2>&1 || echo \"virbr0 not found\"; ip addr show virbr1 2>&1 || echo \"virbr1 not found\"'"
        )
        result = subprocess.run(detailed_net_check, shell=True, capture_output=True, text=True)
        if log_callback:
            log_callback(f"[TF] Network detailed check output:\n{result.stdout}\n{result.stderr}\n")
        
        # If network is still inactive, try to force activation by restarting libvirtd
        if "Active:         no" in result.stdout or "inactive" in result.stdout.lower():
            if log_callback:
                log_callback("[TF] Network is inactive, attempting to force activation...\n")
            
            # Force network activation: restart libvirtd and try to start network again
            force_activation_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo systemctl restart libvirtd && sleep 3 && sudo virsh -c qemu:///system net-start default 2>&1 || echo \"START_FAILED\" && sleep 2 && sudo virsh -c qemu:///system net-info default 2>&1'"
            result = subprocess.run(force_activation_cmd, shell=True, capture_output=True, text=True)
            if log_callback:
                log_callback(f"[TF] Force activation result:\n{result.stdout}\n")
            
            if "Active:         no" in result.stdout or "inactive" in result.stdout.lower():
                if log_callback:
                    log_callback("[TF] WARNING: Network still inactive after force activation. This may cause Terraform to fail.\n")
        
        # Clean up any VMs that terraform might create with the same name to avoid conflicts
        if log_callback:
            log_callback("[TF] Cleaning up any existing VMs with the same names...\n")
        
        # Extract VM names from the local terraform file to know what to clean up
        try:
            main_tf_path = Path(terraform_dir) / "main.tf"
            if main_tf_path.exists():
                main_tf_content = main_tf_path.read_text()
                # Find all resource "libvirt_domain" blocks to extract VM names
                import re
                vm_resources = re.findall(r'resource\s+"libvirt_domain"\s+"([^"]+)"', main_tf_content)
                
                for vm_name in vm_resources:
                    cleanup_vm_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'sudo virsh -c qemu:///system destroy {vm_name} 2>/dev/null || true; sudo virsh -c qemu:///system undefine {vm_name} --remove-all-storage 2>/dev/null || true'"
                    result = subprocess.run(cleanup_vm_cmd, shell=True, capture_output=True, text=True)
                    if log_callback:
                        log_callback(f"[TF] Cleaned up VM {vm_name}\n")
        except Exception as e:
            if log_callback:
                log_callback(f"[TF] Warning: Could not extract VM names for cleanup: {str(e)}\n")
        
        # Step 4: Run terraform init on manager
        if log_callback:
            log_callback("[TF] Running: terraform init (on manager)\n")
        
        init_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'cd {remote_tf_dir} && terraform init'"
        result = subprocess.run(init_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            if log_callback:
                log_callback(f"[TF] Init stderr: {result.stderr}\n")
            return {'success': False, 'message': f"terraform init failed: {result.stderr}"}
        
        # Step 5: Run terraform plan on manager
        if log_callback:
            log_callback("[TF] Running: terraform plan (on manager)\n")
        
        plan_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'cd {remote_tf_dir} && terraform plan -out=tfplan'"
        result = subprocess.run(plan_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            if log_callback:
                log_callback(f"[TF] Plan stderr: {result.stderr}\n")
            return {'success': False, 'message': f"terraform plan failed: {result.stderr}"}
        
        # Step 6: Run terraform apply on manager
        if log_callback:
            log_callback("[TF] Running: terraform apply (on manager)\n")
        
        apply_cmd = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'cd {remote_tf_dir} && terraform apply -auto-approve tfplan'"
        result = subprocess.run(apply_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            apply_out = (result.stdout or "") + "\n" + (result.stderr or "")
            if log_callback:
                log_callback(f"[TF] Apply failed, analyzing error...\n{apply_out}\n")
            # Auto-retry logic for low-memory hosts
            mem_err = ("Cannot allocate memory" in apply_out) or ("cannot set up guest memory" in apply_out)
            if mem_err:
                for new_mem in [512, 256]:
                    if log_callback:
                        log_callback(f"[TF] Low memory detected. Retrying with memory={new_mem} MB...\n")
                    # Reduce memory for all domains in main.tf
                    sed_cmd = (
                        f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                        f"{manager_user}@{manager_ip} 'sed -ri \"s/^[[:space:]]*memory[[:space:]]*=[[:space:]]*[0-9]+/  memory    = {new_mem}/g\" {remote_tf_dir}/main.tf'"
                    )
                    _ = subprocess.run(sed_cmd, shell=True)
                    # Re-plan and apply
                    plan_cmd_retry = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'cd {remote_tf_dir} && terraform plan -out=tfplan'"
                    result_plan = subprocess.run(plan_cmd_retry, shell=True, capture_output=True, text=True)
                    if result_plan.returncode != 0:
                        if log_callback:
                            log_callback(f"[TF] Retry plan failed: {result_plan.stderr}\n")
                        continue
                    apply_cmd_retry = f"sshpass -p '{ssh_password}' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {manager_user}@{manager_ip} 'cd {remote_tf_dir} && terraform apply -auto-approve tfplan'"
                    result_apply = subprocess.run(apply_cmd_retry, shell=True, capture_output=True, text=True)
                    if result_apply.returncode == 0:
                        if log_callback:
                            log_callback("[TF] Terraform apply succeeded after lowering memory\n")
                        return {
                            'success': True,
                            'message': 'Terraform apply successful (memory adjusted)',
                            'output': result_apply.stdout
                        }
                    else:
                        if log_callback:
                            log_callback(f"[TF] Retry apply failed: {(result_apply.stdout or '')}\n{(result_apply.stderr or '')}\n")
                        # If still memory error, continue to next lower setting
                        if not (("Cannot allocate memory" in (result_apply.stdout or "")) or ("cannot set up guest memory" in (result_apply.stderr or ""))):
                            break
                return {'success': False, 'message': 'terraform apply failed due to insufficient RAM on manager (auto-retries exhausted)'}
            return {'success': False, 'message': f"terraform apply failed: {result.stderr}"}
        
        if log_callback:
            log_callback("[TF] Terraform apply completed successfully\n")
        
        return {
            'success': True,
            'message': 'Terraform apply successful',
            'output': result.stdout
        }
    except Exception as e:
        console.print(f"[bold red]Error running Terraform:[/bold red] {e}")
        if log_callback:
            log_callback(f"[TF] Exception: {str(e)}\n")
        return {'success': False, 'message': str(e)}


def create_vm(name, image='ubuntu-22.04', size='small'):
    """
    Stub to create a VM for local development/testing.
    This function currently simulates VM creation and returns a result dict.
    Replace with real provider integration (libvirt, cloud API, terraform, etc.)
    when ready.
    """
    try:
        console.print(f"[blue]Simulating VM creation:[/blue] name={name}, image={image}, size={size}")
        import random
        ip = f"192.168.122.{random.randint(10,250)}"
        return {'success': True, 'message': 'VM created (simulated)', 'ip': ip, 'name': name}
    except Exception as e:
        return {'success': False, 'message': str(e)}
