from nicegui import ui
import os
import asyncio
from pathlib import Path
from reef.manager.core import ANSIBLE_DIR, HOSTS_INI_FILE, load_current_config, update_yaml_config_from_schema
from reef.manager.ui_utils import page_header, card_style, async_run_command, async_run_ansible_playbook

def show_deploy():
    page_header("Deploy & Manage", "Execute playbooks and manage lifecycle")
    
    with ui.tabs().classes('w-full text-slate-300') as tabs:
        tab_deploy = ui.tab('Deploy')
        tab_cleanup = ui.tab('Emergency Cleanup')

    with ui.tab_panels(tabs, value=tab_deploy).classes('w-full bg-transparent'):
        
        # --- DEPLOY TAB ---
        with ui.tab_panel(tab_deploy):
            with ui.column().classes('w-full gap-6'):
                
                # Warning
                with ui.row().classes('w-full bg-amber-500/10 border border-amber-500/20 p-4 rounded-xl items-center gap-4'):
                    ui.icon('warning', size='md').classes('text-amber-500')
                    ui.label("This will overwrite existing configurations on target servers.").classes('text-amber-500 font-bold')

                # Roles Selection
                with ui.column().classes(card_style() + ' w-full'):
                    ui.label("Enabled Components").classes('text-xl font-bold text-slate-200 mb-4')
                    
                    roles_dir = ANSIBLE_DIR / "roles"
                    all_roles = sorted([d.name for d in roles_dir.iterdir() if d.is_dir()]) if roles_dir.exists() else []
                    current_config = load_current_config()
                    enabled = current_config.get('enabled_roles', all_roles)
                    
                    selected_roles = []
                    
                    with ui.grid(columns=3).classes('w-full gap-4'):
                        for role in all_roles:
                            chk = ui.checkbox(role, value=(role in enabled)).classes('text-slate-300')
                            selected_roles.append((role, chk))
                    
                    def save_roles(notify=True):
                        new_enabled = [r for r, c in selected_roles if c.value]
                        # Must reload config to avoid overwriting unrelated concurrent edits (if any)
                        cfg = load_current_config()
                        cfg['enabled_roles'] = new_enabled
                        if update_yaml_config_from_schema(cfg):
                            if notify:
                                ui.notify("Roles updated!", type='positive')
                            
                    ui.button("Save Role Selection", on_click=save_roles).classes('mt-4 bg-slate-700')

                # Target Selection
                with ui.column().classes(card_style() + ' w-full'):
                    ui.label("Deployment Scope").classes('text-xl font-bold text-slate-200 mb-4')
                    
                    target_scope = ui.radio(['All Infrastructure', 'Manager Only', 'Specific Agent'], value='All Infrastructure').classes('text-slate-300').props('inline')
                    
                    # Parse agents for dropdown
                    agent_options = []
                    if HOSTS_INI_FILE.exists():
                        content = HOSTS_INI_FILE.read_text()
                        for line in content.splitlines():
                            line = line.strip()
                            if line and not line.startswith('#') and not line.startswith('['):
                                parts = line.split()
                                if parts:
                                    # Very basic check to exclude manager if possible, or just list all IPs
                                    # Better: check if it was under [agents]
                                    pass
                        
                        # Re-implementing a quick parser strictly for agents to populate dropdown
                        # We can reuse logic from dashboard or config if we refactor, but for now inline is safe
                        current_section = None
                        for line in content.splitlines():
                            line = line.strip()
                            if line.startswith('['):
                                current_section = line.strip('[]')
                                continue
                            
                            if current_section in ['agents', 'wazuh_agents'] and line and not line.startswith('#'):
                                parts = line.split()
                                if parts:
                                    agent_options.append(parts[0])

                    agent_select = ui.select(agent_options, label="Select Agent").classes('w-full text-slate-300')
                    agent_select.bind_visibility_from(target_scope, 'value', value='Specific Agent')

                # Deployment Action
                with ui.column().classes(card_style() + ' w-full'):
                    btn_deploy = ui.button("🚀 Start Deployment", on_click=lambda: run_deployment()).classes('bg-indigo-600 w-full py-4 text-lg')
                    credentials_container = ui.column().classes('w-full mt-4 hidden')
                    deploy_log = ui.log().classes('w-full h-64 bg-slate-900 font-mono text-xs p-4 rounded-xl border border-white/10 mt-4')

                    results_container = ui.column().classes('w-full mt-4')

            async def run_deployment():
                # Auto-save current selection before deploying
                save_roles(notify=False)
                
                deploy_log.clear()
                credentials_container.classes(add='hidden')
                credentials_container.clear()
                results_container.clear()
                btn_deploy.disable()
                

                
                playbook = ANSIBLE_DIR / "playbooks" / "experimental.yml"
                inventory = HOSTS_INI_FILE
                
                # Determine limit
                limit_arg = ""
                scope = target_scope.value
                if scope == 'Manager Only':
                    limit_arg = "-l security_server"
                elif scope == 'Specific Agent':
                    if agent_select.value:
                        limit_arg = f"-l {agent_select.value}"
                    else:
                        ui.notify("Please select an agent", type='warning')
                        btn_deploy.enable()
                        return

                cmd = f"ansible-playbook {playbook} -i {inventory} {limit_arg}"
                
                ret_code, full_output, task_results = await async_run_ansible_playbook(cmd, deploy_log)

                # Render Results Table
                if task_results:
                     with results_container:
                        ui.label("Task Execution Summary").classes('text-lg font-bold text-slate-200 mb-2')
                        
                        cols = [
                            {'name': 'host', 'label': 'Host', 'field': 'host', 'align': 'left'},
                            {'name': 'task', 'label': 'Task', 'field': 'task', 'align': 'left'},
                            {'name': 'status', 'label': 'Status', 'field': 'status', 'align': 'left'},
                        ]
                        
                        table = ui.table(columns=cols, rows=task_results, row_key='task').classes('w-full')
                        table.add_slot('body-cell-status', '''
                            <q-td :props="props">
                                <q-badge :color="props.value === 'ok' ? 'green' : (props.value === 'changed' ? 'amber' : 'red')" text-color="black">
                                    {{ props.value }}
                                </q-badge>
                            </q-td>
                        ''')

                if ret_code == 0:
                     check_credentials(full_output)
                
                btn_deploy.enable()

            def check_credentials(output):
                # Attempt to retrieve credentials
                config = load_current_config()
                manager_ip = config.get('wazuh_manager_ip', '<manager_ip>')
                
                password = None
                pass_file = ANSIBLE_DIR / 'inventory' / 'wazuh-admin-password.txt'
                
                import re
                match = re.search(r'"admin",\s+"([^"]+)"', output)
                if match:
                    password = match.group(1)
                elif pass_file.exists():
                     password = pass_file.read_text().strip().splitlines()[0] if pass_file.read_text().strip() else None
                
                # Only show if retrieved
                if password:
                    credentials_container.classes(remove='hidden')
                    with credentials_container:
                        with ui.column().classes('w-full bg-emerald-500/10 border border-emerald-500/30 p-6 rounded-xl'):
                            ui.label("🚀 System Operational").classes('text-emerald-400 text-xl font-bold mb-2')
                            ui.label("Your security stack is up and running.").classes('text-slate-300 mb-4')
                            
                            with ui.column().classes('bg-black/30 p-4 rounded-lg w-full gap-2 border border-white/10'):
                                with ui.row().classes('gap-2'):
                                    ui.label("Security Dashboard:").classes('font-bold text-slate-400')
                                    ui.link(f"http://{manager_ip}:3000/d/54540/security-dashboard", f"http://{manager_ip}:3000/d/54540/security-dashboard", new_tab=True).classes('text-sky-400 font-bold')
                                
                                with ui.row().classes('gap-2'):
                                    ui.label("Username:").classes('font-bold text-slate-400')   
                                    ui.label("admin").classes('font-mono text-slate-200 bg-white/10 px-1 rounded')

                                admin_password = "admin"
                                ui.label(f"Note: Default password is '{admin_password}'. It's recommended to change it after 1st login.").classes('text-slate-500 text-sm mt-2 italic')

                                with ui.row().classes('gap-2'):
                                    ui.label("Password:").classes('font-bold text-slate-400')
                                    ui.label(admin_password).classes('font-mono text-rose-300 font-bold bg-white/10 px-1 rounded')
                            
                            ui.label("Note: Accept the self-signed certificate warning.").classes('text-slate-500 text-sm mt-2 italic')


        # --- CLEANUP TAB ---
        with ui.tab_panel(tab_cleanup):
            with ui.column().classes('w-full gap-6'):
                with ui.row().classes('w-full bg-rose-500/10 border border-rose-500/20 p-4 rounded-xl items-center gap-4'):
                    ui.icon('dangerous', size='md').classes('text-rose-500')
                    ui.label("DANGER ZONE: This will remove all components.").classes('text-rose-500 font-bold')
                
                cleanup_log = ui.log().classes('w-full h-64 bg-slate-900 font-mono text-xs p-4 rounded-xl border border-white/10')
                
                async def run_cleanup():
                    cleanup_log.clear()
                    playbook = ANSIBLE_DIR / "playbooks" / "experimental.yml"
                    inventory = HOSTS_INI_FILE
                    
                    cmd = f"ansible-playbook {playbook} -i {inventory} -e '{{\"enabled_roles\": [\"cleanup\"]}}'"
                    await async_run_command(cmd, cleanup_log)

                ui.button("🔥 Run Cleanup (ALL HOSTS)", on_click=lambda: run_cleanup()).classes('bg-rose-600 w-full py-4 text-lg')
