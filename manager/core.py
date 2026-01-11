import os
import subprocess
import sys
import re
from pathlib import Path
from ruamel.yaml import YAML
from rich.console import Console

# Initialize Rich Console (Needed for logging in legacy functions)
console = Console()
VERBOSE_MODE = False

BASE_DIR = Path(__file__).parent.parent.resolve()
ANSIBLE_DIR = BASE_DIR / "ansible"
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
                    executable='/bin/zsh',
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
                executable='/bin/zsh',
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

def update_ini_inventory(manager_ip, manager_user, manager_password, agents_data):
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
                if vars_str:
                    match = re.search(r'ansible_user=(\S+)', vars_str)
                    if match:
                        user = match.group(1)
                
                hosts.append({'ip': ip, 'user': user})

        parse_section('security_server')
        parse_section('agents')

    except Exception as e:
        console.print(f"[red]Error parsing inventory:[/red] {e}")
        return []

    return hosts
