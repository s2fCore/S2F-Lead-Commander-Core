import os
import sys
import psycopg2

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def inspect_random_leads():
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[-] PostgreSQL connection error: {e}")
        return

    # Select 3 random leads that have been processed beyond the 'Pending' state
    cursor.execute("""
        SELECT id, name, map_url, personal_email, phone_number, instagram_url, facebook_url, linkedin_url, tiktok_url, ai_winning_score, apparel_gap, targeted_hook, scan_status, delivery_status
        FROM sportswear_leads
        WHERE scan_status IN ('Email_Queue', 'Social_Priority', 'Needs_Dispatch', 'Replied')
        ORDER BY RANDOM()
        LIMIT 3;
    """)
    leads = cursor.fetchall()

    if not leads:
        print("[!] No processed leads found in the database yet. Make sure the scraper and evaluator have completed at least one cycle.")
        cursor.close()
        conn.close()
        return

    print("====================================================================")
    print("🔍 RANDOM DATABASE READINGS INSPECTOR")
    print("====================================================================\n")

    for idx, lead in enumerate(leads, 1):
        lead_id, name, url, email, phone, insta, fb, linkedin, tiktok, score, gap, hook, status, delivery = lead
        
        print(f"--- 📌 RANDOM ENTRY #{idx} (Database ID: {lead_id}) ---")
        print(f" • Company Name:     {name}")
        print(f" • Target Website:   {url}")
        print(f" • Personal Email:   {email}")
        print(f" • Primary Phone:    {phone}")
        print(f" • Instagram Handle: {insta or 'Not Found'}")
        print(f" • Facebook Handle:  {fb or 'Not Found'}")
        print(f" • TikTok Handle:    {tiktok or 'Not Found'}")
        print(f" • LinkedIn Profile: {linkedin or 'Not Found'}")
        print(f" • AI Quality Score: {score}/100")
        print(f" • Apparel Gap:      {gap}")
        print(f" • Customized Hook:  \"{hook}\"")
        print(f" • Pipeline Status:  {status}")
        print(f" • Delivery Status:  {delivery}")
        print("-" * 68 + "\n")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    inspect_random_leads()
