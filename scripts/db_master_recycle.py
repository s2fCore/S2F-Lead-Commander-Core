import os
import sys
import psycopg2

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def run_master_queue_recycle():
    print("====================================================================")
    print("[+] INITIALIZING MASTER S2F QUEUE RECYCLE PROCESS")
    print("====================================================================")

    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[-] PostgreSQL connection error: {e}")
        return

    # Reset all active/notified leads so they enter Qwen and Telemetry again cleanly
    try:
        cursor.execute("""
            UPDATE sportswear_leads
            SET scan_status = 'Needs_Eval',
                targeted_hook = 'Pending',
                apparel_gap = 'Unanalyzed',
                ai_winning_score = 0,
                delivery_status = 'Not Sent'
            WHERE scan_status IN ('Email_Queue', 'Social_Priority', 'Needs_Dispatch', 'Discord_Notified', 'Pitched');
        """)
        rows_recycled = cursor.rowcount
        conn.commit()
        print(f"    ✔ Successfully recycled {rows_recycled} active leads back to 'Needs_Eval'.")
    except Exception as e_db:
        conn.rollback()
        print(f"[-] Failed to execute queue recycle: {e_db}")

    cursor.close()
    conn.close()
    print("====================================================================\n")

if __name__ == "__main__":
    run_master_queue_recycle()
