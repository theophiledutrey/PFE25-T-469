import httpx
import json
import base64
from pathlib import Path
from reef.manager.core import load_current_config

WAZUH_PASSWORD_FILE = Path(__file__).parent.parent / "ansible" / "wazuh-admin-password.txt"

def get_wazuh_credentials():
    config = load_current_config()
    manager_ip = config.get('wazuh_manager_ip', '127.0.0.1')
    user = 'admin'
    password = ''
    if WAZUH_PASSWORD_FILE.exists():
        password = WAZUH_PASSWORD_FILE.read_text().strip()
    return manager_ip, user, password

async def fetch_wazuh_alert_summary(time_range="now-24h"):
    """
    Fetches alert summary from Wazuh Indexer (OpenSearch).
    Returns a dictionary with counts for different severity levels.
    """
    manager_ip, user, password = get_wazuh_credentials()
    url = f"https://{manager_ip}:9200/wazuh-alerts-*/_search"
    
    # Aggregation query
    query = {
        "size": 0,
        "query": {
            "range": {
                "@timestamp": {
                    "gte": time_range
                }
            }
        },
        "aggs": {
            "severity_levels": {
                "terms": {
                    "field": "rule.level",
                    "size": 20
                }
            }
        }
    }

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            response = await client.post(
                url, 
                json=query, 
                auth=(user, password)
            )
            response.raise_for_status()
            data = response.json()
            
            buckets = data.get('aggregations', {}).get('severity_levels', {}).get('buckets', [])
            
            summary = {
                'critical': 0, # >= 13
                'severe': 0,   # 10-12
                'moderate': 0, # 5-9
                'light': 0,    # < 5
                'total': data.get('hits', {}).get('total', {}).get('value', 0)
            }
            
            for bucket in buckets:
                level = int(bucket['key'])
                count = bucket['doc_count']
                
                if level >= 13:
                    summary['critical'] += count
                elif level >= 10:
                    summary['severe'] += count
                elif level >= 5:
                    summary['moderate'] += count
                else:
                    summary['light'] += count
                    
            return summary
            
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return None

def generate_report_text(summary):
    if not summary:
        return "Error fetching report data from Wazuh Indexer."
        
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report = f"""
REEF SECURITY REPORT
Generated: {now}
Period: Last 24 Hours
----------------------------------------

SECURITY ALERT SUMMARY
----------------------
Total Alerts:   {summary['total']}

SEVERITY BREAKDOWN
------------------
[CRITICAL]  (Level 13+):  {summary['critical']}
[SEVERE]    (Level 10-12): {summary['severe']}
[MODERATE]  (Level 5-9):   {summary['moderate']}
[LIGHT]     (Level <5):    {summary['light']}

----------------------------------------
End of Report
    """
    return report.strip()
