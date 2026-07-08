import os
import sys
import psycopg2

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def reset_corrupted_queues():
    print("====================================================================")
    print("[+] INITIALIZING TARGETED DATABASE QUEUE RESET")
    print("====================================================================")

    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        print(f"[-] PostgreSQL connection error: {e}")
        return

    try:
        # Reset any leads that have Swiss placeholder hooks or are missing evaluation metadata
        cursor.execute("""
            UPDATE sportswear_leads
            SET scan_status = 'Needs_Eval',
                targeted_hook = 'Pending',
                apparel_gap = 'Unanalyzed',
                ai_winning_score = 0
            WHERE targeted_hook = 'Pending'
               OR targeted_hook ~* 'Bonjour Icon'
               OR apparel_gap = 'Unanalyzed'
               OR apparel_gap ~* 'Lacks private label rashguards';
        """)
        rows_reset = cursor.rowcount
        conn.commit()
        print(f"    ✔ Successfully reset {rows_reset} corrupted or incomplete evaluations back to 'Needs_Eval'.")
    except Exception as e_db:
        conn.rollback()
        print(f"[-] Failed to execute queue reset: {e_db}")

    cursor.close()
    conn.close()
    print("====================================================================\n")

if __name__ == "__main__":
    reset_corrupted_queues()
