from nicegui import ui
from reef.manager.ui_utils import page_header

# --- Documentation Content (English, Simplified) ---

DOCS_DATA = {
    "project_overview": {
        "title": "Project Overview",
        "icon": "info",
        "content": """
# Welcome to REEF

**REEF** is a streamlined cybersecurity platform designed specifically for **Small and Medium-sized Enterprises (SMEs)**. We understand that effective cybersecurity often feels out of reach due to complexity and cost. REEF bridges that gap.

### 🎯 Our Mission
To provide **enterprise-grade security monitoring** that is accessible to everyone. You shouldn't need a team of experts just to know if your business is safe.

### 🚀 Why REEF?
*   **Simplicity First**: We abstract away the complex configurations.
*   **Unified View**: See the security status of your entire IT infrastructure in one place.
*   **Automated Intelligence**: We use industry-standard tools but handle the heavy lifting of setup and maintenance for you.
"""
    },
    "installation": {
        "title": "Installation & Setup",
        "icon": "build",
        "content": """
# Installation & Configuration

Setting up a Security Operations Center (SOC) usually takes days. With REEF, we aim for minutes.

### 1. The Central Server (The "Brain")
You need one main server to run REEF. This machine will collect data from all your other computers.
*   **Requirement**: A Linux server (Ubuntu 22.04+ Recommended).
*   **Specs**: Minimum 4GB RAM, 2 CPUs.

### 2. The Agents (The "Sensors")
To protect your computers (laptops, workstations, servers), you install a small program called an **Agent**.
*   **What it does**: It runs quietly in the background, watching for viruses, file changes, and suspicious behavior.
*   **Connecting**: The Agent sends this data securely to your REEF Central Server.

### 3. Deployment Process
We use an automation engine called **Ansible**.
1.  Navigate to the **Deploy** tab in REEF.
2.  Enter your server details in the inventory.
3.  Click **"Deploy Security Stack"**.
4.  REEF automatically installs the database, the analysis engine, and the dashboard.
"""
    },
    "services": {
        "title": "Services Explained",
        "icon": "dns",
        "content": """
# Under the Hood: Your Security Shield

REEF orchestrates several powerful open-source security tools. Here is a simple explanation of what each component does for you.

### 🧠 Wazuh & Derivates (The Core)
Wazuh is the brain of the operation. It is a **SIEM** (Security Information and Event Management) system.
*   **Role**: It receives alerts from all your agents, correlates them (finds patterns), and decides if something is a threat.

### 🛡️ UFW (The Firewall)
Think of the firewall as the fence around your digital property.
*   **Role**: It strictly controls traffic, allowing only authorized connections to enter your server and blocking everything else.

### 🚫 Fail2Ban (The Bouncer)
This tool protects your server's login door.
*   **Role**: If a hacker tries to guess your password and fails multiple times, Fail2Ban detects this pattern and **immediately bans** their IP address, locking them out.

### 👁️ Suricata (The Watchtower)
*Available in advanced configurations.*
*   **Role**: An Intrusion Detection System (IDS). It analyzes network traffic in real-time, looking for "signatures" of known cyberattacks, much like an antivirus scanner but for network packets.
"""
    },
    "gadgets": {
        "title": "Features & Gadgets",
        "icon": "widgets",
        "content": """
# Features & Utilities

REEF isn't just about monitoring; it's about making security management actionable and easy.

With Wazuh Dashboard, REEF Dashboard and/or Graphana, you have access to : 
### 📊 Real-Time Dashboard
The **Dashboard** is your control center.
*   **Health Status**: Instant color-coded indicators (Green/Orange/Red) showing your overall security posture.
*   **Alert Feed**: A live stream of security events as they happen.

### 📑 PDF Report Generation
Need to present a status update to your boss or an auditor?
*   **The Gadget**: In the Dashboard, you will find a **"Generate Report"** button.
*   **What you get**: A professionally formatted PDF document.
*   **Contents**: It includes an executive summary, a logic-based security score (e.g., "Healthy" or "At Risk"), and a list of top threats detected in the last 24 hours.

### 🔍 Threat Hunting (Simplified)
You can search through your logs efficiently without needing to learn complex query languages. REEF pre-filters the noise so you see what matters.
"""
    }
}

def show_documentation():
    # Header
    page_header("Documentation", "Guides, References & Help")
    
    # Custom CSS for Markdown styling
    ui.add_head_html('''
        <style>
            .doc-markdown h1 { font-size: 2.2rem; font-weight: 700; color: #f8fafc; margin-bottom: 1.5rem; border-bottom: 1px solid #334155; padding-bottom: 0.5rem; }
            .doc-markdown h3 { font-size: 1.4rem; font-weight: 600; color: #e2e8f0; margin-top: 2rem; margin-bottom: 0.75rem; }
            .doc-markdown p { font-size: 1.05rem; line-height: 1.7; color: #94a3b8; margin-bottom: 1rem; }
            .doc-markdown ul { list-style-type: disc; margin-left: 1.5rem; margin-bottom: 1rem; color: #94a3b8; }
            .doc-markdown li { margin-bottom: 0.5rem; }
            .doc-markdown strong { color: #38bdf8; font-weight: 600; }
        </style>
    ''')

    with ui.row().classes('w-full h-[calc(100vh-180px)] gap-0'):
        
        # --- Sidebar Navigation ---
        nav_col = ui.column().classes('w-1/4 h-full p-4 border-r border-slate-700/50 bg-slate-900/30')
        
        # --- Main Content Area ---
        content_col = ui.scroll_area().classes('w-3/4 h-full bg-slate-900/10 p-8')

        # Content Renderer
        with content_col:
            # Container for the text
            text_container = ui.element('div').classes('w-full max-w-4xl mx-auto')
            
            def render_content(key):
                text_container.clear()
                with text_container:
                    ui.markdown(DOCS_DATA[key]["content"]).classes('doc-markdown w-full')
            
            # Initial Load
            render_content("project_overview")

        # Navigation Renderer
        with nav_col:
            ui.label("CONTENTS").classes('text-xs font-bold text-slate-500 mb-4 tracking-wider pl-2')
            
            for key, data in DOCS_DATA.items():
                # Styling the buttons to look like nav links
                btn = ui.button(on_click=lambda k=key: render_content(k)) \
                    .props('flat') \
                    .classes('w-full text-left align-middle mb-2 rounded-lg hover:bg-slate-800 transition-all duration-200 group')
                
                with btn:
                    with ui.row().classes('w-full items-center gap-3 py-1'):
                        ui.icon(data['icon']).classes('text-slate-400 group-hover:text-sky-400 transition-colors')
                        ui.label(data['title']).classes('text-slate-300 font-medium group-hover:text-white capitalize')
                        ui.icon('chevron_right').classes('ml-auto text-slate-600 text-xs opacity-0 group-hover:opacity-100')
