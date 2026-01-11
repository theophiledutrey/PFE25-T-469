import streamlit as st
import subprocess
import re
import time
from pathlib import Path

def run_shell_stream(command, env=None):
    """Run command and stream output to Streamlit."""
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        executable='/bin/zsh',
        env=env
    )
    
    # Create a container with fixed height for the log window
    log_window = st.container(height=200)
    with log_window:
        output_placeholder = st.empty()
    output_lines = []
    
    # Read output line by line
    for line in iter(process.stdout.readline, ""):
        output_lines.append(line)
        # Updates code block with full path so far - effectively streaming
        # keep last 50 lines per original code
        text = "".join(output_lines[-50:]) 
        output_placeholder.code(text, language="bash")
    
    process.wait()
    
    full_output = "".join(output_lines)
    
    if process.returncode == 0:
        st.success("Command completed successfully.")
    else:
        st.error(f"Command failed with exit code {process.returncode}")
    
    return process.returncode, full_output

def run_ansible_with_loader(command, log_file, env=None):
    """
    Run ansible command, stream output to log file, and update UI with current task.
    """
    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        executable='/bin/zsh',
        env=env,
        bufsize=1  # Line buffered
    )
    
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    status_container = st.empty()
    task_container = st.empty() # For the specific task details
    results_container = st.container() # Persistent results
    
    current_task = "Initializing..."
    
    # regex for ansible task
    # TASK [role : task name] ***
    task_pattern = re.compile(r"TASK \[(.*?)\]")
    # regex for host status line
    # ok: [192.168.64.12] ...
    host_pattern = re.compile(r"^(?:ok|changed|failed|fatal): \[(.*?)\]")
    # regex for debug msg
    # "msg": "[WARN] ..."
    msg_pattern = re.compile(r'"msg": "(.*?)"')
    
    current_host = "Local"

    with open(log_path, 'w') as f:
        with st.spinner("Executing Ansible Playbook..."):
            start_time = time.time()
            
            for line in iter(process.stdout.readline, ""):
                # Write to log
                f.write(line)
                
                # Check for task change
                match = task_pattern.search(line)
                if match:
                    current_task = match.group(1)
                    # Update UI
                    task_container.info(f"▶️  Executing: **{current_task}**")
                
                # Check for host
                host_match = host_pattern.search(line)
                if host_match:
                    current_host = host_match.group(1)

                # Check for debug messages
                msg_match = msg_pattern.search(line)
                if msg_match:
                    content = msg_match.group(1)
                    # Create display string with host
                    display_msg = f"**[{current_host}]** {content}"
                    
                    if "[WARN]" in content:
                        clean_msg = display_msg.replace("[WARN]", "").strip()
                        results_container.warning(clean_msg)
                    elif "[INFO]" in content:
                        clean_msg = display_msg.replace("[INFO]", "").strip()
                        results_container.info(clean_msg)
                    elif "[OK]" in content:
                        clean_msg = display_msg.replace("[OK]", "").strip()
                        results_container.success(clean_msg)

            process.wait()
            end_time = time.time()
            duration = end_time - start_time
    
    if process.returncode == 0:
        task_container.empty()
        st.success(f"✅ Checks completed successfully in {duration:.2f}s")
        st.caption(f"Full logs saved to `{log_path.name}`")
    else:
        st.error(f"❌ Process failed with exit code {process.returncode}")
        st.warning(f"Check logs at `{log_path.name}` for details.")
    
    return process.returncode
