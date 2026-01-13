# Déploiement automatisé et sécurisé d’une infrastructure PME

## Présentation du projet

Ce projet vise à concevoir et déployer une infrastructure informatique **clé-en-main**, sécurisée et reproductible, destinée aux petites et moyennes entreprises (PME).
L’objectif est de permettre une **mise en production rapide et fiable** des services essentiels, en s’appuyant sur des outils d’**Infrastructure as Code (IaC)** afin de limiter les erreurs humaines et de faciliter la maintenance.

---

## Objectifs

- Automatiser le déploiement d’une infrastructure complète
- Intégrer les bonnes pratiques de cybersécurité dès la conception
- Proposer une architecture réaliste et adaptée aux contraintes d’une PME
- Fournir une solution facilement maintenable et évolutive

---

## 1. Services automatisés déployés

### 1.1 Services réseau de base

- **DNS**
  - Résolution de noms interne
  - Facilite la gestion et l’évolution des services
- **NTP**
  - Synchronisation temporelle des systèmes
  - Indispensable pour la cohérence des logs et la sécurité
- **Pare-feu**
  - Filtrage strict des flux réseau
  - Politique *deny by default*

---

### 1.2 Accès sécurisé à l’infrastructure

- **VPN (WireGuard)**
  - Accès distant chiffré pour les administrateurs
  - Aucun service d’administration exposé directement sur Internet
- **SSH**
  - Accès administrateur sécurisé
  - Authentification par clé uniquement

---

### 1.3 Hébergement applicatif

- **Serveur Web (Nginx)**
  - Hébergement de services internes ou publics
  - Support du chiffrement HTTPS
- **Application métier conteneurisée**
  - Déploiement via Docker
  - Isolation des services et portabilité

---

### 1.4 Gestion des données

- **Base de données (PostgreSQL / MariaDB)**
  - Stockage des données applicatives
  - Accès restreint au réseau interne
- **Sauvegardes automatisées**
  - Sauvegardes planifiées
  - Données chiffrées

---

### 1.5 Supervision et journalisation

- **Monitoring (Grafana)**
  - Surveillance de l’état des services et des ressources
  - Alertes en cas d’incident
- **Centralisation des logs (Loki / rsyslog)**
  - Centralisation des journaux système et applicatifs
  - Aide à l’analyse et au diagnostic des incidents

---

## 2. Organisation réseau

L’infrastructure est segmentée en plusieurs zones réseau afin de limiter la surface d’attaque et de confiner les incidents de sécurité.

- **Réseau interne (serveurs)**
  Services critiques : base de données, sauvegardes, supervision
- **Réseau administration**
  Accès réservé aux administrateurs via VPN
- **DMZ (services exposés)**
  Services accessibles depuis Internet (serveur web)
- **Segmentation réseau**
  Communication limitée aux flux strictement nécessaires

---

## 3. Infrastructure as Code (IaC)

### 3.1 Terraform – Provisionnement de l’infrastructure

**Rôle principal : créer l’infrastructure**

Terraform est utilisé pour :
- Créer les machines virtuelles
- Configurer le réseau (sous-réseaux, règles de pare-feu)
- Déployer une infrastructure reproductible
- Garantir l’idempotence (même résultat à chaque exécution)

---

### 3.2 Ansible – Configuration et sécurisation

**Rôle principal : configurer les systèmes**

Ansible est utilisé pour :
- Installer et configurer les services (VPN, Web, base de données)
- Appliquer le durcissement des systèmes (hardening)
- Gérer les utilisateurs et les droits
- Déployer les applications
- Mettre en place la supervision et les sauvegardes

---

### 3.3 Chaîne d’automatisation

Terraform
  → Création des VM et du réseau
      ↓
Ansible
  → Sécurisation des systèmes
  → Installation des services
  → Déploiement applicatif

---

## 4. Sécurité intégrée dès la conception

### 4.1 Principes appliqués

- Principe du moindre privilège
- Sécurité par défaut
- Défense en profondeur

### 4.2 Mesures mises en œuvre

- Accès SSH par clé uniquement
- Chiffrement des flux (TLS, VPN)
- Segmentation réseau
- Journalisation centralisée
- Sauvegardes chiffrées

---

## 5. Démonstration du projet

### Scénario de démonstration

1. Infrastructure vierge
2. Lancement du déploiement automatisé
3. Infrastructure opérationnelle en quelques minutes
4. Connexion VPN
5. Accès sécurisé à l’application
6. Déclenchement d’une alerte de supervision

---

## 6. Livrables du projet

- Dépôt Git contenant les scripts Terraform et Ansible
- Schémas d’architecture
- Documentation utilisateur à destination d’une PME

## 7. How to Run

To run the application, you can use the installed `reef` command.

1.  **Install the package (and dependencies):**
    ```bash
    pip install -e .
    ```

2.  **Usage:**
    *   **Graphical Interface (Web Dashboard):**
        ```bash
        reef
        ```
        This will start the web server and open the dashboard in your browser (default: `http://localhost:8080`).

    *   **Command Line Interface (CLI):**
        ```bash
        reef --cli
        # or verify help
        reef --help
        ```
        The CLI allows you to configure, deploy, and manage the infrastructure directly from the terminal.


