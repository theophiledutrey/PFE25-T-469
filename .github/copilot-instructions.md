**Repository Overview**
- **Purpose:** REEF is a security automation manager. It uses NiceGUI for a local web UI and Ansible playbooks/roles for deploying and managing components.
- **Key entrypoints:** `src/reef/main.py` (NiceGUI app), `src/reef/cli/reef.py` (CLI), UI pages under `src/reef/manager/ui/`, and orchestration helpers in `src/reef/manager/core.py`.

**Big-picture architecture**
- The UI is a single-process NiceGUI app (see `src/reef/main.py`) which imports page builders from `src/reef/manager/ui/*`.
- Deployment/backing operations are executed by calling Ansible via subprocesses. Configuration/state is stored in Ansible inventory and `group_vars/all.yml` (managed via `core.update_yaml_config_from_schema`).
- `manager/core.py` contains utility primitives: command execution, inventory parsing, schema management. UI modules call these functions directly for orchestration.

**Where to make changes (patterns & examples)**
- Add new UI pages or controls inside `src/reef/manager/ui/*.py`. Pages typically expose a `show_<name>()` function and use `page_header()` from `ui_utils.py`.
  - Example: the Deploy page is `src/reef/manager/ui/deploy.py` and defines `show_deploy()`.
- Use `ui` scopes to build components and closure-scoped handlers to keep state. Event handlers are often defined with `async def` inside the page function.
  - Example pattern: define inputs near the button and `async def handler(): ...` that reads input values and calls `core` helpers.
- Use `asyncio.to_thread()` when calling blocking core helpers from async UI handlers.

**Project-specific conventions**
- UI state is kept in local variables within page functions (not global). Add handlers in the same scope so they can access UI controls directly.
- Configuration persistence goes through `update_yaml_config_from_schema()` to keep comments and structure in `ansible/inventory/group_vars/all.yml`.
- Inventory is read from `ansible/inventory/hosts.ini`. The code uses a light, custom parser in `manager/core.py` — be conservative when changing inventory handling.
- Ansible paths are computed from `manager/core.py` constants (`ANSIBLE_DIR`, `HOSTS_INI_FILE`); prefer using these constants rather than hardcoding paths.

**How to run & test locally**
- From the repo root, run the UI with (recommended):

```bash
python src/reef/main.py
```

- Optional env vars: `REEF_HOST` and `REEF_PORT`. Example: `REEF_HOST=0.0.0.0 REEF_PORT=54540 python src/reef/main.py`.
- Tests: run `pytest -q` or the provided script `tests/integration-tests.sh` for integration checks.
- Container: repository contains `Dockerfile` and `docker-compose.yml` if you prefer containerized execution.

**Integration points & where to wire external providers**
- For VM/cloud integration implement provider code in `src/reef/manager/core.py` (or add a new `manager/providers.py`) and expose a small sync API such as `create_vm(name, image, size)`; call it from UI handlers with `await asyncio.to_thread(...)`.
  - Example: the Deploy UI calls `async_run_ansible_playbook()`; follow the same pattern for VM creation.
- Keep provider credentials and secrets out of version control; hook them into `group_vars/all.yml` if needed, or prefer environment variables.

**Debugging tips**
- Enable verbose logs by inspecting `manager/core.py` and `console.print` outputs — long-running subprocesses run with `subprocess.run` and print to console.
- Recreate the environment exactly like the NiceGUI runtime: run `python src/reef/main.py` from repo root so path adjustments in `main.py` behave as expected.

**When adding features (checklist for PRs)**
- Add UI elements inside `src/reef/manager/ui/<page>.py` and keep handlers local to the page function.
- Call into `manager/core.py` for state mutation or external operations; use `asyncio.to_thread()` from the UI when calling blocking code.
- Update `ansible/` assets if the feature requires playbooks/roles and update `ansible/inventory/hosts.ini` programmatically using `update_ini_inventory()` if needed.
- Include a short smoke test (manual steps) in the PR description showing how to exercise the new UI control and expected result.

**Quick references**
- Deploy UI: [src/reef/manager/ui/deploy.py](src/reef/manager/ui/deploy.py)
- Core helpers: [src/reef/manager/core.py](src/reef/manager/core.py)
- UI utilities: [src/reef/manager/ui_utils.py](src/reef/manager/ui_utils.py)
- Ansible assets: [src/reef/ansible/](src/reef/ansible/)

If anything is unclear or you'd like the instructions in French, I can revise the file — voulez-vous que je traduise ce document en français ?
