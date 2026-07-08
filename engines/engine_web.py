import os
import sys
import json
import time
import random
import re
import gc
import socket
import requests
import psycopg2
from bs4 import BeautifulSoup
from urllib.parse import unquote, quote
from playwright.sync_api import sync_playwright

# Bind path to scripts environment directory
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, BROWSER_CDP_URL, AI_API_URL, AI_MODEL, GLOBAL_LOG_PATH
)

DOMAIN_BLACKLIST = [
    "companycheck.co.uk", "companieslist.co.uk", "gov.uk", "wikipedia.org", "yelp.co.uk", 
    "yellowpages", "worldorgs.com", "localgymsandfitness.com", "cylex", "local.com",
    "bloomberg.com", "reuters.com", "cnn.com", "nytimes.com", "forbes.com", "guardian",
    "bbc", "seekingalpha", "financialtimes", "marketwatch", "emis.com", "crunchbase.com",
    "zoominfo", "apollo.io", "dnb.com", "pitchbook", "google.com", "microsoft.com",
    "apple.com", "amazon.com", "github.com", "gitlab", "stackoverflow",
    "facebook.com", "instagram.com", "twitter.com", "youtube.com", "linkedin.com",
    "yelp.com", "tripadvisor.com", "yell.com", "trustpilot.com", "yandex.com", "yahoo.com"
]
COMPETITOR_BLACKLIST = [
    "sialkot", "pakistan", "manufacture in pakistan", "factory in pakistan", "made-in-china", "alibaba",
    "sri lanka", "bangladesh", "china", "japan", "tokyo", "dhaka", "colombo", "beijing", "shanghai"
]

def get_agents():
    return [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/122.0"
    ]

def write_raw_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [WEB_CRAWLER] {message}\n"
    print(message)
    try:
        os.makedirs(os.path.dirname(GLOBAL_LOG_PATH), exist_ok=True)
        with open(GLOBAL_LOG_PATH, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[-] Failed to write to log file: {e}")

def verify_tor_circuit_health():
    """Verifies Tor SOCKS5 proxy connectivity and logs the active outbound exit IP (Original Style)."""
    proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
    for attempt in range(1, 6):
        try:
            res = requests.get("https://check.torproject.org/api/ip", proxies=proxies, timeout=5)
            if res.status_code == 200:
                tor_data = res.json()
                write_raw_log(f"[♻️ Tor SOCKS5] Circuit healthy. Outbound Tor IP Resolved: {tor_data.get('IP', 'Unknown')} (Tor Active: {tor_data.get('IsTor', False)})")
                return True
        except Exception:
            write_raw_log(f"[♻️ Tor SOCKS5] Tor proxy is still bootstrapping circuits. Sleeping 5s (Attempt {attempt}/5)...")
            time.sleep(5)
    return False

def rotate_tor_ip():
    """Signals Tor control port to cycle exit node for a fresh IP address (Original Non-Blocking Style)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 9051))
        s.send(b'AUTHENTICATE ""\r\n')
        s.send(b'SIGNAL NEWNYM\r\n')
        s.close()
        write_raw_log("[♻️ Tor] Signaled NEWNYM: Dynamic exit node rotation triggered.")
        time.sleep(3)
        return True
    except Exception as e:
        write_raw_log(f"[-] Tor IP rotation signal failed: {e}")
    return False

def clean_extracted_text(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    text = soup.get_text(separator=" ")
    lines = [line.strip() for line in text.splitlines()]
    chunks = [phrase for phrase in lines if phrase]
    return " ".join(chunks)[:3000]

def clean_phone_number(phone_str):
    """Sanitizes raw phone matches to reduce false positives."""
    cleaned = re.sub(r'[^\d+]', '', phone_str)
    if len(cleaned) < 8 or len(cleaned) > 15:
        return None
    if cleaned.startswith(('12345', '012345', '99999')):
        return None
    return phone_str

def extract_contacts_and_socials(raw_html, base_url, page_context=None):
    """
    Extracts emails, phone numbers, and social media links.
    If details are missing, crawls discovered contact/about subpages to harvest them.
    Returns: email, phone, insta, fb, linkedin, tiktok, and any appended subpage text context.
    """
    soup = BeautifulSoup(raw_html, "html.parser")
    insta, fb, linkedin, tiktok = None, None, None, None
    discovered_subpages = []
    enriched_text_buffer = ""

    # 1. Gather Social Media Links & Identify Potential Contact Subpages from Homepage ONLY
    for a_tag in soup.find_all('a', href=True):
        href = a_tag.get('href', '').strip()
        href_lower = href.lower()
        
        # Social matching (Insta, FB, LinkedIn, TikTok)
        if "instagram.com" in href_lower and not any(p in href_lower for p in ["/p/", "/reel/", "/explore/"]):
            insta = href
        elif "facebook.com" in href_lower and not any(p in href_lower for p in ["/share", "/groups", "/events"]):
            fb = href
        elif "linkedin.com" in href_lower and not any(p in href_lower for p in ["/sharing", "/company-beta"]):
            linkedin = href
        elif "tiktok.com" in href_lower and not any(p in href_lower for p in ["/share", "/video/"]):
            tiktok = href
            
        # Discover contact-focused subpages (homepage only)
        if any(keyword in href_lower for keyword in ["contact", "about", "contact-us", "about-us", "terms"]):
            if href.startswith("/"):
                discovered_subpages.append(base_url.rstrip("/") + href)
            elif href.startswith("http") and base_url.split("//")[-1].split("/")[0] in href:
                discovered_subpages.append(href)

    # Clean unique subpages to prevent loops
    discovered_subpages = list(set(discovered_subpages))[:3]

    # Email Extraction Regex
    email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails_found = re.findall(email_regex, raw_html)
    valid_emails = [
        e.lower().strip() for e in emails_found 
        if not any(e.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.js', '.css'])
        and not any(x in e.lower() for x in ['sentry', 'reply', 'example', 'yourdomain', 'email@', 'wix'])
    ]
    placeholders = ["me@email.com", "email@email.com", "test@test.com", "user@domain.com", "yourname@gmail.com"]
    final_emails = [e for e in valid_emails if e not in placeholders and not e.endswith(".com.com")]
    email = list(set(final_emails))[0] if final_emails else "Not Found"

    # Phone Extraction Regex
    phone_regex = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?\d{9,15}'
    phones_found = re.findall(phone_regex, raw_html)
    valid_phones = []
    for p in phones_found:
        cleaned = clean_phone_number(p)
        if cleaned:
            valid_phones.append(cleaned)
    phone = list(set(valid_phones))[0] if valid_phones else "Pending"

    # Deep crawl subpages strictly if any info is missing
    info_missing = (email == "Not Found" or phone == "Pending" or not (insta and fb and linkedin and tiktok))
    
    if info_missing and page_context and discovered_subpages:
        for sub_url in discovered_subpages:
            try:
                write_raw_log(f"      ➔ Sourcing missing data on subpage: {sub_url}")
                page_context.goto(sub_url, timeout=10000, wait_until="domcontentloaded")
                sub_html = page_context.content()
                sub_soup = BeautifulSoup(sub_html, "html.parser")
                
                # Append subpage clean text context to buffer
                sub_text = clean_extracted_text(sub_html)
                enriched_text_buffer += f"\n[Subpage Content - {sub_url}]: {sub_text}"
                
                # Extract missing socials from subpages, but DO NOT append more subpages
                for a_tag in sub_soup.find_all('a', href=True):
                    sub_href = a_tag.get('href', '').strip()
                    sub_href_lower = sub_href.lower()
                    if not insta and "instagram.com" in sub_href_lower and not any(p in sub_href_lower for p in ["/p/", "/reel/", "/explore/"]):
                        insta = sub_href
                    elif not fb and "facebook.com" in sub_href_lower and not any(p in sub_href_lower for p in ["/share", "/groups", "/events"]):
                        fb = sub_href
                    elif not linkedin and "linkedin.com" in sub_href_lower and not any(p in sub_href_lower for p in ["/sharing", "/company-beta"]):
                        linkedin = sub_href
                    elif not tiktok and "tiktok.com" in sub_href_lower and not any(p in sub_href_lower for p in ["/share", "/video/"]):
                        tiktok = sub_href

                # Check for emails on subpage
                if email == "Not Found":
                    sub_emails = re.findall(email_regex, sub_html)
                    sub_valid = [
                        e.lower().strip() for e in sub_emails 
                        if not any(e.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'])
                        and not any(x in e.lower() for x in ['sentry', 'reply', 'example', 'yourdomain', 'email@'])
                    ]
                    sub_final = [e for e in sub_valid if e not in placeholders and not e.endswith(".com.com")]
                    if sub_final:
                        email = list(set(sub_final))[0]
                        write_raw_log(f"      ✔ Found email on subpage: {email}")

                # Check for phones on subpage
                if phone == "Pending":
                    sub_phones = re.findall(phone_regex, sub_html)
                    sub_v_phones = []
                    for sp in sub_phones:
                        cleaned_sp = clean_phone_number(sp)
                        if cleaned_sp:
                            sub_v_phones.append(cleaned_sp)
                    if sub_v_phones:
                        phone = list(set(sub_v_phones))[0]
                        write_raw_log(f"      ✔ Found phone on subpage: {phone}")

            except Exception:
                pass

    return email, phone, insta, fb, linkedin, tiktok, enriched_text_buffer

def simulate_human_navigation(page):
    try:
        for _ in range(random.randint(2, 4)):
            x = random.randint(150, 900)
            y = random.randint(150, 700)
            page.mouse.move(x, y)
            page.wait_for_timeout(random.randint(500, 1200))
        for _ in range(random.randint(2, 3)):
            scroll_y = random.randint(350, 750)
            page.evaluate(f"window.scrollBy(0, {scroll_y})")
            page.wait_for_timeout(random.randint(1200, 2800))
    except Exception:
        pass

def fetch_page_via_tor_fallback(url):
    headers = {"User-Agent": random.choice(get_agents()), "Referer": "https://duckduckgo.com/"}
    proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
    try:
        res = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        if res.status_code == 200:
            return res.text
    except Exception as e:
        write_raw_log(f"    [-] Tor fallback failed for {url}: {e}")
    return None

def query_qwen_footprints_survey():
    history = []
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT raw_details FROM sportswear_leads WHERE raw_details LIKE 'Web Harvest Query: %' LIMIT 20;")
        rows = cursor.fetchall()
        history = [r[0].replace("Web Harvest Query: ", "").strip() for r in rows if r[0]]
        cursor.close()
        conn.close()
    except Exception as e:
        write_raw_log(f"    [-] Failed to read search history: {e}")

    history_str = ", ".join(history) if history else "None"

    prompt = (
        "Generate a JSON array of 5 distinct, high-targeted search queries to find "
        "local combat sports clubs, wrestling academies, or BJJ teams globally (e.g. in USA, Netherlands, Switzerland, UK, or Brazil).\n\n"
        "CRITICAL QUERY SIMPLICITY RULE: Each search query must be extremely short, clean, and simple, consisting ONLY of [Business Niche] in [City/State/Country]. "
        "Do NOT append any business intent words like 'for sale', 'buying', 'custom', 'fightwear', 'uniforms', 'provider', 'bulk', or 'needs'. "
        "Keep them structured exactly like: 'wrestling academy in ohio', 'bjj gym amsterdam', 'grappling in zurich'.\n\n"
        f"CRITICAL HISTORY RULE: To ensure endless, un-repeated discovery, do NOT repeat or reuse any of these previously executed search markets: {history_str}. "
        "Respond ONLY with a valid raw JSON array of strings. Do not include markdown backticks or explaining text."
    )
    payload = {
        "model": AI_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": { "temperature": 0.5, "num_predict": 256, "num_thread": 6 }
    }
    try:
        res = requests.post(f"{AI_API_URL}/api/generate", json=payload, timeout=180)
        if res.status_code == 200:
            parsed_json = res.json().get("response", "[]").strip()
            data = json.loads(parsed_json)
            if isinstance(data, dict):
                temp_queries = []
                for k, v in data.items():
                    if isinstance(k, str) and len(k.strip()) > 5 and "query" not in k.lower():
                        temp_queries.append(k)
                    if isinstance(v, str) and len(v.strip()) > 5 and "query" not in v.lower():
                        temp_queries.append(v)
                return list(set(temp_queries))[:5]
            return data
    except Exception as e:
        write_raw_log(f"    [-] AI Market Survey generation failed: {str(e)}")
    return ["wrestling academy in ohio", "bjj amsterdam", "grappling gym zurich"]

def get_blacklist_matches(text_content, domain_url):
    combined_check = f"{text_content} {domain_url}".lower()
    matches = [keyword for keyword in COMPETITOR_BLACKLIST if keyword in combined_check]
    return matches

def clean_yahoo_url(url):
    """Parses target URL out of Yahoo redirect link tracking wrappers."""
    if "r.search.yahoo.com" in url:
        match = re.search(r'/RU=([^/&]+)', url)
        if match:
            return unquote(match.group(1))
    return url

def harvest_yahoo(query):
    """Primary harvester using Yahoo Search (Direct first, fallback to Tor SOCKS5)."""
    discovered = []
    
    headers = {
        "User-Agent": random.choice(get_agents()),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.yahoo.com/",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1"
    }
    url = f"https://search.yahoo.com/search?q={quote(query)}"
    
    # 1. Try Direct first
    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            for block in soup.select("div.compTitle a"):
                raw_url = block.get('href', '')
                if raw_url:
                    clean_url = clean_yahoo_url(raw_url)
                    if clean_url.startswith("http") and not any(d in clean_url for d in ["yahoo.com", "bing.com"]):
                        discovered.append(clean_url)
            if discovered:
                write_raw_log(f"    [+] Successfully harvested {len(discovered)} links via Yahoo Direct.")
                return list(set(discovered))[:6]
    except Exception as e:
        write_raw_log(f"    [-] Direct Yahoo search failed ({e}). Retrying via SOCKS5 Tor Proxy...")

    # 2. Try Tor Fallback if direct fails
    if not discovered:
        proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
        try:
            res = requests.get(url, headers=headers, proxies=proxies, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for block in soup.select("div.compTitle a"):
                    raw_url = block.get('href', '')
                    if raw_url:
                        clean_url = clean_yahoo_url(raw_url)
                        if clean_url.startswith("http") and not any(d in clean_url for d in ["yahoo.com", "bing.com"]):
                            discovered.append(clean_url)
                if discovered:
                    write_raw_log(f"    [♻️ Tor] Successfully harvested {len(discovered)} links via Yahoo over Tor.")
        except Exception as e_tor:
            write_raw_log(f"    [-] Tor Yahoo fallback failed: {e_tor}")
            
    return list(set(discovered))[:6]

def harvest_ddg_fallback(query):
    """Last resort fallback using DuckDuckGo via Tor SOCKS5."""
    discovered = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/122.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {'q': query}
    proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
    
    rotate_tor_ip()
    if verify_tor_circuit_health():
        try:
            res = requests.post("https://html.duckduckgo.com/html/", data=payload, headers=headers, proxies=proxies, timeout=15)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                for a_tag in soup.find_all('a'):
                    raw_url = a_tag.get('href', '')
                    if "uddg=" in raw_url:
                        match = re.search(r'uddg=([^&]+)', raw_url)
                        if match:
                            clean_url = unquote(match.group(1))
                            if not any(domain in clean_url for domain in ["google.com", "duckduckgo.com", "bing.com"]):
                                discovered.append(clean_url)
        except Exception as e_tor:
            write_raw_log(f"    [-] Tor DDG fallback failed: {str(e_tor)}")
            
    return list(set(discovered))[:6]

def harvest_search_results(query):
    """Unified search entrypoint."""
    results = harvest_yahoo(query)
    if not results:
        write_raw_log("    [⚠️ Fallback] Yahoo returned 0 results. Falling back to Tor DuckDuckGo...")
        results = harvest_ddg_fallback(query)
    return results

def execute_scraper_cycle():
    # Mandate Pre-Flight Tor Gating and explicit validation first
    write_raw_log("[♻️ Pre-Flight] Initiating mandatory Tor connection check...")
    rotate_tor_ip()
    if not verify_tor_circuit_health():
        write_raw_log("[❌ Tor Pre-Flight ERROR] Tor validation failed. Postponing scraper run for proxy circuit rebuild.")
        return

    write_raw_log("[🧠 AI] Executing memory-aware global market survey and geo-brainstorming...")
    queries = query_qwen_footprints_survey()
    write_raw_log(f"[🧠 AI] Brainstormed target geographical queries: {queries}")

    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        write_raw_log(f"[-] PostgreSQL connection error: {str(e)}")
        return

    stealth_js = "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"

    # Phase A1: Sourcing (Requests-Only) -> Sourced domains are ingested quietly as 'Pending'
    for query in queries:
        pacing_delay = random.uniform(15.0, 35.0)
        write_raw_log(f"[💤 Pacing] Sleeping for {pacing_delay:.1f} seconds to mimic human search behavior...")
        time.sleep(pacing_delay)
        
        write_raw_log(f"\n--- HARVESTING SEARCH TARGETS FOR: '{query}' ---")
        target_links = harvest_search_results(query)
        write_raw_log(f"[+] Sourced {len(target_links)} candidate domains from search indexes.")

        for target_url in target_links:
            parsed_domain = re.sub(r'^https?://(www\.)?', '', target_url).split('/')[0]
            base_url = f"https://{parsed_domain}"
            lead_name = parsed_domain.split('.')[0].title()

            # Skip irrelevant country TLDs (.jp, .cn, .bd, .lk) immediately during Yahoo parsing stage
            if any(parsed_domain.endswith(tld) for tld in [".jp", ".cn", ".bd", ".lk"]):
                continue

            cursor.execute("SELECT id FROM sportswear_leads WHERE map_url = %s OR name = %s;", (base_url, lead_name))
            if cursor.fetchone():
                continue

            try:
                cursor.execute("""
                    INSERT INTO sportswear_leads (name, map_url, raw_details, scan_status)
                    VALUES (%s, %s, %s, 'Pending')
                    ON CONFLICT DO NOTHING;
                """, (lead_name, base_url, f"Web Harvest Query: {query}"))
                conn.commit()
            except Exception as db_err:
                conn.rollback()

    # Phase A2: Active Queue Crawling (Playwright CDP) -> Crawls ALL 'Pending' records in PostgreSQL
    cursor.execute("SELECT id, map_url, raw_details FROM sportswear_leads WHERE scan_status = 'Pending' LIMIT 12;")
    pending_queue = cursor.fetchall()
    write_raw_log(f"\n[QUEUE_PROCESSOR] Sourced {len(pending_queue)} pending targets from PostgreSQL.")

    for lead_id, base_url, raw_details in pending_queue:
        parsed_domain = base_url.split("//")[-1].split('/')[0].lower()
        
        # Double-check TLD exclusions and expanded directory blacklists
        if any(parsed_domain.endswith(tld) for tld in [".jp", ".cn", ".bd", ".lk"]) or any(bd in parsed_domain for bd in DOMAIN_BLACKLIST):
            cursor.execute("UPDATE sportswear_leads SET scan_status = 'Skipped_NonTarget' WHERE id = %s;", (lead_id,))
            conn.commit()
            continue

        time.sleep(random.uniform(4.0, 8.0))
        write_raw_log(f"    ➔ Scraping landing page: {base_url}")
        page_content = None
        used_playwright = False
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(BROWSER_CDP_URL)
                context = browser.new_context(user_agent=random.choice(get_agents()), ignore_https_errors=True)
                page = context.new_page()
                page.add_init_script(stealth_js)
                page.goto(base_url, timeout=20000, wait_until="domcontentloaded", referer="https://duckduckgo.com/")
                
                simulate_human_navigation(page)
                page_content = page.content()
                
                # Shield 1 check: Filter geographic competitor terms on clean text
                clean_text_content = clean_extracted_text(page_content)
                matched_keywords = get_blacklist_matches(clean_text_content, base_url)
                if matched_keywords:
                    write_raw_log(f"    🛡️ [SHIELD] Dropped regional competitor: {base_url} (Matched terms: {matched_keywords})")
                    cursor.execute("UPDATE sportswear_leads SET scan_status = 'Skipped_NonTarget', raw_details = %s WHERE id = %s;", (f"{raw_details} | Matched: {matched_keywords}", lead_id))
                    conn.commit()
                    browser.close()
                    continue

                # Run extraction with active page context for subpage checks (Insta, FB, LinkedIn, TikTok, Enriched Text Buffer)
                lead_email, lead_phone, insta_url, fb_url, linkedin_url, tiktok_url, subpage_text = extract_contacts_and_socials(page_content, base_url, page_context=page)
                clean_text_content += subpage_text
                used_playwright = True
                browser.close()
        except Exception as e:
            write_raw_log(f"    [⚠️ RETRY] Direct load failed ({e}). Retrying via Playwright Tor Proxy...")
            try:
                with sync_playwright() as p:
                    browser = p.chromium.connect_over_cdp(BROWSER_CDP_URL)
                    context = browser.new_context(
                        user_agent=random.choice(get_agents()),
                        ignore_https_errors=True,
                        proxy={"server": "socks5://172.17.0.1:9050"}
                    )
                    page = context.new_page()
                    page.add_init_script(stealth_js)
                    page.goto(base_url, timeout=12000, wait_until="commit", referer="https://duckduckgo.com/")
                    
                    simulate_human_navigation(page)
                    page_content = page.content()
                    
                    clean_text_content = clean_extracted_text(page_content)
                    matched_keywords = get_blacklist_matches(clean_text_content, base_url)
                    if matched_keywords:
                        write_raw_log(f"    🛡️ [SHIELD] Dropped regional competitor: {base_url} (Matched: {matched_keywords})")
                        cursor.execute("UPDATE sportswear_leads SET scan_status = 'Skipped_NonTarget', raw_details = %s WHERE id = %s;", (f"{raw_details} | Matched: {matched_keywords}", lead_id))
                        conn.commit()
                        browser.close()
                        continue

                    lead_email, lead_phone, insta_url, fb_url, linkedin_url, tiktok_url, subpage_text = extract_contacts_and_socials(page_content, base_url, page_context=page)
                    clean_text_content += subpage_text
                    used_playwright = True
                    browser.close()
            except Exception as e2:
                write_raw_log(f"    [⚠️ FALLBACK] Playwright Tor failed ({e2}). Fetching via direct Tor requests...")
                page_content = fetch_page_via_tor_fallback(base_url)

        # Fallback parsing if requests mode was used
        if not used_playwright and page_content:
            clean_text_content = clean_extracted_text(page_content)
            matched_keywords = get_blacklist_matches(clean_text_content, base_url)
            if matched_keywords:
                write_raw_log(f"    🛡️ [SHIELD] Dropped regional competitor: {base_url} (Matched terms: {matched_keywords})")
                cursor.execute("UPDATE sportswear_leads SET scan_status = 'Skipped_NonTarget', raw_details = %s WHERE id = %s;", (f"{raw_details} | Matched: {matched_keywords}", lead_id))
                conn.commit()
                continue
            
            lead_email, lead_phone, insta_url, fb_url, linkedin_url, tiktok_url, subpage_text = extract_contacts_and_socials(page_content, base_url, page_context=None)
            clean_text_content += subpage_text

        if not page_content:
            cursor.execute("UPDATE sportswear_leads SET scan_status = 'Skipped_NoContact' WHERE id = %s;", (lead_id,))
            conn.commit()
            continue

        try:
            cursor.execute("""
                UPDATE sportswear_leads 
                SET map_url = %s,
                    raw_details = %s,
                    personal_email = %s,
                    phone_number = %s,
                    instagram_url = %s,
                    facebook_url = %s,
                    linkedin_url = %s,
                    tiktok_url = %s,
                    scan_status = 'Needs_Eval'
                WHERE id = %s;
            """, (base_url, clean_text_content, lead_email, lead_phone, insta_url, fb_url, linkedin_url, tiktok_url, lead_id))
            conn.commit()
            write_raw_log(f"    ✔ Successfully Ingested target: {base_url} (Email: {lead_email})")
        except Exception as db_err:
            conn.rollback()
            write_raw_log(f"    [-] Database write error for {base_url}: {db_err}")
        
        gc.collect()

    cursor.close()
    conn.close()
    
    try:
        requests.get("http://127.0.0.1:3000/gc", timeout=5)
        write_raw_log("[♻️ Browserless] Triggered garbage collection flush on port 3000.")
    except Exception:
        pass

if __name__ == "__main__":
    execute_scraper_cycle()
