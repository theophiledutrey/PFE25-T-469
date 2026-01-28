import httpx
import datetime
from pathlib import Path
from fpdf import FPDF
from reef.manager.core import load_current_config

WAZUH_PASSWORD_FILE = Path(__file__).parent.parent / "ansible" / "inventory" / "wazuh-admin-password.txt"

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
    Fetches comprehensive data for the report ONLY from Indexer (9200).
    Aggregates alerts to infer agent activity, ignoring Port 55000.
    """
    manager_ip, user, password = get_wazuh_credentials()
    
    # limits
    top_alerts_limit = 5
    
    data_out = {
        "summary": {'critical': 0, 'severe': 0, 'moderate': 0, 'light': 0, 'total': 0},
        "top_alerts": [],
        "agents": [],
        "period": time_range
    }

    indexer_url = f"https://{manager_ip}:9200/wazuh-alerts-*/_search"

    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        
        # 1. Summary Query
        summary_query = {
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
            resp_summary = await client.post(indexer_url, json=summary_query, auth=(user, password))
            if resp_summary.status_code == 200:
                s_data = resp_summary.json()
                data_out["summary"]['total'] = s_data.get('hits', {}).get('total', {}).get('value', 0)
                buckets = s_data.get('aggregations', {}).get('severity_levels', {}).get('buckets', [])
                for b in buckets:
                    level = int(b['key'])
                    count = b['doc_count']
                    if level >= 13:
                        data_out["summary"]['critical'] += count
                    elif level >= 10:
                        data_out["summary"]['severe'] += count
                    elif level >= 5:
                        data_out["summary"]['moderate'] += count
                    else:
                        data_out["summary"]['light'] += count
                else:
                    print(f"Error fetching summary: Status {resp_summary.status_code} - {resp_summary.text}")
        except Exception as e:
            print(f"Error fetching summary: {e}")

        # 2. Top Alerts Query
        top_query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"range": {"@timestamp": {"gte": time_range}}}
                    ],
                    "must_not": [
                        {"term": {"rule.level": 0}}
                    ]
                }
            },
            "aggs": {
                "top_rules": {
                    "terms": {
                        "field": "rule.description",
                        "size": top_alerts_limit
                    },
                    "aggs": {
                        "max_level": {
                            "max": {
                                "field": "rule.level"
                            }
                        }
                    }
                }
            }
        }
        
        try:
            resp_top = await client.post(indexer_url, json=top_query, auth=(user, password))
            if resp_top.status_code == 200:
                t_data = resp_top.json()
                buckets = t_data.get('aggregations', {}).get('top_rules', {}).get('buckets', [])
                for b in buckets:
                    data_out["top_alerts"].append({
                        "description": b['key'],
                        "count": b['doc_count'],
                        "level": int(b.get('max_level', {}).get('value', 0))
                    })
                else:
                    print(f"Error fetching top alerts: Status {resp_top.status_code} - {resp_top.text}")
        except Exception as e:
            print(f"Error fetching top alerts: {e}")

        # 3. Active Agents Query (Replacing API call)
        agents_query = {
             "size": 0,
             "query": {
                 "range": {
                     "@timestamp": {
                         "gte": time_range
                     }
                 }
             },
             "aggs": {
                 "agents": {
                     "terms": {
                         "field": "agent.name",
                         "size": 100
                     },
                     "aggs": {
                         "ips": {
                             "terms": {
                                 "field": "agent.ip",
                                 "size": 1
                             }
                         }
                     }
                 }
             }
        }

        try:
            resp_agents = await client.post(indexer_url, json=agents_query, auth=(user, password))
            if resp_agents.status_code == 200:
                a_data = resp_agents.json()
                buckets = a_data.get('aggregations', {}).get('agents', {}).get('buckets', [])
                for b in buckets:
                    agent_name = b['key']
                    ip_buckets = b.get('ips', {}).get('buckets', [])
                    agent_ip = ip_buckets[0]['key'] if ip_buckets else "Unknown"
                    
                    data_out["agents"].append({
                        "name": agent_name,
                        "ip": agent_ip,
                        "status": "active",
                        "os": {"name": "N/A (Logs)"}
                    })
                else:
                    print(f"Error fetching agents: Status {resp_agents.status_code} - {resp_agents.text}")
        except Exception as e:
            print(f"Error fetching agents from logs: {e}")

    return data_out

class PDFReport(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(30, 41, 59) # Slate 800
        self.cell(0, 10, 'Rapport de Sécurité REEF', new_x="LMARGIN", new_y="NEXT", align='L')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}} - Généré par REEF Manager', align='C')

def generate_report_pdf(data):
    pdf = PDFReport()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Colors
    COLOR_PRIMARY = (15, 23, 42) # Slate 900
    COLOR_SECONDARY = (100, 116, 139) # Slate 500
    COLOR_ACCENT = (14, 165, 233) # Sky 500
    COLOR_DANGER = (239, 68, 68) # Red 500
    COLOR_WARNING = (245, 158, 11) # Amber 500
    COLOR_SUCCESS = (16, 185, 129) # Emerald 500

    # Timestamp
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(*COLOR_SECONDARY)
    now_str = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
    pdf.cell(0, 10, f"Date du rapport : {now_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # 1. Executive Summary (Audit Rapide)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, "1. Synthèse de l'Audit", new_x="LMARGIN", new_y="NEXT")
    pdf.set_line_width(0.5)
    pdf.set_draw_color(*COLOR_ACCENT)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(5)

    # Calculate global score/assessment (Simplified logic for PME)
    total_alerts = data['summary']['total']
    criticals = data['summary']['critical']
    # Calculate global score/assessment (Simplified logic for PME)
    total_alerts = data['summary']['total']
    criticals = data['summary']['critical']
    severes = data['summary']['severe']
    moderate = data['summary']['moderate']

    # Risk Metrics Calculation
    # Score weight: Critical(10), Severe(5), Moderate(1)
    exposure_score = (criticals * 10) + (severes * 5) + (moderate * 1)
    
    if exposure_score > 2000:
        exposure_level = "CRITIQUE (Action Immédiate)"
        exposure_color = COLOR_DANGER
    elif exposure_score > 1000:
        exposure_level = "ÉLEVÉ (Surveillance Requise)"
        exposure_color = COLOR_WARNING
    else:
        exposure_level = "FAIBLE (Situation Maîtrisée)"
        exposure_color = COLOR_SUCCESS

    # Scope of Impact Calculation
    # Based on diversity of alerts and criticality
    if criticals > 5:
        impact_scope = "LARGE (Système Compromis)"
        impact_color = COLOR_DANGER
    elif criticals > 0:
         impact_scope = "CIBLÉE (Menace Isolée)"
         impact_color = COLOR_WARNING
    elif severes > 10:
         impact_scope = "ÉTENDUE (Multiples Alertes)"
         impact_color = COLOR_WARNING
    else:
         impact_scope = "LIMITÉE (Maintenance / Bruit)"
         impact_color = COLOR_SUCCESS
    
    if criticals > 0:
        status_text = "CRITIQUE"
        status_color = COLOR_DANGER
        advice = "Des menaces critiques ont été détectées. Une intervention immédiate est requise."
    elif severes > 5:
        status_text = "À RISQUE"
        status_color = COLOR_WARNING
        advice = "Niveau d'alerte élevé. Veuillez examiner les incidents sévères."
    elif total_alerts > 2000: # Arbitrary anomaly
        status_text = "ANORMAL"
        status_color = COLOR_WARNING
        advice = "Volume d'activité inhabituel. Vérifiez s'il s'agit d'une attaque ou d'un bruit de fond."
    else:
        status_text = "SAIN"
        status_color = COLOR_SUCCESS
        advice = "Le niveau de sécurité est nominal. Aucune menace majeure détectée."

    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(40, 10, "État Global : ", align='L')
    pdf.set_text_color(*status_color)
    pdf.cell(0, 10, status_text, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 10, status_text, new_x="LMARGIN", new_y="NEXT")

    # Exposure & Impact Display
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(50, 50, 50)
    
    pdf.cell(45, 8, "Niveau d'Exposition : ", align='L')
    pdf.set_text_color(*exposure_color)
    pdf.cell(0, 8, exposure_level, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_text_color(50, 50, 50)
    pdf.cell(45, 8, "Portée de l'Impact : ", align='L')
    pdf.set_text_color(*impact_color)
    pdf.cell(0, 8, impact_scope, new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 8, advice)
    pdf.ln(10)

    # 2. Infrastructure Status
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, "2. État du Parc Informatique", new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(5)

    if not data['agents']:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 10, "Aucun agent détecté.", new_x="LMARGIN", new_y="NEXT")
    else:
        # Table Header
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(240, 240, 240)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(100, 8, "Nom de la machine", 1, 0, 'L', True)
        pdf.cell(90, 8, "Mises à jour (OS)", 1, 1, 'C', True)

        # Rows
        pdf.set_font('Helvetica', '', 10)
        for agent in data['agents']:
            name = agent.get('name', 'Unknown')
            # ip = agent.get('ip', 'Unknown') # Removed per request
            status = agent.get('status', 'Unknown')
            
            # Logic for Updates (Placeholder as we only have logs)
            # If status (activity) is active, we assume we are monitoring it.
            # Without vulnerability-detector data, we can't be sure of "Up to Date".
            if status == "active":
                update_text = "Sous Surveillance" # Under Surveillance
                pdf.set_text_color(*COLOR_SUCCESS)
            else:
                update_text = "Inconnu"
                pdf.set_text_color(*COLOR_SECONDARY)

            pdf.cell(100, 8, name, 1, 0, 'L')
            
            # Color logic for the cell content
            # update_text is already determined above
            
            pdf.cell(90, 8, update_text, 1, 1, 'C')

    pdf.ln(10)

    # 3. Security Alerts Details
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, "3. Activité de Sécurité (24h)", new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(5)

    # Stats Grid
    s = data['summary']
    pdf.set_font('Helvetica', '', 11)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(0, 10, f"Total des événements analysés : {s['total']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Simplified stats boxes
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(45, 10, f"Critiques: {s['critical']}", border=1, align='C')
    pdf.cell(45, 10, f"Sévères: {s['severe']}", border=1, align='C')
    pdf.cell(45, 10, f"Modérés: {s['moderate']}", border=1, align='C')
    pdf.cell(45, 10, f"Légers: {s['light']}", border=1, align='C')
    pdf.ln(15)

    # Top Alerts
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, "Top 5 des événements les plus fréquents :", new_x="LMARGIN", new_y="NEXT")
    
    if not data['top_alerts']:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 10, "Aucun événement significatif remonté.", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font('Helvetica', '', 10)
        for alert in data['top_alerts']:
            count = alert['count']
            desc = alert['description']
            level = alert['level']
            
            # Bullet point
            clean_desc = desc.replace("\n", " ")[:80] + "..." if len(desc) > 80 else desc
            pdf.cell(10, 8, f"- ({count})", align='R')
            
            # Color code level
            if level >= 10: pdf.set_text_color(*COLOR_DANGER)
            elif level >= 5: pdf.set_text_color(*COLOR_WARNING)
            else: pdf.set_text_color(0, 0, 0)
            
            pdf.cell(0, 8, f"Niv.{level} : {clean_desc}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)

    # 4. Recommendations
    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(*COLOR_PRIMARY)
    pdf.cell(0, 10, "4. Recommandations", new_x="LMARGIN", new_y="NEXT")
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(5)

    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(50, 50, 50)
    
    recos = []
    if s['critical'] > 0:
        recos.append("Priorité absolue : Analysez les alertes critiques immédiatement sur le Dashboard Wazuh.")
    if "disconnected" in [a.get('status') for a in data['agents']]:
        recos.append("Maintenance : Un ou plusieurs agents sont déconnectés. Vérifiez la connectivité réseau ou l'état du service.")
    if s['light'] > 1000 and s['critical'] == 0:
        recos.append("Optimisation : Beaucoup de bruit (alertes légères). Envisagez d'ajuster les règles de détection.")
    
    if not recos:
        recos.append("Aucune action urgente requise. Continuez la surveillance régulière.")

    for i, reco in enumerate(recos, 1):
        pdf.multi_cell(0, 6, f"{i}. {reco}")
        pdf.ln(2)

    return pdf.output()