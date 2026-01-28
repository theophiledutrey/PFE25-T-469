from nicegui import ui
from reef.manager.core import SchemaManager, update_yaml_config_from_schema, update_ini_inventory, load_current_config, BASE_DIR, GROUP_VARS_FILE, HOSTS_INI_FILE
from reef.manager.ui_utils import page_header, card_style

def show_configuration():
    page_header("Settings", "Configure your security environment")
    
    schema_file = BASE_DIR / "config.schema.yml"
    schema_mgr = SchemaManager(schema_file)
    categories = schema_mgr.get_categories()
    current_config = load_current_config()
    
    # Store form inputs
    form_inputs = {}

    async def save_config():
        final_data = {}
        errors = []
        
        for var_name, input_elem in form_inputs.items():
            value = input_elem.value
            
            # Find var def
            var_def = next((v for cat in categories.values() for v in cat if v['name'] == var_name), None)
            if var_def:
                valid, res = schema_mgr.validate(var_def, value)
                if not valid:
                    errors.append(f"{var_name}: {res}")
                else:
                    final_data[var_name] = res
        
        if errors:
            for err in errors:
                ui.notify(err, type='negative')
        else:
            if update_yaml_config_from_schema(final_data):
                ui.notify("Configuration saved successfully!", type='positive')
                # Refresh page to update the Agent Inventory section based on new config
                ui.timer(1.0, lambda: ui.run_javascript('window.location.reload()'), once=True)

    # --- Main Config Form ---
    with ui.column().classes('w-full gap-8'):
        
        for cat_name, variables in categories.items():
            with ui.column().classes(card_style() + ' w-full'):
                ui.label(cat_name).classes('text-xl font-bold text-slate-200 mb-4')
                
                with ui.grid(columns=2).classes('w-full gap-6'):
                    for var in variables:
                        var_name = var['name']
                        desc = var['description']
                        default_val = current_config.get(var_name, var.get('default'))
                        var_type = var.get('type')
                        
                        if var_type == 'boolean':
                            form_inputs[var_name] = ui.checkbox(desc, value=bool(default_val)).classes('text-slate-300')
                        
                        elif var_type == 'integer':
                            form_inputs[var_name] = ui.number(desc, value=int(default_val) if default_val is not None else 0).classes('w-full text-slate-300')
                        
                        elif var.get('allowed_values'):
                            options = var.get('allowed_values')
                            form_inputs[var_name] = ui.select(options, value=default_val, label=desc).classes('w-full text-slate-300')
                        
                        else:
                            is_password = 'password' in var_name or 'secret' in var_name
                            form_inputs[var_name] = ui.input(desc, value=str(default_val) if default_val else "", password=is_password).classes('w-full text-slate-300')

        ui.button("Save Settings", on_click=save_config).classes('bg-indigo-600 w-full')

    # --- Agents Inventory Section ---
    ui.separator().classes('my-8 bg-slate-700')
    
    with ui.column().classes(card_style() + ' w-full'):
        ui.label("Computer Inventory").classes('text-xl font-bold text-slate-200 mb-2')
        ui.markdown("List the computers you want to protect. You need to provide their IP address and login credentials so the system can install the necessary software.").classes('text-slate-400 mb-6')

        if GROUP_VARS_FILE.exists():
            # Reload to get fresh count if it changed
            fresh_config = load_current_config()
            count = fresh_config.get('endpoint_count', 0)
            
            # Helper to parse current inventory
            existing_agents = []
            existing_manager = {'user': 'root', 'password': '', 'key': ''}

            if HOSTS_INI_FILE.exists():
                content = HOSTS_INI_FILE.read_text()
                lines = content.splitlines()
                current_section = None
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if line.startswith('['):
                        current_section = line.strip('[]')
                        continue
                    
                    parts = line.split()
                    if not parts:
                        continue

                    # Parse common ansible vars
                    ip = parts[0]
                    user = "root"
                    pw = ""
                    key = ""
                    
                    for p in parts[1:]:
                        if p.startswith("ansible_user="):
                            user = p.split("=", 1)[1]
                        elif p.startswith("ansible_ssh_pass=") or p.startswith("ansible_password="):
                            pw = p.split("=", 1)[1]
                        elif p.startswith("ansible_ssh_private_key_file="):
                            key = p.split("=", 1)[1]

                    if current_section in ['agents', 'wazuh_agents']:
                        existing_agents.append({'ip': ip, 'user': user, 'password': pw, 'key': key})
                    elif current_section == 'security_server':
                        existing_manager['user'] = user
                        existing_manager['password'] = pw
                        existing_manager['key'] = key

            if count > 0:
                agent_inputs = []
                
                with ui.column().classes('gap-4 w-full'):
                    for i in range(count):
                        ui.label(f"Computer {i+1}").classes('font-bold text-slate-300 mt-2')
                        
                        def_ip = existing_agents[i]['ip'] if i < len(existing_agents) else ""
                        def_user = existing_agents[i]['user'] if i < len(existing_agents) else "root"
                        def_pw = existing_agents[i]['password'] if i < len(existing_agents) else ""
                        def_key = existing_agents[i]['key'] if i < len(existing_agents) else ""
                        
                        with ui.grid(columns=4).classes('w-full gap-4'):
                            ip_in = ui.input("IP Address", value=def_ip).classes('w-full')
                            user_in = ui.input("SSH User", value=def_user).classes('w-full')
                            pw_in = ui.input("SSH Password", value=def_pw, password=True).classes('w-full')
                            key_in = ui.input("SSH Key Path", value=def_key).classes('w-full')
                            
                            agent_inputs.append({'ip': ip_in, 'user': user_in, 'pw': pw_in, 'key': key_in})
                    
                    ui.separator().classes('my-4 bg-white/10')
                    
                    # Manager Credentials
                    ex_mgr_user = existing_manager['user']
                    ex_mgr_pw = existing_manager['password']
                    ex_mgr_key = existing_manager['key']
                        
                    with ui.grid(columns=4).classes('w-full gap-4'):
                        mgr_user_in = ui.input("Security Server User", value=ex_mgr_user).classes('w-full')
                        mgr_pass_in = ui.input("Security Server Password", value=ex_mgr_pw, password=True).classes('w-full')
                        mgr_key_in = ui.input("Security Server Key Path", value=ex_mgr_key).classes('w-full')

                    def save_inventory():
                        # Collect data
                        agents_data = []
                        for row in agent_inputs:
                            agents_data.append({
                                'ip': row['ip'].value,
                                'user': row['user'].value,
                                'password': row['pw'].value,
                                'key': row['key'].value
                            })
                        
                        mgr_ip = fresh_config.get('wazuh_manager_ip')
                        if update_ini_inventory(mgr_ip, mgr_user_in.value, mgr_pass_in.value, mgr_key_in.value, agents_data):
                            ui.notify("Inventory updated!", type='positive')

                    ui.button("Save Computer List", on_click=save_inventory).classes('bg-emerald-600 w-full mt-4')
            else:
                 ui.label("Set 'endpoint_count' > 0 in configuration above to configure agents.").classes('text-amber-400')
