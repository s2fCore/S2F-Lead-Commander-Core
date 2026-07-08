import os
import sys
import psycopg2

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def run_database_cleanup():
    print("====================================================================")
    print("[+] INITIALIZING S2F DATABASE MAINTENANCE & ALIGNMENT PROCESS")
    print("====================================================================")

    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[-] PostgreSQL connection error: {e}")
        return

    # 1. Purge Excluded & Competitor Regions (TLDs & Keyword matches)
    try:
        print("[+] 1. Purging competitor and manufacturer domains (JP, CN, BD, LK)...")
        cursor.execute("""
            DELETE FROM sportswear_leads 
            WHERE map_url ~* '\\.(jp|cn|bd|lk)(\\/|$)'
               OR map_url ~* '(sialkot|pakistan|made-in-china|alibaba|sri\\s*lanka|bangladesh|china|japan|colombo|dhaka|tokyo|beijing|shanghai)';
        """)
        rows_deleted_geo = cursor.rowcount
        conn.commit()
        print(f"    ✔ Successfully removed {rows_deleted_geo} competitor region domains.")
    except Exception as e_db:
        conn.rollback()
        print(f"[-] Failed to execute geo purge: {e_db}")

    # 2. Purge News, Travel Directories, & Corporate Databases
    try:
        print("[+] 2. Purging news outlets, travel guides, and corporate directories...")
        cursor.execute("""
            DELETE FROM sportswear_leads 
            WHERE map_url ~* '(bloomberg|emis\\.com|crunchbase|zoominfo|apollo\\.io|dnb\\.com|pitchbook|getyourguide|tripadvisor|yelp|yellowpages|wikipedia)';
        """)
        rows_deleted_dir = cursor.rowcount
        conn.commit()
        print(f"    ✔ Successfully removed {rows_deleted_dir} irrelevant directory/news domains.")
    except Exception as e_db:
        conn.rollback()
        print(f"[-] Failed to execute directory purge: {e_db}")

    # 3. Safe De-duplication (Keeps the oldest entry with the lowest ID)
    try:
        print("[+] 3. Running relational de-duplication sweep...")
        cursor.execute("""
            DELETE FROM sportswear_leads a
            USING sportswear_leads b
            WHERE a.id > b.id 
              AND (a.map_url = b.map_url OR a.name = b.name);
        """)
        rows_deleted_dup = cursor.rowcount
        conn.commit()
        print(f"    ✔ Successfully removed {rows_deleted_dup} duplicate database entries.")
    except Exception as e_db:
        conn.rollback()
        print(f"[-] Failed to execute de-duplication sweep: {e_db}")

    # 4. Re-analyze Table and Vacuum Clean Disk Pages
    try:
        print("[+] 4. Reclaiming disk pages and analyzing relational indexes...")
        # Vacuum cannot run inside a standard transaction block
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cursor.execute("VACUUM ANALYZE sportswear_leads;")
        print("    ✔ Vacuum complete. Database indexes rebuilt and healthy.")
    except Exception as e_db:
        print(f"[-] Failed to execute vacuum: {e_db}")

    # 5. Output Final Database Health Metrics
    try:
        cursor.execute("SELECT COUNT(*) FROM sportswear_leads;")
        total_leads = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Pending';")
        pending_leads = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Email_Queue';")
        queued_emails = cursor.fetchone()[0]
        
        print("\n====================================================================")
        print("📊 POST-ALIGNMENT DATABASE HEALTH REPORT:")
        print("====================================================================")
        print(f" • Total Ingested Leads in DB:  {total_leads}")
        print(f" • Queue Size - Pending Crawl:  {pending_leads}")
        print(f" • Queue Size - Email Outbox:   {queued_emails}")
        print("====================================================================\n")
    except Exception as e_db:
        print(f"[-] Failed to compile database metrics: {e_db}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    run_database_cleanup()
