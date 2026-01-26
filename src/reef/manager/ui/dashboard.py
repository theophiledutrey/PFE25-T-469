from nicegui import ui
from reef.manager.core import GROUP_VARS_FILE, HOSTS_INI_FILE, load_current_config
from reef.manager.ui_utils import page_header, card_style, status_badge
from reef.manager.wazuh_api import fetch_wazuh_alert_summary, generate_report_pdf
import datetime

def show_dashboard():
    page_header("Dashboard", "Overview of your security system")

    if not GROUP_VARS_FILE.exists():
        with ui.card().classes('w-full bg-amber-500/10 border-amber-500/20'):
            with ui.row().classes('items-center gap-4'):
                ui.icon('warning', size='lg').classes('text-amber-500')
                ui.label("Configuration missing. Please go to the Configuration tab to set up your system.").classes('text-amber-500 text-lg')
        return

    # Load data
    config = load_current_config()
    manager_ip = config.get('wazuh_manager_ip', 'Unknown')
    enabled_roles = config.get('enabled_roles', [])
        
    # Count agents
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

    manager_ips = []
    if HOSTS_INI_FILE.exists():
        content = HOSTS_INI_FILE.read_text()
        lines = content.splitlines()
        in_managers = False
        for line in lines:
            if line.strip() == "[security_server]" or line.strip() == "[wazuh_manager]":
                in_managers = True
                continue
            if line.strip().startswith("[") and line.strip() not in ["[security_server]", "[wazuh_manager]"]:
                in_managers = False
            
            if in_managers and line.strip() and not line.strip().startswith("#"):
                parts = line.strip().split()
                if parts:
                    manager_ips.append(parts[0])

    manager_count = len(manager_ips)
    
    # Async Healthcheck
    import httpx
    
    async def download_report():
        ui.notify('Generating PDF report... Please wait.', type='info')
        data = await fetch_wazuh_alert_summary()
        if data:
            try:
                # Convert bytearray to bytes for nicegui
                pdf_bytes = bytes(generate_report_pdf(data))
                # Create a localized timestamp for filename
                filename = f"Reef_Security_Report_{datetime.datetime.now().strftime('%Y-%m-%d')}.pdf"
                ui.download(pdf_bytes, filename)
                ui.notify('Report generated successfully!', type='positive')
            except Exception as e:
                ui.notify(f'Error generating PDF: {e}', type='negative')
                print(f"PDF Error: {e}")
        else:
            ui.notify('Failed to fetch data from Wazuh.', type='negative')

    async def check_wazuh(label_status, spinner):
        try:
            url = f"http://{manager_ip}:3000"
            async with httpx.AsyncClient(verify=False, timeout=2.0) as client:
                response = await client.get(url)

                if response.status_code in [200, 302]:
                     spinner.visible = False
                     label_status.classes(remove='text-slate-500', add='text-emerald-400')
                     label_status.text = "Online"
                else:
                     spinner.visible = False
                     label_status.classes(remove='text-slate-500', add='text-amber-500')
                     label_status.text = f"Status {response.status_code}"
        except Exception as e:
            spinner.visible = False
            label_status.classes(remove='text-slate-500', add='text-rose-500')
            label_status.text = "Unreachable"

    import asyncio

    async def check_ping(ip, status_icon):
        try:
            proc = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '1000', ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
             
            if proc.returncode == 0:
                status_icon.classes(remove='text-slate-500', add='text-emerald-500')
                status_icon.props('icon=check_circle')
            else:
                 status_icon.classes(remove='text-slate-500', add='text-rose-500')
                 status_icon.props('icon=cancel')
        except Exception:
             status_icon.classes(remove='text-slate-500', add='text-rose-500')
             status_icon.props('icon=cancel')

    wazuh_refs = {}
    ping_checks = []

    async def refresh_infrastructure():
        if 'label' in wazuh_refs and 'spinner' in wazuh_refs:
            wazuh_refs['label'].text = 'Checking...'
            wazuh_refs['label'].classes(remove='text-emerald-400 text-amber-500 text-rose-500', add='text-slate-500')
            wazuh_refs['spinner'].visible = True
            asyncio.create_task(check_wazuh(wazuh_refs['label'], wazuh_refs['spinner']))
        
        for ip, icon in ping_checks:
            icon.classes(remove='text-emerald-500 text-rose-500', add='text-slate-500')
            icon.props('icon=circle')
            asyncio.create_task(check_ping(ip, icon))

    # ... Grid Layout ...
    with ui.grid(columns=2).classes('w-full gap-6'):
        
        # Core Infrastructure Card
        with ui.column().classes(card_style()):
            with ui.row().classes('w-full justify-between items-center mb-4 border-b border-white/10 pb-2'):
                ui.label('System Health').classes('text-slate-400 font-bold')
                ui.button(on_click=refresh_infrastructure).props('icon=refresh flat dense round size=sm').classes('text-slate-500 hover:text-white')
            
            with ui.column().classes('gap-6 w-full'):
                
                # Status Row
                with ui.row().classes('w-full justify-between items-center'):
                    with ui.column().classes('gap-0'):
                        ui.label('SYSTEM STATUS').classes('text-xs text-slate-500 font-bold')
                        status_badge(HOSTS_INI_FILE.exists(), "Active", "Pending Setup")
                        ui.tooltip("Shows if the system is configured and ready to use").classes('text-slate-300 text-xs')
                    
                    #with ui.column().classes('gap-0 items-end'):
                        #ui.label('MANAGER NODE').classes('text-xs text-slate-500 font-bold')
                        #ui.label(manager_ip).classes('font-mono text-slate-300 bg-white/5 px-2 py-1 rounded')

                # Wazuh Dashboard Check
                with ui.row().classes('w-full bg-sky-500/5 border border-sky-500/5 rounded-xl p-4 items-center gap-4 justify-between'):
                    with ui.row().classes('items-center gap-4'):
                        with ui.element('div').classes('flex items-center justify-center w-12 h-12 rounded-lg bg-sky-500 text-white text-xl'):
                            ui.icon('security')
                        
                        with ui.column().classes('gap-0'):
                            ui.label('Security Dashboard').classes('text-slate-200 font-bold text-lg')
                            ui.label('View alerts and events').classes('text-slate-400 text-xs')
                            with ui.row().classes('items-center gap-2'):
                                status_label = ui.label('Checking...').classes('text-xs text-slate-500')
                                spinner = ui.spinner('dots', size='xs').classes('text-slate-500')
                                wazuh_refs['label'] = status_label
                                wazuh_refs['spinner'] = spinner

                    ui.button('Open').props(f'flat dense size=sm href=http://{manager_ip}:3000/d/54540/security-dashboard target=_blank').classes('text-sky-400')

                # Managers Box
                with ui.row().classes('w-full bg-sky-500/5 border border-sky-500/10 rounded-xl p-4 items-center gap-4'):
                    with ui.element('div').classes('flex items-center justify-center w-12 h-12 rounded-lg bg-sky-500 text-white text-2xl'):
                        ui.icon('monitor')
                    
                    with ui.column().classes('gap-0'):
                        ui.label(f'{manager_count} Security Servers').classes('text-slate-200 font-bold text-lg')
                        ui.label('Central Management Nodes').classes('text-slate-400 text-sm')
                
                if manager_ips:
                    with ui.scroll_area().classes('w-full h-24 gap-1'):
                         for ip in manager_ips:
                             with ui.row().classes('items-center gap-2'):
                                 # We start with a spinner or generic icon
                                 status_icon = ui.icon('circle', size='xs').classes('text-slate-500')
                                 ping_checks.append((ip, status_icon))
                                 ui.label(f'{ip}').classes('font-mono text-slate-400 text-xs')
                                 # Trigger separate check for each
                                 ui.timer(0.1, lambda i=ip, s=status_icon: check_ping(i, s), once=True)
                else:
                    ui.label('No managers found.').classes('col-span-2 text-slate-500')

                # Agents Box
                with ui.row().classes('w-full bg-sky-500/5 border border-sky-500/10 rounded-xl p-4 items-center gap-4'):
                    with ui.element('div').classes('flex items-center justify-center w-12 h-12 rounded-lg bg-sky-500 text-white text-2xl'):
                        ui.icon('monitor')
                    
                    with ui.column().classes('gap-0'):
                        ui.label(f'{agent_count} Protected Computers').classes('text-slate-200 font-bold text-lg')
                        ui.label('Monitored Devices').classes('text-slate-400 text-sm')
                
                if agent_ips:
                    with ui.scroll_area().classes('w-full h-24 gap-1'):
                         for ip in agent_ips:
                             with ui.row().classes('items-center gap-2'):
                                 # We start with a spinner or generic icon
                                 status_icon = ui.icon('circle', size='xs').classes('text-slate-500')
                                 ping_checks.append((ip, status_icon))
                                 ui.label(f'{ip}').classes('font-mono text-slate-400 text-xs')
                                 # Trigger separate check for each
                                 ui.timer(0.1, lambda i=ip, s=status_icon: check_ping(i, s), once=True)
                else:
                    ui.label('No agents found.').classes('col-span-2 text-slate-500')

                


        # Active Roles Card
        with ui.column().classes(card_style()):
            ui.label('Installed Features').classes('text-slate-400 font-bold mb-4 border-b border-white/10 pb-2 w-full')
            
            with ui.grid(columns=2).classes('w-full gap-3 mb-6'):
                if enabled_roles:
                    for role in enabled_roles:
                        with ui.row().classes('bg-white/5 border border-white/5 rounded-lg p-2 items-center gap-2'):
                            ui.icon('check', size='xs').classes('text-emerald-400')
                            ui.label(role.replace("_", " ").title()).classes('text-slate-200 text-sm')
                else:
                    ui.label('No roles enabled.').classes('col-span-2 text-slate-500')

            ui.separator().classes('bg-white/10 mb-4')
            
            with ui.column().classes('gap-1'):
                ui.label('ENVIRONMENT INFO').classes('text-xs text-slate-500 font-bold mb-2')
                
                with ui.row().classes('gap-6'):
                    with ui.column().classes('gap-0'):
                        ui.label('Config File').classes('text-xs text-slate-400')
                        ui.label('Main Settings').classes('text-sm text-slate-300')
                        ui.tooltip("group_vars/all.yml").classes('text-slate-300 text-xs')
                    
                    with ui.column().classes('gap-0'):
                        ui.label('Inventory').classes('text-xs text-slate-400')
                        ui.label('Computer List').classes('text-sm text-slate-300')
                        ui.tooltip("hosts.ini").classes('text-slate-300 text-xs')

        # Reports Card
        with ui.column().classes(card_style()):
            ui.label('Security Reports').classes('text-slate-400 font-bold mb-4 border-b border-white/10 pb-2 w-full')
            ui.label('Generate a comprehensive PDF audit based on Wazuh data.').classes('text-slate-400 text-sm mb-4')
            
            with ui.row().classes('items-center gap-4'):
                ui.button('Download Audit Report (PDF)', on_click=download_report).props('icon=picture_as_pdf color=red-5').classes('w-full')

    # Trigger check
    ui.timer(0.1, lambda: check_wazuh(status_label, spinner), once=True)
