import os
import sys
import random
import re
import time
import requests
import json
import psycopg2
from bs4 import BeautifulSoup
import phonenumbers
from phonenumbers import PhoneNumberType

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, AI_API_URL, AI_MODEL,
    DISCORD_TOKEN, CHANNEL_ALPHA, CHANNEL_ALPHA_1, CHANNEL_BETA, GLOBAL_LOG_PATH
)

def write_raw_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [DISPATCHER] {message}\n"
    print(message)
    try:
        os.makedirs(os.path.dirname(GLOBAL_LOG_PATH), exist_ok=True)
        with open(GLOBAL_LOG_PATH, "a") as f:
            f.write(log_entry)
    except Exception as e:
         print(f"[-] Failed to write to log file: {e}")

def deduce_iso_region(email, website, address, raw_details):
    """
    Cross-checks TLDs, postal address, and website content to derive the highly accurate 
    2-letter ISO country code for self-healing phone parsing.
    """
    email_lower = email.lower() if email else ""
    web_lower = website.lower() if website else ""
    addr_lower = address.lower() if address else ""
    text_lower = raw_details.lower() if raw_details else ""
    
    # 1. Direct TLD Checks
    if email_lower.endswith(".uk") or web_lower.endswith(".uk") or ".co.uk" in web_lower:
        return "GB", "44"
    if email_lower.endswith(".ch") or web_lower.endswith(".ch") or ".ch" in web_lower:
        return "CH", "41"
    if email_lower.endswith(".nl") or web_lower.endswith(".nl") or ".nl" in web_lower:
        return "NL", "31"
    if email_lower.endswith(".de") or web_lower.endswith(".de") or ".de" in web_lower:
        return "DE", "49"
    if email_lower.endswith(".fr") or web_lower.endswith(".fr") or ".fr" in web_lower:
        return "FR", "33"
    if email_lower.endswith(".se") or web_lower.endswith(".se") or ".se" in web_lower:
        return "SE", "46"
    if email_lower.endswith(".ca") or web_lower.endswith(".ca") or ".ca" in web_lower:
        return "CA", "1"
    if email_lower.endswith(".au") or web_lower.endswith(".au") or ".com.au" in web_lower:
        return "AU", "61"
    if email_lower.endswith(".br") or web_lower.endswith(".br") or ".com.br" in web_lower:
        return "BR", "55"

    # 2. Maps Postal Address Checks
    if any(k in addr_lower for k in ["united kingdom", "great britain", "england", "scotland", "wales", "uk"]):
        return "GB", "44"
    if any(k in addr_lower for k in ["switzerland", "suisse", "schweiz", "geneva", "zurich", "ch"]):
        return "CH", "41"
    if any(k in addr_lower for k in ["netherlands", "nederland", "holland", "amsterdam", "rotterdam"]):
        return "NL", "31"
    if any(k in addr_lower for k in ["germany", "deutschland", "düsseldorf", "munich", "berlin"]):
        return "DE", "49"
    if any(k in addr_lower for k in ["sweden", "sverige", "stockholm"]):
        return "SE", "46"
    if any(k in addr_lower for k in ["canada", "toronto", "vancouver"]):
        return "CA", "1"
    if any(k in addr_lower for k in ["united states", "usa", "texas", "california", "america"]):
        return "US", "1"

    # 3. Web Page Content City/Synonym Checks
    combined_context = f"{web_lower} {text_lower}"
    if any(k in combined_context for k in ["glasgow", "nottingham", "london", "manchester", "birmingham", "leeds"]):
        return "GB", "44"
    if any(k in combined_context for k in ["zurich", "geneva", "geneve", "basel", "lausanne"]):
        return "CH", "41"
    if any(k in combined_context for k in ["amsterdam", "rotterdam", "utrecht"]):
        return "NL", "31"
    if any(k in combined_context for k in ["dusseldorf", "duesseldorf", "berlin", "munchen", "frankfurt"]):
        return "DE", "49"

    # Fallback default
    return "US", "1"

def verify_and_classify_phone(phone_str, email, website, address, raw_details):
    """
    Parses, validates, self-heals, and classifies phone carrier line types 
    using the derived ISO region to prevent "INVALID_FORMAT" errors.
    """
    if not phone_str or phone_str in ["Pending", "Not Found"]:
        return False, "UNKNOWN", "Not Found", None
    
    # Extract clean numeric string for prefix inspections
    clean_numeric = "".join(filter(str.isdigit, phone_str))
    
    # Derive region ISO and corresponding dial code
    region, dial_code = deduce_iso_region(email, website, address, raw_details)
    
    try:
        # Self-Healing Check: If the parsed number is missing an international prefix
        # (e.g. '156133804647' for UK instead of '+441561...'), we heal it by prepending the dial code
        if not phone_str.startswith("+") and not clean_numeric.startswith(dial_code):
            # Prepend dial code and clean up leading zeros
            healed_phone = f"+{dial_code}{clean_numeric.lstrip('0')}"
        elif not phone_str.startswith("+") and clean_numeric.startswith(dial_code):
            healed_phone = f"+{clean_numeric}"
        else:
            healed_phone = phone_str

        parsed_num = phonenumbers.parse(healed_phone, region)
        
        # If healed parse fails, fall back to parsing with default region directly
        if not phonenumbers.is_valid_number(parsed_num):
            parsed_num = phonenumbers.parse(phone_str, region)
            
        if not phonenumbers.is_valid_number(parsed_num):
            return False, "INVALID_FORMAT", phone_str, None
        
        num_type = phonenumbers.number_type(parsed_num)
        
        line_type = "LANDLINE"
        is_mobile = False
        
        if num_type in [PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE]:
            line_type = "MOBILE - WhatsApp Ready"
            is_mobile = True
        elif num_type == PhoneNumberType.FIXED_LINE:
            line_type = "LANDLINE - Office Call Only"
        elif num_type == PhoneNumberType.VOIP:
            line_type = "VOIP / IP PHONE"
            is_mobile = True
            
        formatted_phone = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        e164_format = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.E164)
        whatsapp_number = e164_format.replace("+", "") if is_mobile else None
        
        return True, line_type, formatted_phone, whatsapp_number
    except Exception:
        pass
    return False, "PARSING_ERROR", phone_str, None

def generate_social_dm_pitch(company_name, raw_details):
    """Uses Qwen to write a professional, highly polite B2B Instagram/WhatsApp DM pitch."""
    prompt = (
        f"Write a short, professional, highly polite B2B Instagram/WhatsApp DM pitch for our sublimation manufacturing brand (S2F Sportswear) "
        f"targeting '{company_name}'.\n"
        f"Website Context: {raw_details[:1000]}\n\n"
        "RULES:\n"
        "1. Do NOT sound like a generic sales bot. Maintain a warm, human, and professional tone.\n"
        "2. Do NOT use slang, emojis, or exclamation marks.\n"
        "3. Focus on our custom sportswear manufacturing, sublimation, and club uniform capabilities.\n"
        "4. Keep the message under 4 sentences.\n"
        "5. Invite them to reply to see custom samples, or browse our portfolio on Instagram @s2fsportswear.\n"
        "6. Respond only with the message body. Do not include placeholders, brackets, or explaining text."
    )
    payload = {
        "model": AI_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": { "temperature": 0.4, "num_predict": 180, "num_thread": 6 }
    }
    try:
        res = requests.post(f"{AI_API_URL}/api/generate", json=payload, timeout=45)
        if res.status_code == 200:
            return res.json().get("response", "").strip()
    except Exception as e:
        write_raw_log(f"    [-] Failed to generate social pitch via Qwen: {e}")
    return (
        f"Hello Team. We noticed your specialized programs over at {company_name}.\n"
        f"We are a custom sportswear manufacturer specializing in high-end sublimated fightwear and team uniforms. "
        f"If you ever need custom rashguards or apparel for the academy, we'd love to send over some sample designs. "
        f"Please reply here if you'd like to see our work, or check out our portfolio on Instagram at @s2fsportswear. Best regards."
    )

def fetch_osint_bio_safely(social_url):
    """Safely attempts to scrape a profile biography text, handling login walls gracefully."""
    if not social_url or "instagram.com" not in social_url.lower():
        return "Not Inspected (Alternate social platform or invalid handle)"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    proxies = {"http": "socks5://127.0.0.1:9050", "https": "socks5://127.0.0.1:9050"}
    try:
        res = requests.get(social_url, headers=headers, proxies=proxies, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.parser")
            meta_desc = soup.find("meta", {"name": "description"})
            if meta_desc and meta_desc.get("content"):
                return meta_desc.get("content").strip()
    except Exception:
        pass
    return "Profile Bio Restricted (Login wall / CAPTCHA challenge intercepted)"

def dispatch_discord_embed(lead_data, dm_pitch):
    """Sends a clean, copy-paste optimized Style #2 native Embed Card with locked-in S2F branding and routing."""
    lead_id, name, website, email, phone, insta, fb, linkedin, tiktok, score, apparel_gap, hook, raw_details, postal_address = lead_data
    
    # Run carrier verification, self-healing region lookup, and line classification
    is_valid_phone, line_type, formatted_phone, wa_number = verify_and_classify_phone(phone, email, website, postal_address, raw_details)
    wa_link = f"https://wa.me/{wa_number}" if wa_number else "None"
    
    bio_text = fetch_osint_bio_safely(insta)
    bio_emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', bio_text)))
    bio_email_str = ", ".join(bio_emails) if bio_emails else "None"
    
    # Enforce strict channel routing and sidebar colors
    # Alpha Channel: Both Email AND Social exist (Green)
    # Alpha-1 Channel: NO Email, but Social exists (Blue)
    # Beta Channel: All other cases (Gray)
    has_email = (email != "Not Found" and email is not None)
    has_social = bool(insta or fb or tiktok)
    
    if has_email and has_social:
        target_channel = CHANNEL_ALPHA
        title_prefix = "🟩 S2F Alpha Lead Ingested"
        sidebar_color = 3066993 # Active Email Green
        
        # Format the embed payload (EMBED CARD ONLY with Social DM copy block - Email pitch dropped as requested)
        fields = [
            {"name": "🎯 Target Company", "value": f"{name} (Serial: #{lead_id})", "inline": True},
            {"name": "🏆 Score", "value": f"{score}/100", "inline": True},
            {"name": "📞 Primary Phone", "value": f"{formatted_phone} ({line_type})", "inline": True},
            {"name": "🌐 Website", "value": f"{website}", "inline": False},
            {"name": "📸 Instagram Profile", "value": f"{insta}" if insta else "None", "inline": False},
            {"name": "🌟 Sourced Profile Bio", "value": f"\"{bio_text[:1000]}\"", "inline": False},
            {"name": "📝 Qwen Insight / Apparel Gap", "value": apparel_gap[:1000], "inline": False},
            {"name": "💬 Copy-Paste Social DM Pitch (Instagram / WhatsApp)", "value": f"```\n{dm_pitch}\n```", "inline": False},
            {"name": "🔗 WhatsApp Link", "value": wa_link, "inline": False}
        ]
        
    elif (not has_email) and has_social:
        target_channel = CHANNEL_ALPHA_1
        title_prefix = "🟦 S2F Alpha-1 Manual Social"
        sidebar_color = 3447003 # Active Social Blue
        
        # Format the embed payload (EMBED CARD ONLY with Social DM copy block - Email pitch dropped as requested)
        fields = [
            {"name": "🎯 Target Company", "value": f"{name} (Serial: #{lead_id})", "inline": True},
            {"name": "🏆 Score", "value": f"{score}/100", "inline": True},
            {"name": "📞 Primary Phone", "value": f"{formatted_phone} ({line_type})", "inline": True},
            {"name": "🌐 Website", "value": f"{website}", "inline": False},
            {"name": "📸 Instagram Profile", "value": f"{insta}" if insta else "None", "inline": False},
            {"name": "🌟 Sourced Profile Bio", "value": f"\"{bio_text[:1000]}\"", "inline": False},
            {"name": "📝 Qwen Insight / Apparel Gap", "value": apparel_gap[:1000], "inline": False},
            {"name": "💬 Copy-Paste Social DM Pitch (Instagram / WhatsApp)", "value": f"```\n{dm_pitch}\n```", "inline": False},
            {"name": "🔗 WhatsApp Link", "value": wa_link, "inline": False}
        ]
        
    else:
        target_channel = CHANNEL_BETA
        title_prefix = "⬜ S2F Lead Fallback"
        sidebar_color = 9807270 # Fallback Gray
        
        # Format the embed payload (EMBED CARD ONLY - Both Pitches Dropped as requested)
        fields = [
            {"name": "🎯 Target Company", "value": f"{name} (Serial: #{lead_id})", "inline": True},
            {"name": "🏆 Score", "value": f"{score}/100", "inline": True},
            {"name": "📞 Primary Phone", "value": f"{formatted_phone} ({line_type})", "inline": True},
            {"name": "🌐 Website", "value": f"{website}", "inline": False},
            {"name": "📸 Instagram Profile", "value": f"{insta}" if insta else "None", "inline": False},
            {"name": "🌟 Sourced Profile Bio", "value": f"\"{bio_text[:1000]}\"", "inline": False},
            {"name": "📝 Qwen Insight / Apparel Gap", "value": apparel_gap[:1000], "inline": False},
            {"name": "⚠️ Telemetry Notice", "value": "No direct digital outbox paths were extracted. Marked for landline calling or standard web search.", "inline": False}
        ]

    url = f"https://discord.com/api/v10/channels/{target_channel}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "embeds": [{
            "title": f"{title_prefix}: {name}",
            "color": sidebar_color,
            "fields": fields,
            "footer": {"text": "S2F Autonomous Hunter Engine"}
        }]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200 or res.status_code == 201:
            write_raw_log(f"    ✔ Dispatched Embed safely to Discord. Status: {name} (Serial: #{lead_id})")
            return True
        else:
            write_raw_log(f"    [-] Discord API rejected message: Status {res.status_code} | {res.text}")
    except Exception as e:
        write_raw_log(f"    [-] Failed to transmit telemetry to Discord: {e}")
    return False

def execute_dispatch_cycle():
    write_raw_log("=== INITIALIZING STATELESS TELEMETRY DISPATCHER ===")
    
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        write_raw_log(f"[-] PostgreSQL connection error: {str(e)}")
        return

    cursor.execute("""
        SELECT id, name, map_url, personal_email, phone_number, instagram_url, facebook_url, linkedin_url, tiktok_url, ai_winning_score, apparel_gap, targeted_hook, raw_details, postal_address
        FROM sportswear_leads
        WHERE scan_status = 'Needs_Dispatch'
        LIMIT 30;
    """)
    queue = cursor.fetchall()
    write_raw_log(f"[DISPATCHER] Loaded {len(queue)} target profiles for routing.")

    for lead in queue:
        lead_id = lead[0]
        name = lead[1]
        email = lead[3]
        raw_details = lead[12]
        
        # Anti-flood pacing delay to prevent Discord 429 API rate limits (4-8 seconds)
        pacing_delay = random.uniform(4.0, 8.0)
        write_raw_log(f"      [💤 Pacing] Sleeping for {pacing_delay:.1f} seconds to protect Discord API limits...")
        time.sleep(pacing_delay)

        lead_payload = lead[:14] # Capture all 14 columns including raw_details and postal_address
        dm_pitch = generate_social_dm_pitch(name, raw_details)
        success = dispatch_discord_embed(lead_payload, dm_pitch)
        
        if success:
            next_state = "Email_Queue" if email != "Not Found" else "Social_Priority"
            cursor.execute("UPDATE sportswear_leads SET scan_status = %s WHERE id = %s;", (next_state, lead_id))
            conn.commit()
            write_raw_log(f"    ✔ Processed target: '{name}' | Email: {email} (Moved to {next_state})")
        else:
            write_raw_log(f"    [-] Retaining lead ID {lead_id} in queue due to dispatch failure.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    execute_dispatch_cycle()
