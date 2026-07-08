import os
import sys
import json
import time
import requests
import psycopg2

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, AI_API_URL, AI_MODEL, GLOBAL_LOG_PATH
)

def write_raw_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [AI_REASONER] {message}\n"
    print(message)
    try:
        os.makedirs(os.path.dirname(GLOBAL_LOG_PATH), exist_ok=True)
        with open(GLOBAL_LOG_PATH, "a") as f:
            f.write(log_entry)
    except Exception as e:
         print(f"[-] Failed to write to log file: {e}")

def query_qwen_evaluation(company_name, raw_details):
    """Instructs Qwen to perform structured market parsing, enforcing a highly explicit target sector list."""
    # Guard check to prevent NoneType subscript errors
    if not raw_details:
        raw_details = "No website text content available."
        
    prompt = (
        f"Perform a targeted B2B sportswear qualification check on this business profile:\n"
        f"Company Name: {company_name}\n"
        f"Website Content: {raw_details[:1500]}\n\n"
        "CRITICAL TARGET SECTOR GATE:\n"
        "You must determine if this business is actually a fit under our strict sportswear buyer criteria.\n"
        "1. EXPLICIT TARGET LIST (Approve with 50-100 Score):\n"
        "   - Brazilian Jiu-Jitsu (BJJ), Grappling, No-Gi, and wrestling academies.\n"
        "   - Mixed Martial Arts (MMA), Muay Thai, Kickboxing, Boxing, and Judo clubs.\n"
        "   - Karate, Taekwondo, Aikido, Sambo, or alternate traditional martial arts dojos.\n"
        "   - CrossFit boxes, functional fitness gyms, strength/conditioning gyms, and powerlifting facilities.\n"
        "2. EXPLICIT EXCLUSION LIST (MUST return Score of 0 instantly):\n"
        "   - News platforms (Bloomberg, CNN, Reuters), travel directories (GetYourGuide, TripAdvisor), ticket sellers (Jasumo Tickets), financial databases (EMIS), blog networks, or corporate holding firms unrelated to physical athletic training.\n"
        "   * Note: This is a global dataset. Page text may be in Japanese, Dutch, German, or French. Search for international keywords like 'Jiu-Jitsu', 'BJJ', 'MMA', 'Dojo', 'Gym', 'combat', 'grappling', 'fight', or 'coach' to determine if it is a training hall.\n\n"
        "RELEVANT ACADEMY INSTRUCTIONS (Only apply if it passes the Target Sector Gate above):\n"
        "1. Identify their Sportswear offerings.\n"
        "2. Identify the 'Apparel Gap' (what they are missing, e.g., lacks private label rashguards, lacks integrated club store).\n"
        "3. Formulate a 'Targeted Hook' - an ultra-brief, warm, conversational email introduction targeting them in standard business tone.\n"
        "4. Assign an 'AI Winning Score' from 50 to 100 based on their business fit.\n\n"
        "Respond ONLY with a valid raw JSON object. Do not include markdown backticks or explaining text. Use this exact schema structure:\n"
        "{\n"
        '  "score": <integer_0_to_100>,\n'
        '  "apparel_gap": "<brief_description_of_missing_apparel_gear>",\n'
        '  "hook": "<one_sentence_personalized_outreach_hook_referencing_them_specifically>",\n'
        '  "disciplines": "<comma_separated_sports_disciplines>"\n'
        "}"
    )
    payload = {
        "model": AI_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": { "temperature": 0.2, "num_predict": 256, "num_thread": 6 }
    }
    try:
        res = requests.post(f"{AI_API_URL}/api/generate", json=payload, timeout=90)
        if res.status_code == 200:
            parsed = json.loads(res.json().get("response", "{}").strip())
            return parsed
    except Exception as e:
        write_raw_log(f"    [-] Qwen evaluation failed for {company_name}: {e}")
    return None

def execute_evaluation_cycle():
    write_raw_log("=== INITIALIZING STATELESS AI REASONER ===")
    
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        write_raw_log(f"[-] PostgreSQL connection error: {str(e)}")
        return

    # Select leads waiting for AI qualification
    cursor.execute("""
        SELECT id, name, map_url, raw_details 
        FROM sportswear_leads 
        WHERE scan_status = 'Needs_Eval' 
        LIMIT 30;
    """)
    leads = cursor.fetchall()
    write_raw_log(f"[AI_REASONER] Sourced {len(leads)} leads for Qwen evaluation.")

    for lead_id, name, base_url, raw_details in leads:
        write_raw_log(f"    ➔ Analyzing target with Qwen: {base_url}")
        
        # Check raw_details NoneType safety before passing to evaluator
        clean_raw_details = raw_details if raw_details else ""
        eval_data = query_qwen_evaluation(name, clean_raw_details)
        
        if not eval_data or not isinstance(eval_data, dict):
            score = 65
            gap = "Generic sportswear requirements"
            hook = f"Hi {name} Team, we noticed your specialized programs and wanted to reach out regarding custom sublimation sportswear and club teamwear..."
            disciplines = "Combat Sports"
        else:
            try:
                score = int(eval_data.get("score", 65))
            except Exception:
                score = 65
            gap = eval_data.get("apparel_gap", "Pending")
            hook = eval_data.get("hook", "Hi Team...")
            disciplines = eval_data.get("disciplines", "Combat Sports")

        # Shielding filter: Drops irrelevant sites scored 0, or directory matches
        if score < 45 or any(k in name.lower() for k in ["directory", "corporation", "limited", "check"]):
            write_raw_log(f"    🛡️ [SHIELD] Dropped irrelevant target or directory: {name} (Score: {score})")
            cursor.execute("UPDATE sportswear_leads SET scan_status = 'Skipped_NonTarget' WHERE id = %s;", (lead_id,))
            conn.commit()
            continue

        try:
            cursor.execute("""
                UPDATE sportswear_leads 
                SET ai_winning_score = %s,
                    apparel_gap = %s,
                    targeted_hook = %s,
                    raw_details = %s,
                    scan_status = 'Needs_Dispatch'
                WHERE id = %s;
            """, (score, gap, hook, f"{clean_raw_details} | Disciplines: {disciplines}", lead_id))
            conn.commit()
            write_raw_log(f"    ✔ Successfully scored target: '{name}' | Score: {score}/100")
        except Exception as db_err:
            conn.rollback()
            write_raw_log(f"    [-] Database write error for {base_url}: {db_err}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    execute_evaluation_cycle()
