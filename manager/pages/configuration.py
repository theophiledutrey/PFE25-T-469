import streamlit as st
import time
from manager.core import SchemaManager, update_yaml_config_from_schema, update_ini_inventory, load_current_config, BASE_DIR, GROUP_VARS_FILE, HOSTS_INI_FILE

def render_configuration():
    st.title("Configuration")
    st.markdown("Configure your deployment variables below. Changes are saved to `group_vars/all.yml`.")

    schema_file = BASE_DIR / "config.schema.yml"
    schema_mgr = SchemaManager(schema_file)
    categories = schema_mgr.get_categories()
    current_config = load_current_config()
    
    with st.form("config_form"):
        form_data = {}
        
        for cat_name, variables in categories.items():
            st.subheader(cat_name)
            col1, col2 = st.columns(2)
            cols = [col1, col2]
            
            for index, var in enumerate(variables):
                var_name = var['name']
                desc = var['description']
                default_val = current_config.get(var_name, var.get('default'))
                var_type = var.get('type')
                
                # Determine input widget type
                valid_col = cols[index % 2]
                
                if var_type == 'boolean':
                    val = valid_col.checkbox(desc, value=bool(default_val), help=var_name)
                elif var_type == 'integer':
                    val = valid_col.number_input(desc, value=int(default_val) if default_val is not None else 0, help=var_name)
                elif var.get('allowed_values'):
                    options = var.get('allowed_values')
                    try:
                        idx = options.index(default_val) if default_val in options else 0
                    except:
                        idx = 0
                    val = valid_col.selectbox(desc, options, index=idx, help=var_name)
                else:
                    is_password = 'password' in var_name or 'secret' in var_name
                    val = valid_col.text_input(desc, value=str(default_val) if default_val else "", type="password" if is_password else "default", help=var_name)
                
                form_data[var_name] = val
        
        # Agents Configuration
        st.markdown("---")
        st.subheader("Agent Inventory")
        st.info("Agent IPs and Credentials for `hosts.ini` generation (Required for deployment).")
        
        submitted = st.form_submit_button("Save Configuration")
        
        if submitted:
            # Validate
            errors = []
            final_data = {}
            for var_name, value in form_data.items():
                # Find the var def
                var_def = next((v for cat in categories.values() for v in cat if v['name'] == var_name), None)
                if var_def:
                    valid, res = schema_mgr.validate(var_def, value)
                    if not valid:
                        errors.append(f"{var_name}: {res}")
                    else:
                        final_data[var_name] = res
            
            if errors:
                for err in errors:
                    st.error(err)
            else:
                if update_yaml_config_from_schema(final_data):
                    st.success("Configuration saved successfully!")
                    # Reload to reflect changes
                    time.sleep(1)
                    st.rerun()

    # Dynamic Agent Input
    if GROUP_VARS_FILE.exists():
        current_config = load_current_config() # Reload fresh
        count = current_config.get('endpoint_count', 0)
        
        # Helper to parse current inventory
        existing_agents = []
        existing_mgr_user = "root"
        existing_mgr_pass = ""
        
        # Simple manual parser for Ansible INI
        if HOSTS_INI_FILE.exists():
            content = HOSTS_INI_FILE.read_text()
            lines = content.splitlines()
            in_agents = False
            for line in lines:
                line = line.strip()
                if line == "[wazuh_agents]":
                    in_agents = True
                    continue
                if line.startswith("[") and line != "[wazuh_agents]":
                    in_agents = False
                
                if in_agents and line and not line.startswith("#"):
                    parts = line.split()
                    ip = parts[0]
                    user = "root"
                    pw = ""
                    for p in parts[1:]:
                        if p.startswith("ansible_user="):
                            user = p.split("=")[1]
                        if p.startswith("ansible_ssh_pass="):
                            pw = p.split("=")[1]
                    existing_agents.append({'ip': ip, 'user': user, 'password': pw})

        if count > 0:
            st.markdown("### Agent Details")
            with st.form("agents_form"):
                agents_data = []
                
                for i in range(count):
                    st.markdown(f"**Agent {i+1}**")
                    
                    # Defaults
                    def_ip = existing_agents[i]['ip'] if i < len(existing_agents) else ""
                    def_user = existing_agents[i]['user'] if i < len(existing_agents) else "root"
                    def_pw = existing_agents[i]['password'] if i < len(existing_agents) else ""
                    
                    c1, c2, c3 = st.columns(3)
                    ip = c1.text_input(f"IP Address ##{i}", value=def_ip, key=f"agent_ip_{i}")
                    user = c2.text_input(f"SSH User ##{i}", value=def_user, key=f"agent_user_{i}")
                    pw = c3.text_input(f"SSH Password ##{i}", value=def_pw, type="password", key=f"agent_pw_{i}")
                    agents_data.append({'ip': ip, 'user': user, 'password': pw})
                
                st.markdown("---")
                # Try to find manager user/pass (simplified)
                ex_mgr_user = "root"
                ex_mgr_pw = ""
                if HOSTS_INI_FILE.exists():
                     content = HOSTS_INI_FILE.read_text()
                     lines = content.splitlines()
                     in_mgr = False
                     for line in lines:
                         if line.strip() == "[wazuh_manager]":
                             in_mgr = True
                             continue
                         if line.startswith("[") and line.strip() != "[wazuh_manager]":
                             in_mgr = False
                         
                         if in_mgr and line.strip() and not line.startswith("#"):
                             parts = line.split()
                             for p in parts:
                                 if p.startswith("ansible_user="):
                                     ex_mgr_user = p.split("=")[1]
                                 if p.startswith("ansible_ssh_pass="):
                                     ex_mgr_pw = p.split("=")[1]
                
                mgr_user = st.text_input("Manager SSH User", value=ex_mgr_user)
                mgr_pass = st.text_input("Manager SSH Password", value=ex_mgr_pw, type="password")
                
                if st.form_submit_button("Update Inventory (hosts.ini)"):
                    mgr_ip = current_config.get('wazuh_manager_ip')
                    if update_ini_inventory(mgr_ip, mgr_user, mgr_pass, agents_data):
                        st.success("Inventory updated!")
