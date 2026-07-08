import os
import sys
import time
import requests
import json
import csv
import io
import psycopg2
from datetime import datetime, timezone

# Bind path to scripts environment directory
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    DISCORD_TOKEN, CHANNEL_BETA
)

def send_custom_discord_payload_with_file(channel_id, payload, csv_content, filename):
    """Sends a native Discord embed along with the actual compiled CSV spreadsheet attached."""
    url = f"https://discord.com/api/v10/channels/{str(channel_id)}/messages"
    
    # Do NOT specify Content-Type in headers; the requests library will generate the multipart boundary automatically.
    headers = {
        "Authorization": f"Bot {str(DISCORD_TOKEN)}"
    }
    
    # Format the payload as a JSON string inside the multipart form
    data = {
        "payload_json": json.dumps(payload)
    }
    
    # Prepare the raw CSV string as an in-memory file attachment
    files = {
        "file": (filename, csv_content, "text/csv")
    }
    
    try:
        res = requests.post(url, headers=headers, data=data, files=files, timeout=30)
        return res.status_code in [200, 201]
    except Exception as e:
        print(f"[-] Discord File Upload Failure: {e}")
    return False

def compile_overnight_metrics():
    print("[+] Compiling overnight pipeline execution metrics and generating CSV export...")

    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[-] PostgreSQL connection error: {str(e)}")
        return

    # --- 1. COMPILE STATS FOR EMBED SUMMARY ---
    cursor.execute("SELECT COUNT(*) FROM sportswear_leads;")
    total_leads = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status != 'Pending';")
    total_processed = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Email_Queue' AND delivery_status = 'Not Sent';")
    email_queue_size = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Social_Priority';")
    social_priority_size = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE delivery_status = 'Sent';")
    total_sent = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Replied' OR delivery_status = 'Success/Reply';")
    total_replied = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE delivery_status = 'Bounced';")
    total_bounced = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE delivery_status = 'Invalid_MX';")
    total_invalid_mx = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Skipped_NonTarget' OR scan_status = 'Skipped_NoContact';")
    skipped_count = cursor.fetchone()[0]

    # --- 2. QUERY CLEAN, PROCESSED LEADS FOR CSV SPREADSHEET ---
    cursor.execute("""
        SELECT id, name, map_url, personal_email, phone_number, instagram_url, facebook_url, linkedin_url, tiktok_url, ai_winning_score, apparel_gap, targeted_hook, scan_status, delivery_status
        FROM sportswear_leads
        WHERE scan_status IN ('Email_Queue', 'Social_Priority', 'Needs_Dispatch', 'Replied', 'Pitched', 'Discord_Notified')
        ORDER BY id ASC;
    """)
    clean_leads = cursor.fetchall()

    cursor.close()
    conn.close()

    # --- 3. GENERATE IN-MEMORY CSV FILE ---
    csv_output = io.StringIO()
    writer = csv.writer(csv_output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Write Excel/CSV columns
    writer.writerow([
        "Lead ID", "Company Name", "Website", "Email", "Phone", 
        "Instagram Profile", "Facebook Page", "LinkedIn Profile", "TikTok Profile", 
        "AI Score", "Apparel Gap", "Outbound Target Hook", "Pipeline Status", "Delivery Status"
    ])
    
    for row in clean_leads:
        writer.writerow(row)
        
    csv_content = csv_output.getvalue()
    csv_output.close()

    # Save a local persistent copy of the CSV to the disk
    local_csv_path = "/opt/b2b-agent/mail_data/s2f_leads_daily.csv"
    try:
        with open(local_csv_path, "w", encoding="utf-8") as f:
            f.write(csv_content)
        print(f"    ✔ Local CSV spreadsheet backup saved to: {local_csv_path}")
    except Exception as e:
        print(f"[-] Failed to save local CSV: {e}")

    # --- 4. FORMAT THE DISCORD Telemetry EMBED ---
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"s2f_clean_leads_export_{date_str}.csv"
    
    report_desc = (
        f"### 📊 S2F Overnight Operations Summary: {date_str}\n\n"
        f"• **Total Relational Leads in Pool:** `{total_leads}`\n"
        f"• **Leads Processed through Ingestion:** `{total_processed}`\n"
        f"• **Active Email Outbound Queue:** `{email_queue_size}`\n"
        f"• **Active Manual Social (Alpha-1) Queue:** `{social_priority_size}`\n"
        f"• **Pruned Directories & Blacklisted Targets:** `{skipped_count}`\n\n"
        f"--- 📧 OUTBOUND CAMPAIGN METRICS ---\n"
        f"• **Emails Dispatched successfully:** `{total_sent}`\n"
        f"• **B2B Active Leads Replied (Success):** `{total_replied}` 🔥\n"
        f"• **Bounces caught (Sequence Blocked):** `{total_bounced}` 🛡️\n"
        f"• **Domains skipped (MX-Record Guard):** `{total_invalid_mx}`\n\n"
        f"📎 *The complete clean lead spreadsheet is attached below.*"
    )

    payload = {
        "embeds": [{
            "title": "📋 S2F Master Operations Report",
            "description": report_desc,
            "color": 3066993,  # Verified S2F Green
            "footer": {"text": "S2F Telemetry Gateway"}
        }]
    }

    # Transmit embed and the physical spreadsheet attachment
    success = send_custom_discord_payload_with_file(CHANNEL_BETA, payload, csv_content, filename)
    if success:
        print("[+] Overnight report and spreadsheet dispatched cleanly to CHANNEL_BETA.")
    else:
        print("[-] Failed to dispatch overnight report/attachment to Discord.")

if __name__ == "__main__":
    compile_overnight_metrics()
