import streamlit as st
from manager.core import GROUP_VARS_FILE, HOSTS_INI_FILE, load_current_config

def render_dashboard():
    st.markdown("<h1>Welcome to <span style='background: linear-gradient(90deg, #4f46e5, #06b6d4); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>REEF</span></h1>", unsafe_allow_html=True)
    st.markdown("### Security Infrastructure Manager")
    
    st.markdown("""<p style="color: #94a3b8; font-size: 1.1em; line-height: 1.6; margin-top: -10px;">
REEF simplifies the deployment of your security stack. 
Automate SIEM, IDS, and network defenses with a unified management interface.
</p>""", unsafe_allow_html=True)
    
    st.markdown("---")
    
    if GROUP_VARS_FILE.exists():
        config = load_current_config()
        manager_ip = config.get('wazuh_manager_ip', 'Unknown')
        enabled_roles = config.get('enabled_roles', [])
        
        # Count actual configured agents from inventory
        agent_ips = []
        if HOSTS_INI_FILE.exists():
            content = HOSTS_INI_FILE.read_text()
            lines = content.splitlines()
            in_agents = False
            for line in lines:
                if line.strip() == "[agents]" or line.strip() == "[wazuh_agents]":
                    in_agents = True
                    continue
                if line.strip().startswith("[") and line.strip() not in ["[agents]", "[wazuh_agents]"]:
                    in_agents = False
                
                if in_agents and line.strip() and not line.strip().startswith("#"):
                    parts = line.strip().split()
                    if parts:
                        agent_ips.append(parts[0])

        agent_count = len(agent_ips)
        status_text = "Active" if HOSTS_INI_FILE.exists() else "Pending Setup"
        status_color = "#34d399" if HOSTS_INI_FILE.exists() else "#fbbf24"
        
        # UI Layout
        col1, col2 = st.columns([1, 1.2])
        
        with col1:
            # Overview Card
            st.markdown(f"""<div class="css-card">
<h4 style="margin-top:0; color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 15px;">Core Infrastructure</h4>
<div style="display: flex; flex-direction: column; gap: 20px;">
<div style="display: flex; justify-content: space-between; align-items: center;">
<div>
<div style="color: #64748b; font-size: 0.8em; text-transform: uppercase;">System Status</div>
<div style="color: {status_color}; font-weight: 600; font-size: 1.1em;">● {status_text}</div>
</div>
<div style="text-align: right;">
<div style="color: #64748b; font-size: 0.8em; text-transform: uppercase;">Manager Node</div>
<div style="font-family: monospace; color: #cbd5e1; background: rgba(255,255,255,0.05); padding: 4px 8px; border-radius: 4px;">{manager_ip}</div>
</div>
</div>
<div style="background: rgba(56, 189, 248, 0.05); border: 1px solid rgba(56, 189, 248, 0.1); border-radius: 12px; padding: 15px;">
<div style="display: flex; align-items: center; gap: 15px;">
<div style="background: #38bdf8; color: white; width: 45px; height: 45px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.3em;">🖥️</div>
<div>
<div style="color: #cbd5e1; font-weight: 600; font-size: 1.1em;">{agent_count} Agents</div>
<div style="color: #94a3b8; font-size: 0.85em;">Inventory Endpoints</div>
</div>
</div>
{f'<div style="margin-top: 12px; display: grid; grid-template-columns: 1fr 1fr; gap: 5px; max-height: 80px; overflow-y: auto;">' + "".join([f'<div style="font-family: monospace; color: #64748b; font-size: 0.8em;">• {ip}</div>' for ip in agent_ips]) + '</div>' if agent_ips else ""}
</div>
</div>
</div>""", unsafe_allow_html=True)

        with col2:
            # Active Roles / Components Card
            roles_html = "".join([
                f'<div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.05); padding: 8px 12px; border-radius: 8px; display: flex; align-items: center; gap: 10px;">'
                f'<span style="color: #34d399;">✓</span> <span style="color: #e2e8f0; font-size: 0.9em;">{role.replace("_", " ").title()}</span>'
                f'</div>' for role in enabled_roles
            ])
            
            st.markdown(f"""<div class="css-card">
<h4 style="margin-top:0; color: #94a3b8; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 15px;">Active Components</h4>
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
{roles_html if enabled_roles else '<div style="color: #64748b; grid-column: span 2;">No roles enabled.</div>'}
</div>
<div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
<div style="color: #64748b; font-size: 0.8em; text-transform: uppercase; margin-bottom: 10px;">Environment Info</div>
<div style="display: flex; gap: 20px;">
<div>
<div style="color: #94a3b8; font-size: 0.75em;">Config File</div>
<div style="color: #cbd5e1; font-size: 0.85em;">group_vars/all.yml</div>
</div>
<div>
<div style="color: #94a3b8; font-size: 0.75em;">Inventory</div>
<div style="color: #cbd5e1; font-size: 0.85em;">hosts.ini</div>
</div>
</div>
</div>
</div>""", unsafe_allow_html=True)
            
    else:
        st.warning("⚠️ Configuration missing. Please go to the Configuration tab to initialize the system.")

    st.markdown("<br>", unsafe_allow_html=True)
    

