# S2F-Core: Telemetry Harvester (High-Yield Local B2B Lead Harvesting)

S2F-Core is an enterprise-grade, high-yield local B2B lead harvesting and multi-channel outbound CRM pipeline engineered and owned exclusively by S2F Sportswear. Designed for high-volume B2B and B2C operations, the engine autonomously extracts, qualifies, and initiates outreach to prospective athletic brands, local sports clubs, and training centers globally.

The system utilizes headless browser rendering, Tor-gated connection routing, local linguistic evaluation models, and international phonebook carrier-line verification to systematically extract, qualify, and initiate highly targeted outbound operations, completely bypassing standard search index rate limits and bot-detection blocks.

---

## Project Leadership & Heuristic Credits
* **Systems Architect & Founder:** Abubakr Ahmed (info@ahmed.com.pk)
* **Corporate Identity:** Matrix Engineered Systems
* **Founder Background:** Startup Founder, Systems Architect, and Industrial Operations Director with a proven track record of engineering high-performance automation pipelines and enterprise-grade B2B infrastructure.
* **Active Brand Portfolio:**
  * **S2F Sportswear:** @s2fsportswear (https://instagram.com/s2fsportswear) (High-end custom sublimated team wear and combat sports apparel manufacturing)
* **Areas of Expertise:** Enterprise Systems Architecture, Multidisciplinary B2B/B2C Infrastructure, Industrial Automation, Supply-Chain Optimization, Full-Stack Product Lifecycle Engineering.
* **Operational Node:** Sialkot, Pakistan

### The Local-Resource Thesis
S2F-Core was engineered to solve a manual business-sourcing challenge. Operating from Sialkot, Pakistan—a global epicenter of sports equipment and technical apparel manufacturing—the system was architected from a unique, practical perspective: combining physical manufacturing logistics with software automation.

The core design thesis is to run a high-performance outbound pipeline with zero recurring API costs. The only required investments are standard host hardware and an internet connection. By leveraging exclusively self-hosted, local resources—such as local language models (Ollama), local SOCKS5 Tor network routing, and offline phonebook carrier classification libraries—the engine bypasses the need for expensive third-party scrapers, API subscriptions, or proxy pools.

This engine incorporates sophisticated human-like pacing, randomized delay gates, pre-flight DNS MX-record verifications, and direct opt-out reply routing to respect consumer inbox privacy, actively preventing digital noise pollution while operating with minimal financial overhead.

*Notice: This system represents proprietary operational technology. All custom ingestion crawlers, multi-channel Discord telemetry, and self-healing regional phone validation libraries are proprietary intellectual assets of S2F Sportswear, Matrix Engineered, and Abubakr Ahmed.*

---

## Core Architecture & Methods

The pipeline operates on a relational state model using a local PostgreSQL database as the central clearinghouse. The pipeline runs continuously across independent, stateless services:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      1. INGESTION & HARVESTING                         │
│ • Sourcing: Yahoo Direct + Google Maps CDP scrolling (Fast Commit)     │
│ • Regex Sweep: Captures Emails, Phones, Socials on full un-cut DOM     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Direct DB Ingestion)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     2. QUALIFICATION & SCORING                         │
│ • Qwen2.5:7b: Token-capped (256), 6-cores thread-locked CPU parsing     │
│ • Logic: Drops directories & competitor domains (Niche-relevance gate) │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ (Sharded Telemetry Routing)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        3. TELEMETRY GATEWAY                            │
│ • CHANNEL_ALPHA  : Email Found + Socials (Active Email Queue)          │
│ • CHANNEL_ALPHA_1: Socials Found, No Email (Manual Social Queue)       │
│ • CHANNEL_BETA   : Fallbacks, data anomalies, daily summary reports    │
└────────────────────────────────────────────────────────────────────────┘
                                   │ (Outbound Campaign Execution)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  4. TIMEZONE-AWARE CAMPAIGN DISPATCH                   │
│ • bulk_sender.py: Active timezone verification (Only delivers 9am-5pm) │
│ • SMTP Rotator: Alternates Resend (Tier 1), Brevo (Tier 2), Mailgun (T3)│
│ • Control: Appends "INTERESTED", "LATER", "UNSUBSCRIBE" user footer    │
└────────────────────────────────────────────────────────────────────────┘
```

### Advanced Ingest & Evasion Techniques
* **Non-Authenticated Sourcing (Stealth Ingestion):** Bypasses social media platform login walls by querying duckduckgo's static HTML search index and extracting public profile bios directly from cached search snippets.
* **Relational Competitor & Exporter Filtering:** Instantly detects and filters out regional competitors or wholesale exporters (e.g., Sialkot, Punjab or Chinese direct factories) using a combination of fast regex scans on clean body text and Qwen-driven semantic fit evaluations.
* **Multi-Layer Network Fallback:** Direct crawler connections land on pages passing authentic search-engine referrers. If blocked, the crawler automatically retries through a local Tor SOCKS5 proxy, executing automated circuit/IP rotations (SIGNAL NEWNYM) before retrying.
* **WhatsApp Standardization:** Formats raw phone numbers into standardized international formats using Google's libphonenumbers engine, outputting clean warning tags if the country/region is unresolved to allow manual review.

---

## System Requirements & Prerequisites

The system is highly optimized to run as a set of lightweight microservices communicating via transactional states. Minimum and recommended hardware guidelines for deployment:

* **Operating System:** Debian 12/13 or Ubuntu 22.04/24.04 LTS (Optimized for Proxmox unprivileged LXC Containers).
* **Physical Memory:** 8 GB RAM minimum (12 GB recommended to support concurrent headless browser execution and local model memory caching).
* **System Swap:** 4 GB Swap space.
* **CPU Core Allocation:** 4 Cores minimum (6 Cores recommended to prevent thread-locking during local Ollama linguistic evaluations).

---

## Host Optimization & Setup (Debian 13)

To replicate this environment locally, refer to these step-by-step setup guides and configuration templates in the repository:

* **OS Kernel Socket Tuning:** Reference our guest OS TCP optimization blocks in [Debian 13 Setup Guide](./README.md#A-Apply-Kernel-Network-Tuning).
* **Database Schema Initialization:** Reconstruct your Postgres tables and indexes instantly using [schema.sql](./schema.sql).
* **Container Orchestration Setup:** Spin up your PostgreSQL, Browserless, and Mail container services using [docker/docker-compose.yml.example](./docker/docker-compose.yml.example).
* **Python Environment Setup:** Initialize variables and active python paths using the templates in [scripts/s2f_env_config.py.example](./scripts/s2f_env_config.py.example).

---

## Step-by-Step Installation Guide

Follow these sequential commands to set up and run the entire pipeline inside a clean Debian or Ubuntu environment.

### 1. File System Initialization
Initialize your target directory tree structure:
```bash
sudo mkdir -p /opt/b2b-agent/docker
sudo mkdir -p /opt/b2b-agent/scripts
sudo mkdir -p /opt/b2b-agent/engines
sudo mkdir -p /opt/b2b-agent/config
sudo mkdir -p /opt/b2b-agent/postgres_data
sudo mkdir -p /opt/b2b-agent/ollama_models
sudo mkdir -p /opt/b2b-agent/mail_data/smtp_logs

# Align mail server directory permissions
sudo chown -R 1000:1000 /opt/b2b-agent/mail_data
```

### 2. Install Operating System Packages
Install dependencies for network routing, virtual envs, databases, and Tor SOCKS5 proxies:
```bash
sudo apt-get update && sudo apt-get install -y \
    curl git nano sudo procps net-tools rsync \
    python3-pip python3-venv python3-dev libpq-dev build-essential \
    tor torsocks libtorsocks tor-geoipdb
```

### 3. Configure Tor SOCKS5 and Control Ports
Configure your local Tor service to bind globally (allowing internal Docker containers to connect) and enable on-demand circuit rotations on port 9051:
```bash
# Append binding and security policy configurations
sudo echo "SocksPort 0.0.0.0:9050" >> /etc/tor/torrc
sudo echo "SocksPolicy accept 127.0.0.1" >> /etc/tor/torrc
sudo echo "SocksPolicy accept 172.17.0.0/16" >> /etc/tor/torrc
sudo echo "SocksPolicy reject *" >> /etc/tor/torrc
sudo echo "ControlPort 9051" >> /etc/tor/torrc
sudo echo "CookieAuthentication 0" >> /etc/tor/torrc

# Restart and enable Tor daemon on system boot
sudo systemctl daemon-reload
sudo systemctl enable tor
sudo systemctl restart tor

# Verify both SOCKS (9050) and Control (9051) ports are active
ss -tulpn | grep -E '9050|9051'
```

### 4. Initialize Python Virtual Environment
Initialize your isolated Python virtual environment and install dependencies:
```bash
# Create venv
python3 -m venv /opt/b2b-agent/venv

# Upgrade core pip tools
/opt/b2b-agent/venv/bin/pip install --upgrade pip setuptools wheel

# Install dependencies (Including Streamlit for the Web UI)
/opt/b2b-agent/venv/bin/pip install \
    psycopg2-binary==2.9.9 \
    requests==2.31.0 \
    beautifulsoup4==4.12.3 \
    playwright==1.42.0 \
    PySocks==1.7.1 \
    watchdog==4.0.0 \
    phonenumbers==9.0.33 \
    streamlit==1.35.0
```

### 5. Docker Containers Initialization
Create your /opt/b2b-agent/docker/docker-compose.yml configuration (see .example templates section below) and bring the services online:
```bash
cd /opt/b2b-agent/docker
docker compose up -d

# Verify that all 4 containers are running and healthy
docker ps
```

### 6. Relational Database Schema Setup
Execute the initialization query inside your Postgres container to build the tables and index trees:
```bash
docker exec -i b2b_postgres psql -U hunt_agent -d b2b_hunt_db << 'EOF'
CREATE TABLE IF NOT EXISTS sportswear_leads (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    map_url TEXT UNIQUE NOT NULL,
    external_website TEXT DEFAULT 'Pending',
    phone_number VARCHAR(50) DEFAULT 'Pending',
    scan_status VARCHAR(50) DEFAULT 'Pending',
    raw_details TEXT,
    apparel_gap TEXT DEFAULT 'Unanalyzed',
    calculated_margin NUMERIC DEFAULT 0.00,
    targeted_hook TEXT DEFAULT 'Pending',
    contact_name VARCHAR(255) DEFAULT 'Decision Maker',
    contact_title VARCHAR(255) DEFAULT 'Gym Owner / Head Coach',
    personal_email VARCHAR(255) DEFAULT 'Not Found',
    instagram_url VARCHAR(255),
    facebook_url VARCHAR(255),
    linkedin_url VARCHAR(255),
    tiktok_url TEXT,
    ai_winning_score INTEGER DEFAULT 0,
    ai_qualification_notes TEXT,
    email_stage INTEGER DEFAULT 1,
    last_delivery_attempt TIMESTAMP,
    delivery_status VARCHAR(50) DEFAULT 'Not Sent',
    postal_address VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_leads_scan_status ON sportswear_leads(scan_status);
CREATE INDEX IF NOT EXISTS idx_leads_map_url ON sportswear_leads(map_url);
CREATE UNIQUE INDEX IF NOT EXISTS sportswear_leads_name_key ON sportswear_leads(name);
EOF
```

### 7. Provision Local Qwen AI Weights
Pull your local qwen2.5:7b models directly inside your Docker AI brain:
```bash
docker exec -it b2b_ai_brain ollama run qwen2.5:7b "hello"
```

### 8. Configure Systemd Auto-Restart Supervision
To ensure the orchestrator starts instantly on boot and automatically restarts in case of a power crash or unhandled exception, register it as a Systemd service:
```bash
# 1. Write the service unit file
sudo cat << 'EOF' > /etc/systemd/system/s2f-orchestrator.service
[Unit]
Description=S2F Decoupled Microservices Orchestrator Daemon
After=network.target docker.service tor.service
Requires=docker.service tor.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/b2b-agent
ExecStart=/opt/b2b-agent/venv/bin/python3 -u /opt/b2b-agent/scripts/main_orchestrator.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/b2b-agent/mail_data/overnight_summary.log
StandardError=append:/opt/b2b-agent/mail_data/overnight_summary.log

[Install]
WantedBy=multi-user.target
EOF

# 2. Reload, enable, and start the managed daemon
sudo systemctl daemon-reload
sudo systemctl enable s2f-orchestrator.service
sudo systemctl start s2f-orchestrator.service
```

### 9. Configure the Automated Crontab
Open your cron editor (crontab -e) and register your Maildir reply tracker, outbox sender, and nightly reporting triggers:
```text
# 1. Every 30 minutes: Dispatch outbound campaign emails
*/30 * * * * /opt/b2b-agent/venv/bin/python3 /opt/b2b-agent/scripts/bulk_sender.py >> /opt/b2b-agent/mail_data/overnight_summary.log 2>&1

# 2. Every 15 minutes: Scan Maildir user folders for incoming replies or bounce-backs to log them in Postgres
*/15 * * * * /opt/b2b-agent/venv/bin/python3 /opt/b2b-agent/scripts/incoming_reply_handler.py >> /opt/b2b-agent/mail_data/overnight_summary.log 2>&1

# 3. Daily at 06:00 UTC: Compile and dispatch metrics summaries directly to Discord CHANNEL_BETA
0 6 * * * /opt/b2b-agent/venv/bin/python3 /opt/b2b-agent/scripts/overnight_reporter.py >> /opt/b2b-agent/mail_data/overnight_summary.log 2>&1
```

### 10. Initialize the Unified Web Admin Panel
To run the browser-based Streamlit operations dashboard securely in the background:
```bash
nohup /opt/b2b-agent/venv/bin/streamlit run /opt/b2b-agent/engines/web_ui.py \
    --server.port 8501 \
    --server.address 0.0.0.0 > /opt/b2b-agent/mail_data/overnight_summary.log 2>&1 &
```
Once running, the admin control panel is accessible via your browser at: `http://[your-host-ip]:8501`.
* **Zero-Code Operations:** Engineered to be fully operable by non-technical business owners, founders, and sales teams. Once deployed, the entire system can be managed, monitored, and executed via a clean, intuitive web interface without ever opening a terminal.

---

## Troubleshooting: Why Replications Fail (Common Pitfalls)
If you attempt to deploy this self-hosted architecture and encounter execution stalls or email delivery drops, it is almost always caused by one of these four system misconfigurations:

* **1. Cold Domain IPs & Lack of DNS Alignment:** Attempting outbound campaigns from a fresh, un-warmed domain or failing to align your SPF, DKIM, and DMARC records on your Cloudflare dashboard [2]. This results in emails going straight to spam or getting blocked at the SMTP gateway [2]. *Due to its complexity, our proprietary, data-backed Cloudflare DNS alignment blueprints are kept as exclusive, paid consultation information [2].*
* **2. Misconfigured Tor Control Ports:** Failing to expose and authenticate Port 9051 or SocksPort 9050 inside your guest OS, which breaks the pre-flight check, prevents dynamic IP rotations, and causes crawling fallbacks to fail [6].
* **3. Headless Browser Profiling:** Crawling heavy target directories using datacenter IPs or default browser configurations without mimicking natural human navigation (typing curves, mouse movements, scrolling), resulting in instant WAF blocks.
* **4. Database Parameter Mismatches:** Misconfiguring PostgreSQL authentication rules (pg_hba.conf) or failing to grant raw file execution permission to your Python virtual environment [6].

---

## Legal Disclaimer & Terms of Use
* S2F-Core is provided strictly for educational, research, and authorized internal lead-generation testing purposes.
* Users are 100% responsible for adhering to their regional and international anti-spam, privacy, and electronic communication laws (including but not limited to CAN-SPAM in the United States, GDPR in Europe, and PECR/Data Protection Act in the United Kingdom) [2].
* S2F Sportswear, Matrix Engineered, and Abubakr Ahmed assume absolute zero liability for any platform account bans, IP restrictions, domain blacklisting, or legal disputes resulting from the installation, replication, or usage of this software.

---

## Open-Source Shoutouts & Credits
This zero-overhead, highly optimized architecture would not be possible without the remarkable contributions of the open-source community. Special thanks to the creators of:
* **PostgreSQL:** For providing the rock-solid relational database engine [6].
* **Tor Project:** For enabling decentralized, anonymous, and unblocked routing pathways [6].
* **Playwright & BeautifulSoup4:** For advanced headless browser interaction and high-speed DOM parsing.
* **Poste.io:** For providing a clean, self-hosted, lightweight Maildir-driven SMTP container.
* **Resend, Brevo, & Mailgun:** For their excellent, developer-friendly SMTP relay APIs.

---

## System Status & Future Roadmap
* **Current Status:** Stable Operational Baseline (v1.0.0). The system is fully optimized, self-contained, and operating at its standard target level [6]. Regular maintenance updates are not required as all current parsing and fallback databases are synchronized [6]. the system is currently under standard administrative diagnostics [6].
* **Host Production Verification (Live Node Snapshot):**
  * **System Uptime:** `4 days, 18 hours` (Verified continuous background daemon execution)
  * **Host CPU Load Average:** `0.43 / 0.72 / 1.35` (Optimized resource allocation across 6 cores)
  * **Root Storage Usage:** `8% utilized` (Abundant local capacity for database scaling)
* **Future Roadmap (Planned Enhancements):**
  * **Automated Social Messaging:** Integrating direct, automated Instagram DM and WhatsApp outreach sequences via custom browser profiles [1].
  * **Multi-Search Engine Sourcing:** Expanding the initial maps harvest phase beyond Yahoo to include native automated Bing and local directory feeds [6].
  * **Advanced Data Refinement:** Implementing deeper NLP classification models to further clean and categorize incoming leads [6].

---

## Enterprise Services, Collaborations & Deployments
For brands looking to leverage the S2F Lead Commander Core without managing background server infrastructure, we offer three professional, paid service tiers, as well as **assisted installations for deserving setups and open-source collaborations (collabs)**:

* **1. Managed Cloud Hosting (SaaS):** Skip the proxy configurations, Docker setups, and local model compilation. We host a dedicated, high-speed, private instance of the pipeline for your brand. You simply receive qualified leads directly in your Discord channels.
* **2. On-Premises Custom Deployment & Cloud DNS Alignment:** Our systems engineering team will deploy, configure, and optimize the pipeline directly inside your AWS, Google Cloud, Proxmox VE, or local bare-metal environments—including guest kernel socket tuning and complete, secure Cloudflare SPF/DKIM/DMARC alignment [2, 6].
* **3. Custom CRM & Production Integration:** We design custom target search footprints and build dedicated API webhooks to link Lead Commander directly into your internal Salesforce, HubSpot, or manufacturing ERP systems.

For inquiries, custom deployments, open-source collaboration proposals, or assisted install requests, contact our technical operations team at **info@ahmed.com.pk**.
