import os
import sys
import time
import random
import subprocess
import requests
import json
import psycopg2

# Bind path to scripts environment directory
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, AI_API_URL, AI_MODEL,
    SCRIPT_WEB_HUNTER, SCRIPT_AI_REASONER, SCRIPT_DISCORD_DISPATCH, SCRIPT_MAPS_HARVESTER, GLOBAL_LOG_PATH
)

LOCK_FILE_PATH = "/tmp/s2f_orchestrator.lock"
STALL_TIMEOUT_SECONDS = 14400  # 4-hour stall timeout check

def write_raw_log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [ORCHESTRATOR] {message}\n"
    print(message)
    try:
        os.makedirs(os.path.dirname(GLOBAL_LOG_PATH), exist_ok=True)
        with open(GLOBAL_LOG_PATH, "a") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[-] Failed to write to log file: {e}")

def acquire_lock_or_exit():
    my_pid = os.getpid()
    if os.path.exists(LOCK_FILE_PATH):
        try:
            with open(LOCK_FILE_PATH, "r") as f:
                old_pid = int(f.read().strip())
            lock_age = time.time() - os.path.getmtime(LOCK_FILE_PATH)
            if lock_age > STALL_TIMEOUT_SECONDS:
                write_raw_log(f"[🛡️ LOCK] Stalled process detected (PID {old_pid}, Age: {int(lock_age/3600)}h). Forcing termination.")
                try:
                    os.kill(old_pid, 9)
                except OSError:
                    pass
                os.remove(LOCK_FILE_PATH)
            else:
                os.kill(old_pid, 0)
                write_raw_log(f"[🛡️ LOCK] Orchestrator already running under PID {old_pid}. Exiting.")
                sys.exit(0)
        except (ProcessLookupError, ValueError, OSError):
            write_raw_log("[🛡️ LOCK] Reclaiming orphaned lock file from dead process.")
            if os.path.exists(LOCK_FILE_PATH):
                try: os.remove(LOCK_FILE_PATH)
                except Exception: pass
    try:
        with open(LOCK_FILE_PATH, "w") as f:
            f.write(str(my_pid))
    except Exception as e:
        write_raw_log(f"[-] Failed to write lock file: {e}")

def release_lock():
    if os.path.exists(LOCK_FILE_PATH):
        try:
            os.remove(LOCK_FILE_PATH)
            write_raw_log("[🛡️ LOCK] Lock file cleanly released.")
        except Exception as e:
            write_raw_log(f"[-] Failed to release lock file: {e}")

def query_sourcing_matrix_and_brainstorm():
    """
    Connects to database, retrieves the next Pending region/product line, 
    and returns a structured list of hyper-localized queries.
    Gracefully falls back to generic brainstorming if the matrix queue is empty.
    """
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
    except Exception as e:
        write_raw_log(f"[-] Database connection failure inside orchestrator: {e}")
        return [], None

    # 1. Pull the next pending target from our Sourcing Matrix
    cursor.execute("""
        SELECT id, city, country, target_product_line 
        FROM sourcing_matrix 
        WHERE scan_status = 'Pending' 
        ORDER BY id ASC 
        LIMIT 1;
    """)
    target = cursor.fetchone()

    if not target:
        # Fallback Mode: If the matrix queue is completed, fall back to autonomous wide brainstorming
        write_raw_log("[ℹ] No pending sourcing matrix targets. Entering autonomous wide-area footprint brainstorming...")
        prompt = (
            "Generate a JSON array of 5 distinct, highly targeted local search queries to find "
            "combat sports, wrestling, or BJJ academies in specific sub-districts, neighborhoods, or suburbs within major global cities.\n\n"
            "GEOLOCATION BOUNDING-BOX RULES:\n"
            "1. Choose a major metropolitan target area in Europe, the Americas, Africa, Russia, or the USA.\n"
            "2. Break down that city into 5 specific local sub-districts, neighborhoods, postal areas, or suburbs.\n"
            "3. Generate highly localized queries matching this exact structure: '[Business Niche] in [Sub-District], [City]'.\n"
            "   Examples: 'wrestling in Salford, Manchester', 'bjj gym in Brooklyn, New York'.\n"
            "4. EXCLUSION RULE: Do NOT generate queries for locations in Sri Lanka, Bangladesh, China, or Japan.\n\n"
            "Respond ONLY with a valid raw JSON array of strings. Do not include markdown backticks or explaining text."
        )
        matrix_id = None
    else:
        matrix_id, city, country, product_line = target
        write_raw_log(f"[+] Loaded Sourcing Matrix Target Row ID: #{matrix_id} | Region: {city}, {country} | Apparel Line: {product_line}")
        prompt = (
            f"Generate a JSON array of 5 distinct, highly targeted local search queries specifically "
            f"designed to find prospective buyers for our apparel manufacturing line: '{product_line}' "
            f"inside the metropolitan area of {city}.\n\n"
            f"GEOGRAPHIC DISCOVERY RULES:\n"
            f"1. Identify 5 specific suburbs, local neighborhoods, postal codes, or sub-districts within the metropolitan area of {city}.\n"
            f"2. Formulate a search query for each district targeting training centers, fitness halls, martial arts dojos, or athletic clubs that represent a direct market fit for '{product_line}'.\n"
            f"3. Format each query simply as: '[Niche Keyword] in [Sub-District], {city}'.\n\n"
            f"Respond ONLY with a valid raw JSON array of 5 strings. Do not include markdown backticks, explanations, or code indicators."
        )

    payload = {
        "model": AI_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": { "temperature": 0.4, "num_predict": 256, "num_thread": 6 }
    }

    extracted_queries = []
    try:
        res = requests.post(f"{AI_API_URL}/api/generate", json=payload, timeout=120)
        if res.status_code == 200:
            raw_response = res.json().get("response", "").strip()
            parsed_queries = json.loads(raw_response)
            
            if isinstance(parsed_queries, list):
                extracted_queries = [str(q).strip() for q in parsed_queries if q]
            elif isinstance(parsed_queries, dict):
                list_key_found = False
                for k, v in parsed_queries.items():
                    if isinstance(v, list):
                        extracted_queries = [str(q).strip() for q in v if q]
                        list_key_found = True
                        break
                
                # Fallback: Extract keys/values while filtering out generic placeholders
                if not list_key_found:
                    for k, v in parsed_queries.items():
                        k_clean = str(k).strip()
                        v_clean = str(v).strip()
                        
                        # Filter out system placeholder patterns (like 'query1', 'result_1', etc.)
                        if k_clean and not any(x in k_clean.lower() for x in ["query", "result", "search", "keyword", "list"]):
                            if len(k_clean) > 3:
                                extracted_queries.append(k_clean)
                        if v_clean and not any(x in v_clean.lower() for x in ["query", "result", "search", "keyword", "list"]):
                            if len(v_clean) > 3:
                                extracted_queries.append(v_clean)
                                
            extracted_queries = list(set(extracted_queries))[:8]
    except Exception as e:
        write_raw_log(f"    [-] Sourcing evaluation failed: {e}")

    cursor.close()
    conn.close()
    
    # If API fails or returns empty, default to safe static fallback targets
    if not extracted_queries:
        extracted_queries = ["wrestling in Salford, Manchester", "bjj gym in Namba, Osaka", "grappling in Brooklyn, New York"]
        
    return extracted_queries, matrix_id

def execute_submodule(script_path, args=None):
    """Executes a pipeline module inside the virtual environment cleanly."""
    cmd = ["/opt/b2b-agent/venv/bin/python3", script_path]
    if args:
        cmd.extend(args)
    write_raw_log(f"[▶] Launching module: {os.path.basename(script_path)}")
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800  # Hard 30-minute execution cap per module
        )
        if res.stdout:
            for line in res.stdout.splitlines():
                if line.strip():
                    write_raw_log(f"  {line}")
        if res.stderr:
            write_raw_log(f"  ⚠️ [stderr]: {res.stderr}")
    except subprocess.TimeoutExpired:
        write_raw_log(f"  ❌ [TIMEOUT] Module {os.path.basename(script_path)} exceeded runtime cap. Terminated.")
    except Exception as e:
        write_raw_log(f"  ❌ [ERROR] Failed to run {os.path.basename(script_path)}: {e}")

def update_sourcing_matrix_status(matrix_id, status_str):
    """Updates the status of a specific row inside the sourcing_matrix table."""
    if not matrix_id:
        return
    try:
        conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
        cursor.execute("UPDATE sourcing_matrix SET scan_status = %s WHERE id = %s;", (status_str, matrix_id))
        conn.commit()
        write_raw_log(f"    ✔ Sourcing Matrix Row ID #{matrix_id} updated to scan_status = '{status_str}'")
        cursor.close()
        conn.close()
    except Exception as e:
        write_raw_log(f"    [-] Failed to update Sourcing Matrix state: {e}")

def main():
    acquire_lock_or_exit()
    
    write_raw_log("====================================================================")
    write_raw_log("[+] S2F DECOUPLED MICROSERVICES ORCHESTRATOR INITIALIZED SUCCESSFULLY")
    write_raw_log("====================================================================")

    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            write_raw_log(f"\n========== STARTING PIPELINE CYCLE #{cycle_count} ==========")
            
            # Step 1: Brainstorm target keywords using dynamic Sourcing Matrix
            write_raw_log("[🧠 AI] Selecting next geographical targets from matrix...")
            queries, active_matrix_id = query_sourcing_matrix_and_brainstorm()
            write_raw_log(f"[🧠 AI] Targets finalized. Sourcing queries: {queries}")
            
            # Step 2: Run Standalone Google Maps Harvester autonomously for each generated query
            for q in queries:
                execute_submodule(SCRIPT_MAPS_HARVESTER, [q])
                time.sleep(random.randint(30, 45))  # Anti-bot pacing delay between Maps searches
            
            # Step 3: Commit matrix state progress
            if active_matrix_id:
                update_sourcing_matrix_status(active_matrix_id, 'Completed')

            # Step 4: Run Ingestion Crawler (Saves HTML, extracts raw emails/phones)
            execute_submodule(SCRIPT_WEB_HUNTER)
            
            # Step 5: Run AI Evaluator (Performs Qwen scoring & classification)
            execute_submodule(SCRIPT_AI_REASONER)
            
            # Step 6: Run Telemetry Gateway (Handles Discord routing & OSINT bio scans)
            execute_submodule(SCRIPT_DISCORD_DISPATCH)
            
            # Step 7: Flush Browserless VRAM Cache
            try:
                requests.get("http://127.0.0.1:3000/gc", timeout=5)
                write_raw_log("[♻️ Browserless] Triggered garbage collection flush on port 3000.")
            except Exception:
                pass

            # Step 8: Randomized Human Pacing Rest
            sleep_delay = random.randint(300, 600)
            write_raw_log(f"[💤] Cycle #{cycle_count} complete. Outbox and Discord queues synced.")
            write_raw_log(f"[💤] Sleeping for {sleep_delay} seconds (approx {int(sleep_delay/60)}m)...")
            time.sleep(sleep_delay)

    except KeyboardInterrupt:
        write_raw_log("\n[⚠️ SYSTEM] Manual cancellation detected. Shutting down.")
    finally:
        release_lock()

if __name__ == "__main__":
    main()
