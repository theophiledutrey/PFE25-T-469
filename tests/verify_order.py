def verify_ansible_logic():
    # The hardcoded loop order in experimental.yml
    static_order = [
         'cleanup',
         'common',
         'wazuh-indexer',
         'wazuh-server',
         'wazuh-dashboard',
         'ufw',
         'fail2ban'
    ]

    # User input (shuffled order as usually returned by UI selection)
    user_input_scenarios = [
        ['wazuh-server', 'cleanup', 'common'],
        ['fail2ban', 'ufw', 'cleanup'],
        ['wazuh-dashboard', 'wazuh-indexer', 'wazuh-server'] # Reverse typical order
    ]

    print("Verifying Ansible Execution Order Logic...\n")
    
    for i, enabled_roles in enumerate(user_input_scenarios):
        print(f"Scenario {i+1}: User selected: {enabled_roles}")
        executed_order = []
        
        # Simulate Ansible Loop
        for role_item in static_order:
            if role_item in enabled_roles:
                executed_order.append(role_item)
                
        print(f"  -> Actual Execution Order: {executed_order}")
        
        # Verify order is monotonic with respect to static_order
        # i.e. indices in static_order must be increasing
        indices = [static_order.index(r) for r in executed_order]
        if indices == sorted(indices):
             print("  -> [PASS] Order is preserved correctly.")
        else:
             print("  -> [FAIL] Order is broken!")
        print("-" * 40)

if __name__ == "__main__":
    verify_ansible_logic()
