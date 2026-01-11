import streamlit as st
import os
import time
import subprocess
import re

from datetime import datetime
from pathlib import Path
from manager.core import ANSIBLE_DIR, HOSTS_INI_FILE, BASE_DIR

def get_log_files():
    """Get list of prerequisite log files sorted by date."""
    log_dir = BASE_DIR / "logs"
    if not log_dir.exists():
        return []
    files = list(log_dir.glob("prerequisites_*.log"))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files

def parse_ansible_line(line, current_task, current_host):
    """Parse a line of Ansible output to extract status updates."""
    # Regex patterns
    task_pattern = re.compile(r"TASK \[(.*?)\]")
    # ok: [host], changed: [host], failed: [host], fatal: [host]
    status_pattern = re.compile(r"^(ok|changed|failed|fatal): \[(.*?)\]")
    msg_pattern = re.compile(r'"msg": "(.*?)"')
    
    new_task = current_task
    new_host = current_host
    row_update = None
    
    # Check for Task
    task_match = task_pattern.search(line)
    if task_match:
        new_task = task_match.group(1)
        
    # Check for Status/Host
    status_match = status_pattern.search(line)
    if status_match:
        status = status_match.group(1)
        new_host = status_match.group(2)
        
        # We found a result line. Let's try to capture the message 
        # (usually follows or is on the same line depending on verbosity/callback)
        # For simplicity in this stream, we might capture the message from a subsequent line 
        # or just mark it as done. 
        # But often "msg" appears in a separate block for debug tasks.
        
        # Basic row entry
        row_update = {
            "Timestamp": datetime.now().strftime("%H:%M:%S"),
            "Host": new_host,
            "Task": new_task,
            "Status": status.upper(),
            "Message": "" 
        }

    # Check for debug msg
    msg_match = msg_pattern.search(line)
    if msg_match and row_update is None:
        # If we find a message but no status line immediately, 
        # we might want to attach it to the LAST row or treat it as an info row.
        # For this implementation, we'll return it as a partial update to be handled by the caller.
        return new_task, new_host, {"Message": msg_match.group(1)}

    return new_task, new_host, row_update

def run_checks(cmd, log_file, env):
    """Run checks with real-time logging and structured parsing."""
    
    # UI Elements for Live Updates
    status_container = st.empty()
    table_placeholder = st.empty()
    
    # Expander for raw logs
    with st.expander("Raw Live Logs", expanded=True):
        with st.container(height=200):
            log_placeholder = st.empty()
        
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        executable='/bin/zsh',
        env=env,
        bufsize=1
    )
    
    # State tracking
    full_logs = []
    structured_data = [] # List of dicts
    current_task = "Initializing"
    current_host = "Local"
    
    # Regex for fast error spotting
    fail_pattern = re.compile(r"(fatal|failed):")
    
    start_time = time.time()
    
    with open(log_file, 'w') as f:
        for line in iter(process.stdout.readline, ""):
            # Save to file
            f.write(line)
            
            # Update raw logs view (keep last 100 lines to avoid UI lag if very long)
            full_logs.append(line)
            log_text = "".join(full_logs[-100:])
            log_placeholder.code(log_text, language="bash")
            
            # Check for immediate errors
            if fail_pattern.search(line):
                st.toast(f"Error detected: {line.strip()}", icon="Vg")
                
            # Parse for table
            current_task, current_host, info = parse_ansible_line(line, current_task, current_host)
            
            if info:
                if "Status" in info:
                    # New result row
                    structured_data.append(info)
                elif "Message" in info and structured_data:
                    # Append message to the last relevant row if possible
                    structured_data[-1]["Message"] = info["Message"]
            
            # Update Table
            if structured_data:
                table_placeholder.dataframe(
                    structured_data, 
                    width='stretch'
                )


    process.wait()
    duration = time.time() - start_time
    
    if process.returncode == 0:
        status_container.success(f"Checks passed in {duration:.2f}s")
    else:
        status_container.error(f"Checks failed in {duration:.2f}s")
        
    return process.returncode

def render_prerequisites():
    st.title("Prerequisites Check")

    # Main Interface
    col1, col2 = st.columns([2, 1])
    
    with col1:
        mode = st.radio("Target", ["Local Machine", "Inventory Hosts"], horizontal=True)
    
    with col2:
        st.write("Options")
        more_verbose = st.checkbox("More Verbose (-vv)")

    if st.button("Run Check", type="primary"):
        # Setup Command
        playbook = ANSIBLE_DIR / "playbooks" / "prerequisites.yml"
        
        # Verbosity
        if more_verbose:
            verbosity_flag = "-vv"
        else:
            verbosity_flag = ""
            
        env = os.environ.copy()
        env["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
        
        # Generate Log Filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = BASE_DIR / "logs" / f"prerequisites_{timestamp}.log"
        # Ensure log dir exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        if mode == "Local Machine":
            cmd = f"ansible-playbook {playbook} --connection=local -i localhost, {verbosity_flag}"
        else:
            if not HOSTS_INI_FILE.exists():
                st.error(f"Inventory file not found at {HOSTS_INI_FILE}")
                return
            cmd = f"ansible-playbook {playbook} -i {HOSTS_INI_FILE} {verbosity_flag}"
            
        run_checks(cmd, log_file, env)
