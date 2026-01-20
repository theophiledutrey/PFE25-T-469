  Concepts to Improve the Overall Tool

  These are bigger ideas to evolve your project from a set of scripts into a mature, maintainable tool.

  check that agents are comm correctly even if added after manager
  passwords are in clear
  add custom rules tab
  add ruleset

   2. Adopt a GitOps Flow:
       * Concept: Use Git as the central source of truth for your server configurations. Instead of a user running the pme_manager and immediately
         pushing changes to a server, the manager would help them commit a variable change to a Git repository.
       * Benefit: A CI/CD pipeline (like GitHub Actions) can then automatically run the Molecule tests on the change and, if they pass, deploy it.
         This gives you an audit log of all changes, the ability to review/approve configurations via pull requests, and a much safer, more
         controlled deployment process.

   4. Environment-Specific Configurations:
       * Concept: Your current inventory is static. Real-world use involves multiple environments (development, staging, production) with
         different settings (e.g., more relaxed firewall in dev).
       * Benefit: Structure your inventory to support this. A common pattern is inventory/production/hosts.ini and inventory/staging/hosts.ini,
         with different variables defined in inventory/production/group_vars/all.yml and inventory/staging/group_vars/all.yml. This allows you to
         manage multiple environments from the same codebase.

   5. Secrets Management Strategy:
       * Concept: Move away from plain text passwords (like in wazuh-passwords.txt) and simple vars_files. Use Ansible Vault or a dedicated
         secrets manager (like HashiCorp Vault, or even environment variables injected at runtime).
       * Benefit: Prevents credential leakage. Essential for any security-focused project. It ensures that if the repo is shared, secrets aren't
         exposed.

   6. Automated Integration Testing (Molecule):
       * Concept: Implement Molecule (https://ansible.readthedocs.io/projects/molecule/) to test roles in isolation using Docker containers.
       * Benefit: Allows you to verify that a role (e.g., wazuh-agent) correctly installs and configures the service before running it against a
         real VM. This drastically reduces the "trial and error" loop and prevents regressions.



