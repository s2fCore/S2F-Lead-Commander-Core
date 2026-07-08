import os
import sys
import time
import random
import re
import requests
import psycopg2
from bs4 import BeautifulSoup
from urllib.parse import quote
from playwright.sync_api import sync_playwright

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, BROWSER_CDP_URL
)

LOG_FILE_PATH = "/opt/b2b-agent/mail_data/scraper_execution.log"

def get_agents():
    return [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/122.0"
    ]

def write_raw_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [MAPS_HARVESTER] {message}\n"
    print(message)
    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        with open(LOG_FILE_PATH, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[-] Failed to write to log file: {e}")

def verify_tor_circuit_health():
    proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
    for attempt in range(1, 6):
        try:
            res = requests.get("https://check.torproject.org/api/ip", proxies=proxies, timeout=5)
            if res.status_code == 200:
                write_raw_log(f"[♻️ Tor SOCKS5] Circuit verified healthy. Outbound Tor IP: {res.json().get('IP', 'Unknown')}")
                return True
        except Exception:
            write_raw_log(f"[♻️ Tor SOCKS5] Standalone Maps Tor proxy is still bootstrapping. Sleeping 5s (Attempt {attempt}/5)...")
            time.sleep(5)
    return False

def simulate_human_navigation(page, feed_element):
    try:
        for _ in range(random.randint(2, 3)):
            x = random.randint(150, 450)
            y = random.randint(150, 650)
            page.mouse.move(x, y)
            page.wait_for_timeout(random.randint(400, 1000))
        for _ in range(random.randint(3, 4)):
            scroll_y = random.randint(600, 1100)
            page.evaluate(f"arg => arg.scrollBy(0, {scroll_y})", feed_element)
            page.wait_for_timeout(random.randint(1500, 3200))
    except Exception:
        pass

def harvest_google_maps_standalone(query):
    write_raw_log(f"=== STARTING STANDALONE MAPS HARVEST FOR: '{query}' ===")
    
    # Initialize URL globally to protect fallback scopes
    maps_url = f"https://www.google.com/maps/search/{quote(query)}"

    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        write_raw_log(f"[-] PostgreSQL connection error: {str(e)}")
        return

    stealth_js = "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    discovered_leads = []

    # Tier 1: Direct, un-proxied connection (Bypasses Tor exit-node blocks)
    with sync_playwright() as p:
        try:
            write_raw_log(f"[+] Connecting to CDP: {BROWSER_CDP_URL}")
            browser = p.chromium.connect_over_cdp(BROWSER_CDP_URL)
            context = browser.new_context(
                user_agent=random.choice(get_agents()),
                viewport={"width": 1280, "height": 900},
                ignore_https_errors=True
            )
            context.add_cookies([{
                "name": "CONSENT",
                "value": "YES+cb.20230531-15-p0.en+FX+902",
                "domain": ".google.com",
                "path": "/"
            }])
            page = context.new_page()
            page.add_init_script(stealth_js)

            write_raw_log(f"[+] Loading Google Maps search panel (Direct connection)...")
            page.goto(maps_url, timeout=20000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)

            feed = page.query_selector('div[role="feed"]')
            if feed:
                write_raw_log("[+] Sourced results sidebar. Simulating human scrolling feeds...")
                simulate_human_navigation(page, feed)

            soup = BeautifulSoup(page.content(), 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '').strip()
                if href.startswith('http') and not any(d in href for d in ["google.com", "gstatic.com", "google.co.uk", "google-analytics.com"]):
                    discovered_leads.append(href)
            browser.close()
        except Exception as e:
            # Tier 2: Tor SOCKS5 Fallback (Only if direct connection fails)
            write_raw_log(f"    [⚠️ RETRY] Direct Maps load failed ({e}). Retrying via SOCKS5 Tor Proxy...")
            tor_active = verify_tor_circuit_health()
            if tor_active:
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.connect_over_cdp(BROWSER_CDP_URL)
                        context = browser.new_context(
                            user_agent=random.choice(get_agents()),
                            viewport={"width": 1280, "height": 900},
                            ignore_https_errors=True,
                            proxy={"server": "socks5://172.17.0.1:9050"}
                        )
                        context.add_cookies([{
                            "name": "CONSENT",
                            "value": "YES+cb.20230531-15-p0.en+FX+902",
                            "domain": ".google.com",
                            "path": "/"
                        }])
                        page = context.new_page()
                        page.add_init_script(stealth_js)
                        page.goto(maps_url, timeout=20000, wait_until="domcontentloaded")
                        page.wait_for_timeout(4000)

                        feed = page.query_selector('div[role="feed"]')
                        if feed:
                            simulate_human_navigation(page, feed)

                        soup = BeautifulSoup(page.content(), 'html.parser')
                        for a_tag in soup.find_all('a', href=True):
                            href = a_tag.get('href', '').strip()
                            if href.startswith('http') and not any(d in href for d in ["google.com", "gstatic.com", "google.co.uk", "google-analytics.com"]):
                                discovered_leads.append(href)
                        browser.close()
                except Exception as e_tor:
                    write_raw_log(f"    [-] Tor SOCKS5 Maps session failed: {e_tor}")

    unique_domains = list(set(discovered_leads))
    write_raw_log(f"[+] Sourced {len(unique_domains)} unique domains from Maps DOM. Ingesting to PostgreSQL...")

    inserted_count = 0
    for target_url in unique_domains:
        parsed_domain = re.sub(r'^https?://(www\.)?', '', target_url).split('/')[0]
        base_url = f"https://{parsed_domain}"
        lead_name = parsed_domain.split('.')[0].title()

        cursor.execute("SELECT id FROM sportswear_leads WHERE map_url = %s OR name = %s;", (base_url, lead_name))
        if cursor.fetchone():
            continue

        try:
            cursor.execute("""
                INSERT INTO sportswear_leads (name, map_url, raw_details, scan_status)
                VALUES (%s, %s, %s, 'Pending');
            """, (lead_name, base_url, f"Google Maps Sourced: {query}"))
            conn.commit()
            inserted_count += 1
        except Exception as db_err:
            conn.rollback()

    cursor.close()
    conn.close()
    write_raw_log(f"=== HARVEST COMPLETE: INGESTED {inserted_count} NEW 'PENDING' LEADS ===")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        search_query = " ".join(sys.argv[1:])
    else:
        search_query = "wrestling academy in ohio"
    harvest_google_maps_standalone(search_query)
