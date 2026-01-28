import sys
from pathlib import Path
from nicegui import ui

# Ensure path is set up (similar to original app.py)
# Ensure path is set up (similar to original app.py)
current_dir = Path(__file__).parent.resolve()
src_dir = str(current_dir.parent)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import Pages
from reef.manager.ui.dashboard import show_dashboard
from reef.manager.ui.configuration import show_configuration
from reef.manager.ui.prerequisites import show_prerequisites
from reef.manager.ui.deploy import show_deploy
from reef.manager.ui.documentation import show_documentation

# --- App Layout & State ---

@ui.page('/')
def main_page():
    # Global Style
    ui.add_head_html("""
    <style>
        body { background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); }
    </style>
    """)
    ui.colors(primary='#4f46e5', secondary='#06b6d4', accent='#111827', dark='#111827')
       
    # Sidebar
    with ui.left_drawer(value=True).classes('bg-slate-900 border-r border-white/5') as drawer:
        # Header
        with ui.row().classes('items-center gap-2 mb-8 mt-4'):
            ui.label('🪸').classes('text-2xl')
            with ui.column().classes('gap-0'):
                ui.label('REEF').classes('text-xl font-bold text-white tracking-widest')
                ui.label('Security Automation').classes('text-xs text-slate-400')
        
        # Navigation
        nav_items = [
            ('Dashboard', 'dashboard', show_dashboard),
            ('Configuration', 'settings', show_configuration),
            ('Prerequisites', 'check_circle', show_prerequisites),
            ('Deploy & Manage', 'rocket_launch', show_deploy),
            ('Documentation', 'menu_book', show_documentation),
        ]

    # Content Area
    content = ui.column().classes('w-full p-8 items-start')
    
    # Store button references to update state
    nav_buttons = {}

    def update_nav_visuals(active_title):
        for title, btn in nav_buttons.items():
            if title == active_title:
                btn.props('text-color=white color=indigo-10')
                btn.classes(add='bg-indigo-600/20')
            else:
                btn.props('text-color=grey-5 color=transparent') 
                btn.classes(remove='bg-indigo-600/20')

    def navigate(title, func):
        content.clear()
        with content:
            func()
        update_nav_visuals(title)

    # Populate Drawer Navigation 
    with drawer:
        for title, icon, func in nav_items:
            # Initial state handled by update_nav_visuals called in initial load, 
            # but we define base props here.
            btn = ui.button(title, icon=icon, on_click=lambda t=title, f=func: navigate(t, f)) \
                .props('flat align=left text-color=grey-3') \
                .classes('w-full hover:bg-white/5 transition-colors')
            nav_buttons[title] = btn

    # Initial Load
    navigate('Dashboard', show_dashboard)

def run_app():
    import os
    import socket
    
    env_host = os.environ.get('REEF_HOST')
    env_port = os.environ.get('REEF_PORT')
    
    # Defaults
    host = env_host if env_host else '127.0.0.1'
    port = int(env_port) if env_port else 54540
    
    # If running in Docker (implied by 0.0.0.0 host), the printed URL might be confusing.
    # We can print a helpful message manually before NiceGUI starts.
    if host == '0.0.0.0':
        print(f"\n[REEF] Server starting on internal IP: {host}:{port}")
        print(f"[REEF] If running in Docker, access via: http://localhost:{port}\n")
    else:
        print(f"\n[REEF] Server starting on: http://{host}:{port}\n")

    ui.run(title='REEF Manager', dark=True, storage_secret='reef_secret', favicon='🪸', reload=False, host=host, port=port)

if __name__ in {"__main__", "__mp_main__"}:
    run_app()