import reef.click
import os
import subprocess
import sys
import re
import time
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.align import Align
from pathlib import Path
from ruamel.yaml import YAML

# Initialize Rich Console
console = Console()
VERBOSE_MODE = False

# Configuration Paths
# Configuration Paths
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
        env['ANSIBLE_CONFIG'] = str(ANSIBLE_DIR / "ansible.cfg")
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
        
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

def run_ansible_with_progress(command, cwd=BASE_DIR, total_tasks=100):
    """
    Run ansible-playbook with a progress bar.
    Parses output to advance progress on "TASK [...]" lines.
    """
    if VERBOSE_MODE:
        return run_command(command, cwd=cwd, quiet=False)

    try:
        env = os.environ.copy()
        env['ANSIBLE_CONFIG'] = str(ANSIBLE_DIR / "ansible.cfg")
        env['ANSIBLE_ROLES_PATH'] = str(ANSIBLE_DIR / "roles")
        
        process = subprocess.Popen(
            command,
            cwd=cwd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            executable='/bin/bash',
            env=env
        )
        
        task_pattern = re.compile(r'TASK \[(.*)\]')
        
        with Progress(
            SpinnerColumn("dots", style="green"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="green"),
            TextColumn("{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            # Initial setup with fixed width buffer
            task_id = progress.add_task(f"[cyan]Task: {'Working...':<30}", total=total_tasks)
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if line:
                    match = task_pattern.search(line)
                    if match:
                        task_name = match.group(1).strip()
                        max_len = 30
                        # Truncate if too long
                        if len(task_name) > max_len:
                            task_name = task_name[:max_len-3] + "..."
                        
                        # Update with padded string for fixed width
                        progress.update(task_id, advance=1, description=f"[cyan]Task: {task_name:<{max_len}}")
                        
        if process.poll() != 0:
             console.print(f"[bold red]Ansible failed with exit code {process.returncode}[/bold red]")
             console.print("[dim]Last 20 lines of output:[/dim]")
             # We can't easily get the full output here because we consumed it in the loop.
             # But we can try to rely on the fact that we displayed tasks.
             # A better approach for error reporting is to capture lines in a deque.
             return False
        
        console.print("[bold green]Operation complete![/bold green]")
        return True

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation cancelled by user.[/bold yellow]")
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            process.kill()
        return False

    except Exception as e:
        console.print(f"[bold red]Error running ansible:[/bold red] {e}")
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

def update_ini_inventory(manager_ip, manager_user, manager_password, agents_data):
    """Update ansible/inventory/hosts.ini using regex to preserve structure."""
    if not HOSTS_INI_FILE.exists():
        try:
            HOSTS_INI_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(HOSTS_INI_FILE, 'w') as f:
                f.write("[security_server]\n")
                if manager_ip:
                     entry = f"{manager_ip} ansible_user={manager_user or 'root'}"
                     if manager_password:
                         entry += f" ansible_password={manager_password} ansible_become_password={manager_password}"
                     f.write(f"{entry}\n")
                
                f.write("\n[agents]\n")
                for agent in agents_data:
                    entry = f"{agent['ip']}"
                    if agent['user']:
                        entry += f" ansible_user={agent['user']}"
                    if agent['password']:
                        entry += f" ansible_password={agent['password']} ansible_become_password={agent['password']}"
                    f.write(f"{entry}\n")
            
            console.print(f"[green]Created {HOSTS_INI_FILE}[/green]")
            return True
        except Exception as e:
            console.print(f"[bold red]Failed to create INI inventory:[/bold red] {e}")
            return False

    try:
        with open(HOSTS_INI_FILE, 'r') as f:
            lines = f.readlines()

        new_lines = []
        ip_pattern = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(\s+.*)$')
        
        # State tracking
        current_section = None
        agents_section_found = False
        in_agents_section = False
        
        for line in lines:
            stripped = line.strip()
            
            # Detect section headers
            if stripped.startswith('[') and stripped.endswith(']'):
                current_section = stripped
                
                # If we hit the agents section
                if current_section == '[agents]':
                    agents_section_found = True
                    in_agents_section = True
                    
                    # Write the header
                    new_lines.append("[agents]\n")
                    
                    # Write all agent IPs
                    for agent in agents_data:
                        entry = f"{agent['ip']}"
                        if agent['user']:
                            entry += f" ansible_user={agent['user']}"
                        if agent['password']:
                            entry += f" ansible_password={agent['password']} ansible_become_password={agent['password']}"
                        new_lines.append(f"{entry}\n")
                    
                    # Skip the line that was the header (we just wrote it)
                    continue
                else:
                    in_agents_section = False
            
            # If we are currently inside the old agents section, skip every line until next section
            if in_agents_section:
                continue

            # Update Security Server IP
            if current_section == '[security_server]' and ip_pattern.match(line):
                match = ip_pattern.match(line)
                rest = match.group(2)
                if manager_user:
                    rest = re.sub(r'ansible_user=\S+', f'ansible_user={manager_user}', rest)
                if manager_password:
                    # Update password
                    if 'ansible_password=' in rest:
                        rest = re.sub(r'ansible_password=\S+', f'ansible_password={manager_password}', rest)
                    else:
                        rest += f" ansible_password={manager_password}"
                    
                    # Update become password
                    if 'ansible_become_password=' in rest:
                         rest = re.sub(r'ansible_become_password=\S+', f'ansible_become_password={manager_password}', rest)
                    else:
                        rest += f" ansible_become_password={manager_password}"

                new_lines.append(f"{manager_ip}{rest}\n")
            else:
                new_lines.append(line)

        # If [agents] section was never found, append it at the end
        if not agents_section_found:
             if new_lines and new_lines[-1].strip() != "":
                 new_lines.append("\n")
             new_lines.append("[agents]\n")
             for agent in agents_data:
                entry = f"{agent['ip']}"
                if agent['user']:
                    entry += f" ansible_user={agent['user']}"
                if agent['password']:
                    entry += f" ansible_password={agent['password']} ansible_become_password={agent['password']}"
                new_lines.append(f"{entry}\n")

        with open(HOSTS_INI_FILE, 'w') as f:
            f.writelines(new_lines)
            
        console.print(f"[green]Successfully updated {HOSTS_INI_FILE}[/green]")
        return True

    except Exception as e:
        console.print(f"[bold red]Failed to update INI inventory:[/bold red] {e}")
        return False

def get_inventory_hosts():
    """
    Parse hosts.ini to find all configured hosts in [security_server] and [agents].
    Returns a list of dicts: [{'ip': '...', 'user': '...'}]
    """
    if not HOSTS_INI_FILE.exists():
        return []

    hosts = []
    try:
        with open(HOSTS_INI_FILE, 'r') as f:
            lines = f.readlines()

        current_section = None
        ip_pattern = re.compile(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(\s+.*)?$')
        
        for line in lines:
            line = line.strip()
            if line.startswith('[') and line.endswith(']'):
                current_section = line
                continue
            
            if current_section in ['[security_server]', '[agents]']:
                match = ip_pattern.match(line)
                if match:
                    ip = match.group(1)
                    rest = match.group(2) or ""
                    user = "root" # Default
                    
                    user_match = re.search(r'ansible_user=(\S+)', rest)
                    if user_match:
                        user = user_match.group(1)
                    
                    hosts.append({'ip': ip, 'user': user})
    except Exception as e:
        console.print(f"[red]Error parsing inventory:[/red] {e}")
        return []

    return hosts

@click.group(invoke_without_command=True, epilog="For more information, visit the documentation.")
@click.option('--verbose/--no-verbose', '-v', default=False, help="Enable verbose output for debugging.")
@click.pass_context
def cli(ctx, verbose):
    """
    PME Security Infrastructure Manager (REEF)
    
    A CLI tool to manage the deployment, configuration, and maintenance
    of the PME security infrastructure (Wazuh, Suricata, Fail2Ban).
    """
    global VERBOSE_MODE
    VERBOSE_MODE = verbose
    
    if ctx.invoked_subcommand is None:
        menu()

from rich.text import Text
from rich.table import Table

def role_management_menu():
    """Interactive Role Management Menu"""
    while True:
        console.clear()
        console.print(Panel("[bold magenta]Role Management[/bold magenta]", subtitle="Enable/Disable Security Components"))
        
        current_config = load_current_config()
        enabled_roles = current_config.get('enabled_roles', [])
        
        console.print(f"Current Enabled Roles: [green]{', '.join(enabled_roles)}[/green]\n")
        
        console.print("1. [bold]View Available Roles[/bold]")
        console.print("2. [bold]Enable/Disable Roles[/bold]")
        console.print("3. [bold]Validate Role Dependencies[/bold]")
        console.print("0. [bold]Back to Main Menu[/bold]")
        
        choice = Prompt.ask("Select option", choices=["0", "1", "2", "3"], default="0")
        
        if choice == "0":
            return
        elif choice == "1":
            view_available_roles()
        elif choice == "2":
            toggle_roles_interactive(current_config)
        elif choice == "3":
            validate_roles_interactive()
            
        if not Confirm.ask("\nReturn to Role Menu?", default=True):
            return

def view_available_roles():
    """List all available roles in roles/ directory with descriptions."""
    roles_dir = ANSIBLE_DIR / "roles"
    if not roles_dir.exists():
        console.print("[red]Roles directory not found![/red]")
        return

    table = Table(title="Available Roles")
    table.add_column("Role Name", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Description")

    yaml = YAML()
    found_roles = [d.name for d in roles_dir.iterdir() if d.is_dir()]
    
    for role in sorted(found_roles):
        meta_file = roles_dir / role / "meta" / "reef.yml"
        category = "Custom"
        description = "User defined role"
        
        if meta_file.exists():
            try:
                with open(meta_file, 'r') as f:
                    data = yaml.load(f) or {}
                    role_info = data.get('role_info', {})
                    category = role_info.get('category', category)
                    description = role_info.get('description', description)
            except Exception:
                pass # Fallback to defaults on error
        
        table.add_row(role, category, description)
        
    console.print(table)

def toggle_roles_interactive(current_config):
    """Checkbox-style selection for roles."""
    # We use a simple loop prompt for stability without adding more deps.
    
    roles_dir = ANSIBLE_DIR / "roles"
    if roles_dir.exists():
        all_known_roles = sorted([d.name for d in roles_dir.iterdir() if d.is_dir()])
    else:
        all_known_roles = ['common', 'ufw', 'fail2ban', 'wazuh-agent', 'wazuh-server', 'wazuh-indexer', 'wazuh-dashboard', 'suricata', 'cleanup']
        
    enabled = set(current_config.get('enabled_roles', []))
    
    while True:
        console.clear()
        console.print("[bold]Toggle Roles[/bold] (Type number to toggle, or 'done' to save)")
        
        for idx, role in enumerate(all_known_roles, 1):
            if role in enabled:
                status = "[green][ENABLED][/green] "
            else:
                status = "[dim][OFF]    [/dim] "
            console.print(f"{idx}. {status} {role}")
            
        choice = Prompt.ask("Toggle role # or 'done'", default="done")
        
        if choice.lower() == 'done':
            break
            
        try:
            idx = int(choice)
            if 1 <= idx <= len(all_known_roles):
                role = all_known_roles[idx-1]
                if role in enabled:
                    enabled.remove(role)
                    # Strict Coupling: OFF Logic
                    if role == 'wazuh-server' and 'wazuh-indexer' in enabled:
                         enabled.remove('wazuh-indexer')
                         console.print("[yellow]Auto-disabling wazuh-indexer (coupled with wazuh-server)[/yellow]")
                         time.sleep(1)
                    if role == 'wazuh-indexer' and 'wazuh-server' in enabled:
                        enabled.remove('wazuh-server')
                        console.print("[yellow]Auto-disabling wazuh-server (coupled with wazuh-indexer)[/yellow]")
                        time.sleep(1)

                else:
                    enabled.add(role)
                    # Strict Coupling: ON Logic
                    if role == 'wazuh-indexer' and 'wazuh-server' not in enabled:
                        enabled.add('wazuh-server')
                        console.print("[green]Auto-enabling wazuh-server (coupled with wazuh-indexer)[/green]")
                        time.sleep(1)
                    if role == 'wazuh-server' and 'wazuh-indexer' not in enabled:
                        enabled.add('wazuh-indexer')
                        console.print("[green]Auto-enabling wazuh-indexer (coupled with wazuh-server)[/green]")
                        time.sleep(1)
            else:
                console.print("[red]Invalid index[/red]")
                time.sleep(1)
        except ValueError:
            pass

    if Confirm.ask("Save changes to enabled_roles?"):
        current_config['enabled_roles'] = list(enabled)
        # We reuse the existing update function which handles the file write
        update_yaml_config_from_schema(current_config)

def validate_roles_interactive():
    """Run the check_dependencies.yml task locally."""
    console.print("[bold blue]Checking dependencies...[/bold blue]")
    # We can run ansible-playbook with just that task file on localhost or just dry-run the main playbook
    # A dry run of experimental.yml is better as it checks everything
    
    playbook = ANSIBLE_DIR / "playbooks" / "experimental.yml"
    inventory = HOSTS_INI_FILE
    
    cmd = f"ansible-playbook {playbook} -i {inventory} --check --tags never" 
    # Actually, we want to run the dependency check task. 
    # But that task is inside the playbook.
    # Let's just run the playbook in check mode, restricted to localhost if possible, but our playbook targets real hosts.
    # Alternatively, run a specific command to just verify variables.
    
    # Let's try running just the dependency check file via a temporary ad-hoc playbook approach or just assume dry-run is enough.
    # We can create a temporary playbook for validation?
    # Or just rely on the user running 'deploy' to fail fast.
    
    # Better: Run `ansible-playbook -i ... experimental.yml --list-tasks` does not check logic.
    # Let's run a dry run.
    if Confirm.ask("Run full playbook dry-run (check mode) to validate?"):
        cmd = f"ansible-playbook {playbook} -i {inventory} --check"
        run_ansible_with_progress(cmd, total_tasks=20)


def menu():
    """Interactive Menu"""
    while True:
        try:
            console.clear()
            ascii_art = """    
           ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣶⠾⠿⠿⠯⣷⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣼⣾⠛⠁⠀⠀⠀⠀⠀⠀⠈⢻⣦⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣾⠿⠁⠀⠀⠀⢀⣤⣾⣟⣛⣛⣶⣬⣿⣆⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣾⠟⠃⠀⠀⠀⠀⠀⣾⣿⠟⠉⠉⠉⠉⠛⠿⠟⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
     ⠀⠀⠀⠀⠀⠀⢀⣴⡟⠋⠀⠀⠀⠀⠀⠀⠀⣿⡏⣤⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
      ⠀⠀⠀⠀⣠⡿⠛⠀⠀⠀⠀⠀⠀⠀⠀⠀⠙⣷⡍⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣀⣀⣤⣤⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
       ⠀⣠⣼⡏⠀⠀⠀⠀     ⠀⠀⠀⠈⠙⠷⣤⣤⣠⣤⣤⡤⡶⣶⢿⠟⠹⠿⠄⣿⣿⠏⠀⣀⣤⡦⠀⠀⠀⠀⣀⡄
   ⢀⣄⣠⣶⣿⠏⠀⠀⠀⠀            ⠀⠀⠈⠉⠓⠚⠋⠉⠀⠀⠀⠀⠀⠀⠈⠛⡛⡻⠿⠿⠙⠓⢒⣺⡿⠋⠁
   ⠉⠉⠉⠛⠁⠀⠀⠀⠀⠀⠀       ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠉⠁⠀
            """
            console.print(Align.center(Text(ascii_art, style="bold cyan")))
            console.print(Panel(Align.center("[bold white on blue]  REEF  [/bold white on blue]"), subtitle="Automatic Security Infrastructure Manager"))
            console.print(f"Verbose Mode: {'[green]ON[/green]' if VERBOSE_MODE else '[dim]OFF[/dim]'}")
            console.print("1. [bold green]Configure Deployment[/bold green] (Set IPs & User)")
            console.print("2. [bold cyan]Run Prerequisites Check[/bold cyan]")
            console.print("3. [bold yellow]Deploy / Start[/bold yellow]")
            console.print("4. [bold magenta]Role Management[/bold magenta]")
            console.print("5. [bold red]Emergency Cleanup[/bold red]")
            console.print("6. [bold]View Documentation[/bold]")
            console.print("0. [bold]Exit[/bold]")
            
            choice = Prompt.ask("Enter action [0/1/2/3/4/5/6]", choices=["0", "1", "2", "3", "4", "5", "6"], default="0", show_choices=False)
            
            if choice == "0":
                console.print("Goodbye!")
                sys.exit(0)
            elif choice == "1":
                configure_interactive()
            elif choice == "2":
                check_interactive()
            elif choice == "3":
                deploy.callback()
            elif choice == "4":
                role_management_menu()
            elif choice == "5":
                cleanup.callback()
            elif choice == "6":
                view_guide()
            
            if not Confirm.ask("\nReturn to menu?", default=True):
                sys.exit(0)
                
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Cancelled. Returning to menu...[/bold yellow]")
            time.sleep(0.5)
            continue

from rich.markdown import Markdown

def view_guide():
    console.print(Panel("[bold]Documentation Viewer[/bold]"))
    docs_map = {
        "1": ("User Manual", BASE_DIR / "docs" / "user-manual.md"),
        "2": ("Installation Guide", BASE_DIR / "docs" / "installation-guide.md"),
        "3": ("Architecture", BASE_DIR / "docs" / "architecture.md"),
        "4": ("README", BASE_DIR / "README.md")
    }
    
    console.print("Select a document to view:")
    for key, (name, _) in docs_map.items():
        console.print(f"{key}. {name}")
    console.print("0. Back")
    
    choice = Prompt.ask("Select document", choices=["0", "1", "2", "3", "4"], default="1")
    
    if choice == "0":
        return
        
    name, path = docs_map[choice]
    if path.exists():
        with console.pager():
            console.print(Markdown(path.read_text()))
    else:
        console.print(f"[bold red]Error:[/bold red] Document not found at {path}")

def check_interactive():
    console.print(Panel("[bold]Prerequisites Check[/bold]"))
    mode = Prompt.ask("Check mode", choices=["local", "remote"], default="local")
    
    if mode == "local":
        check.callback(ip=None, user=None)
    else:
        # Auto-detect hosts from inventory
        hosts = get_inventory_hosts()
        
        if hosts:
            console.print(f"[green]Found {len(hosts)} hosts in inventory.[/green]")
            for host in hosts:
                 check.callback(ip=host['ip'], user=host['user'])
        else:
            console.print("[yellow]No hosts found in inventory. Switching to manual input.[/yellow]")
            ip = Prompt.ask("Remote IP")
            user = Prompt.ask("SSH User", default="root")
            check.callback(ip=ip, user=user)

def configure_interactive():
    console.print(Panel("[bold]Configuration Wizard (Schema Driven)[/bold]"))
    
    schema_mgr = SchemaManager(SCHEMA_FILE)
    categories = schema_mgr.get_categories()
    current_config = load_current_config()
    new_config = {}

    # 1. General Configuration from Schema
    for cat_name, variables in categories.items():
        console.print(f"\n[bold cyan]--- {cat_name} ---[/bold cyan]")
        for var in variables:
            var_name = var['name']
            description = var['description']
            default_val = current_config.get(var_name, var.get('default'))
            
            while True:
                # Format default for display
                default_display = str(default_val)
                
                user_input = Prompt.ask(f"{description} ([dim]{var_name}[/dim])", default=default_display)
                
                valid, result = schema_mgr.validate(var, user_input)
                if valid:
                    new_config[var_name] = result
                    break
                else:
                    console.print(f"[red]{result}[/red]")

    # 2. Agent Inventory Configuration (Special Case, kept separate for now as it touches hosts.ini)
    # Check if we need to configure agents based on endpoint_count
    endpoint_count = new_config.get('endpoint_count', 1)
    
    # Still need manager user for hosts.ini update 
    manager_user = Prompt.ask("Wazuh Manager SSH User (for inventory)", default="root")
    manager_password = Prompt.ask("Wazuh Manager SSH Password", password=True)
    manager_ip = new_config.get('wazuh_manager_ip')

    agents_data = []
    if endpoint_count > 0:
        console.print(f"\n[bold]Enter details for {endpoint_count} agents (for inventory):[/bold]")
        last_user = "root"
        for i in range(1, endpoint_count + 1):
            console.print(f"  [cyan]Agent {i}[/cyan]")
            ip = Prompt.ask(f"    IP")
            user = Prompt.ask(f"    SSH User", default=last_user)
            password = Prompt.ask(f"    SSH Password", password=True)
            last_user = user
            agents_data.append({'ip': ip, 'user': user, 'password': password})

    if Confirm.ask("Save these settings?"):
        # Ensure enabled_roles has a default if missing from current config
        if 'enabled_roles' not in current_config:
             roles_dir = ANSIBLE_DIR / "roles"
             if roles_dir.exists():
                 default_roles = sorted([d.name for d in roles_dir.iterdir() if d.is_dir()])
             else:
                 default_roles = ['common', 'ufw', 'fail2ban', 'wazuh-agent', 'wazuh-server', 'wazuh-indexer', 'wazuh-dashboard', 'suricata', 'cleanup']
             new_config['enabled_roles'] = default_roles

        # Update group_vars/all.yml
        update_yaml_config_from_schema(new_config)
        
        # Update hosts.ini
        if manager_ip:
            update_ini_inventory(manager_ip, manager_user, manager_password, agents_data)
        
        Prompt.ask("Configuration updated. Press Enter to continue...")

@cli.command()
def configure():
    """Start the interactive configuration wizard to set up variables."""
    configure_interactive()

@cli.command()
@click.option('--ip', help='Target IP for remote check')
@click.option('--user', default='root', help='SSH User for remote check')
def check(ip, user):
    """
    Verify system prerequisites on local or remote targets.
    
    Checks for supported OS, RAM, disk space, and required ports including:
    - 443 (Dashboard)
    - 1514/1515 (Wazuh Registration/Events)
    - 9200 (Indexer)
    """
    script_path = SCRIPTS_DIR / "prerequisites-check.sh"
    
    if ip:
        console.print(f"[bold blue]Running remote check on {user}@{ip}...[/bold blue]")
        remote_path = "/tmp/pme_prerequisites_check.sh"
        
        # Use connection multiplexing to avoid double password prompt
        ssh_opts = "-o ControlMaster=auto -o ControlPersist=60s -o ControlPath=/tmp/reef-ssh-%r@%h:%p"
        
        # 1. Copy script to remote
        if run_command(f"scp {ssh_opts} {script_path} {user}@{ip}:{remote_path}"):
            # 2. Execute with sudo (using -t to allow password prompt)
            # We chain the removal of the script to ensure cleanup
            cmd = f"ssh {ssh_opts} -t {user}@{ip} 'sudo bash {remote_path}; sudo rm {remote_path}'"
            run_command(cmd)
    else:
        run_command(f"{script_path}")

@cli.command()
def deploy():
    """
    Execute the Ansible playbook to deploy the security stack.
    
    This command runs the 'experimental.yml' playbook using variables
    from the configuration step. It handles:
    - Firewall setup (UFW)
    - Wazuh Manager/Indexer/Dashboard installation
    - Client agent deployment
    """
    playbook = ANSIBLE_DIR / "playbooks" / "experimental.yml"
    inventory = HOSTS_INI_FILE
    
    if not GROUP_VARS_FILE.exists() or not HOSTS_INI_FILE.exists():
        console.print("[yellow]Configuration and hosts inventory not found. Launching configuration wizard...[/yellow]")
        configure_interactive()
        
        # If user cancelled configuration (Ctrl+C or didn't save), we might still not have a file.
        if not GROUP_VARS_FILE.exists() or not HOSTS_INI_FILE.exists():
             console.print("[red]Configuration aborted. Deployment cannot proceed without configuration.[/red]")
             return

    # Check for enabled_roles before deploying
    current_config = load_current_config()
    if 'enabled_roles' not in current_config:
        console.print("[yellow]Warning: 'enabled_roles' not found in configuration. Initializing with ALL roles.[/yellow]")
        roles_dir = ANSIBLE_DIR / "roles"
        if roles_dir.exists():
            default_roles = sorted([d.name for d in roles_dir.iterdir() if d.is_dir()])
        else:
             default_roles = ['common', 'ufw', 'fail2ban', 'wazuh-agent', 'wazuh-server', 'wazuh-indexer', 'wazuh-dashboard', 'suricata', 'cleanup']
        
        current_config['enabled_roles'] = default_roles
        update_yaml_config_from_schema(current_config)

    if Confirm.ask(f"Ready to deploy? The action is irreversible", default=True):
        cmd = f"ansible-playbook {playbook} -i {inventory}"
        # Use progress bar unless verbose. Estimate ~110 tasks based on full playbook.
        if run_ansible_with_progress(cmd, total_tasks=110):
            show_post_deployment_msg()

def show_post_deployment_msg():
    """Display success message with credentials."""
    yaml = YAML()
    manager_ip = "Unknown"
    
    if GROUP_VARS_FILE.exists():
        try:
            with open(GROUP_VARS_FILE, 'r') as f:
                data = yaml.load(f)
                manager_ip = data.get('wazuh_manager_ip', "Unknown")
        except:
            pass

    password_file = INVENTORY_DIR / "wazuh-admin-password.txt"
    password = "See wazuh-admin-password.txt"
    
    if password_file.exists():
        try:
            content = password_file.read_text().strip()
            # Check if file contains the key-value structure or just the password
            if "indexer_username" in content:
                # Regex to find admin password in the provided format
                match = re.search(r"indexer_username:\s*'admin'.*?indexer_password:\s*'([^']+)'", content, re.DOTALL)
                if match:
                    password = match.group(1)
                else:
                    password = "Password not found (check format)"
            else:
                # Assume raw password
                password = content
        except Exception as e:
            password = f"Error reading file: {e}"
            
    console.print(Panel(
        f"[bold green]Operation Successful![/bold green]\n\n"
        f"Access Wazuh Dashboard at: [link=https://{manager_ip}/app/login?]https://{manager_ip}/app/login?[/link]\n"
        f"User: [bold]admin[/bold]\n"
        f"Password: [bold]{password}[/bold]",
        subtitle=f"(Information has been saved to [blue]{password_file}[/blue])",
        title="Operation Summary",
        border_style="green"
    ))# https://192.168.64.12/app/login?next=%2Fapp%2Fdashboard

@cli.command()
def cleanup():
    """
    Remove all installed components and reset configuration (Destructive).
    
    Runs the 'cleanup' tag in the playbook to uninstall:
    - Wazuh components
    - Suricata
    - Fail2ban
    - UFW rules
    """
    if Confirm.ask("[bold red]WARNING: This will remove all installed components. Continue?[/bold red]", default=False):
        playbook = ANSIBLE_DIR / "playbooks" / "experimental.yml"
        inventory = HOSTS_INI_FILE
        cmd = f"ansible-playbook {playbook} -i {inventory} -e '{{\"enabled_roles\": [\"cleanup\"]}}'"
        # Use progress bar with accurate estimated tasks for cleanup (approx 44-50)
        run_ansible_with_progress(cmd, total_tasks=50)

if __name__ == "__main__":
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[bold red]Aborted.[/bold red]")
        sys.exit(130)
