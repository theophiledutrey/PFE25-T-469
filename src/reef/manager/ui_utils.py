from nicegui import ui
import asyncio
import subprocess
import os
import signal
from reef.manager.core import BASE_DIR, ANSIBLE_DIR

class AppState:
    running_process: str = None
    current_process: asyncio.subprocess.Process = None

    def cancel_process(self):
        if self.current_process:
            try:
                # Send SIGTERM to the process group to kill shell and children
                os.killpg(os.getpgid(self.current_process.pid), signal.SIGTERM)
                self.running_process = "Stopping..."
            except Exception as e:
                print(f"Error terminating process: {e}")

app_state = AppState()

def page_header(title: str, subtitle: str = None):
    with ui.row().classes('w-full justify-between items-center mb-6'):
        with ui.column():
            ui.label(title).classes('text-3xl font-bold text-white tracking-tight')
            if subtitle:
                ui.label(subtitle).classes('text-lg text-slate-400')
        
        # Process Status Indicator
        with ui.row().classes('items-center gap-3 bg-indigo-500/10 border border-indigo-500/20 px-4 py-2 rounded-full hidden') as status_badge:
            ui.spinner('dots', size='md').classes('text-indigo-400')
            status_label = ui.label('Processing...').classes('text-indigo-300 font-bold animate-pulse')
            
            def update_status():
                if app_state.running_process:
                    status_badge.classes(remove='hidden')
                    status_label.text = app_state.running_process
                else:
                    status_badge.classes(add='hidden')
            
            ui.timer(0.5, update_status)

    ui.separator().classes('mb-6 bg-slate-700')

def card_style():
    return 'p-6 rounded-2xl bg-white/5 border border-white/10 shadow-lg backdrop-blur-md transition-all hover:-translate-y-1 hover:shadow-2xl'

def _get_ansible_env():
    env = os.environ.copy()
    env['ANSIBLE_CONFIG'] = str(BASE_DIR / "ansible.cfg")
    env['ANSIBLE_ROLES_PATH'] = str(ANSIBLE_DIR / "roles")
    return env

async def async_run_command(command: str, log_element: ui.log, on_complete=None):
    """
    Asynchronously run a shell command and stream output to a UI log element.
    """
    app_state.running_process = " Running..."
    try:
        log_element.push(f"Running: {command}")
    except:
        pass
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            executable='/bin/bash',
            cwd=str(BASE_DIR),
            env=_get_ansible_env(),
            preexec_fn=os.setsid # Allow killing whole process group
        )
        app_state.current_process = process

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode().strip()
            try:
                log_element.push(text)
            except:
                pass # UI element might be gone if user navigated away

        await process.wait()
        
        try:
            if process.returncode == 0:
                ui.notify('Command completed successfully', type='positive')
            elif process.returncode == -15: # SIGTERM
                 ui.notify('Command stopped by user', type='warning')
            else:
                ui.notify(f'Command failed with exit code {process.returncode}', type='negative')
        except:
            pass

        if on_complete:
            on_complete(process.returncode)
            
    finally:
        app_state.running_process = None
        app_state.current_process = None

async def async_run_ansible_playbook(command: str, log_element: ui.log):
    """
    Runs an ansible playbook, streams output to log, and returns parsed task results.
    Returns: (returncode, full_output_string, task_results_list)
    """
    import re
    import signal
    app_state.running_process = "Running Playbook..."
    try:
        log_element.clear()
        log_element.push(f"Running: {command}")
    except:
        pass
    
    captured_lines = []
    task_results = []
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            executable='/bin/bash',
            cwd=str(BASE_DIR),
            env=_get_ansible_env(),
            preexec_fn=os.setsid # Allow killing whole process group
        )
        app_state.current_process = process

        current_task = "Starting"

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            text = line.decode().strip()
            
            try:
                log_element.push(text)
            except:
                pass
                
            captured_lines.append(text)

            # Parsing Logic
            if text.startswith("TASK ["):
                m_task = re.search(r"TASK \[(.*?)\]", text)
                if m_task:
                    current_task = m_task.group(1)
            
            elif text.startswith("ok: [") or text.startswith("changed: [") or text.startswith("failed: [") or text.startswith("fatal: ["):
                    parts = text.split("]")
                    if len(parts) >= 1:
                        meta = parts[0] # ok: [host
                        if ": [" in meta:
                            status_part, host_part = meta.split(": [")
                            host = host_part.strip()
                            status = status_part.strip()
                            
                            task_results.append({
                                'host': host,
                                'task': current_task,
                                'status': status
                            })

        await process.wait()
        
        try:
            if process.returncode == 0:
                ui.notify('Playbook completed successfully', type='positive')
            elif process.returncode == -15:
                 ui.notify('Playbook stopped by user', type='warning')
            else:
                ui.notify(f'Playbook failed (Exit {process.returncode})', type='negative')
        except:
            pass
            
    finally:
        app_state.running_process = None
        app_state.current_process = None
        
        # Ensure we kill the process group in case child processes (like ansible-playbook workers) persist
        if process and process.returncode is None:
             try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
             except:
                 pass

    return process.returncode, "\n".join(captured_lines), task_results

def status_badge(active: bool, text_active="Active", text_inactive="Inactive"):
    color = "green-400" if active else "amber-400"
    text = text_active if active else text_inactive
    
    with ui.row().classes('items-center gap-2'):
        ui.icon('circle', size='xs').classes(f'text-{color}')
        ui.label(text).classes(f'text-{color} font-bold')
