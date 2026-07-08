import os
import sys
import subprocess
import time
import psycopg2
import streamlit as st

# Bind environment configurations
sys.path.append("/opt/b2b-agent/scripts")
from s2f_env_config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, GLOBAL_LOG_PATH

# Set page styling
st.set_page_config(page_title="S2F ThreadHunter Command Center", page_icon="🥋", layout="wide")

# Helper function to get PostgreSQL connection
def get_db_connection():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

# Helper function to execute shell commands securely
def run_shell_command(cmd_list):
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30)
        return res.stdout, res.stderr
    except Exception as e:
        return "", str(e)

# Sidebar Navigation
st.sidebar.title("🥋 S2F ThreadHunter")
st.sidebar.markdown("---")
view = st.sidebar.radio("Navigation Menu", ["📊 Dashboard & Leads", "⚙️ Service & Script Control", "🔑 .env Config Manager", "📝 Real-time Log Viewer"])

# ─── VIEW 1: DASHBOARD & LEADS ───
if view == "📊 Dashboard & Leads":
    st.title("📊 Pipeline Operations Dashboard")
    
    # 1. Fetch system metrics
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM sportswear_leads;")
        total_leads = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Needs_Eval';")
        needs_eval = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Email_Queue' AND delivery_status = 'Not Sent';")
        email_queue = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM sportswear_leads WHERE scan_status = 'Social_Priority';")
        social_queue = cursor.fetchone()[0]
        
        # Display Metric Cards
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Leads Pool", total_leads)
        col2.metric("Pending AI Eval", needs_eval)
        col3.metric("Email Outbox Queue", email_queue)
        col4.metric("Manual Social Queue", social_queue)
        
        # 2. Display lead explorer table
        st.subheader("🔍 Active Lead Explorer")
        status_filter = st.selectbox("Filter by Pipeline Status", ["All", "Email_Queue", "Social_Priority", "Needs_Eval", "Needs_Dispatch", "Replied", "Bounced"])
        
        query = "SELECT id, name, map_url, personal_email, phone_number, ai_winning_score, apparel_gap, targeted_hook, scan_status, delivery_status FROM sportswear_leads"
        if status_filter != "All":
            query += f" WHERE scan_status = '{status_filter}'"
        query += " ORDER BY id DESC LIMIT 100;"
        
        cursor.execute(query)
        leads_data = cursor.fetchall()
        
        if leads_data:
            # Format display list
            display_list = []
            for r in leads_data:
                display_list.append({
                    "ID": r[0], "Name": r[1], "Website": r[2], "Email": r[3], "Phone": r[4],
                    "Score": r[5], "Apparel Gap": r[6], "Target Hook": r[7], "Status": r[8], "Delivery": r[9]
                })
            st.dataframe(display_list, use_container_width=True)
        else:
            st.info("No leads found matching the selected status filter.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"PostgreSQL Connection Error: {e}")

# ─── VIEW 2: SERVICE & SCRIPT CONTROL ───
elif view == "⚙️ Service & Script Control":
    st.title("⚙️ Service & Script Control Panel")
    
    # 1. Systemd Orchestrator Status Check
    st.subheader("🛰️ Background Orchestrator Daemon")
    stdout, stderr = run_shell_command(["systemctl", "is-active", "s2f-orchestrator.service"])
    status = stdout.strip()
    
    if status == "active":
        st.success("🟢 ORCHESTRATOR IS ACTIVE & RUNNING (s2f-orchestrator.service)")
    else:
        st.error(f"🔴 ORCHESTRATOR IS STOPPED (Status: {status})")
        
    col1, col2, col3 = st.columns(3)
    if col1.button("▶️ Start Orchestrator Service"):
        run_shell_command(["rm", "-f", "/tmp/s2f_orchestrator.lock"])
        run_shell_command(["systemctl", "start", "s2f-orchestrator.service"])
        st.rerun()
    if col2.button("⏸️ Stop Orchestrator Service"):
        run_shell_command(["systemctl", "stop", "s2f-orchestrator.service"])
        st.rerun()
    if col3.button("♻️ Restart Orchestrator"):
        run_shell_command(["rm", "-f", "/tmp/s2f_orchestrator.lock"])
        run_shell_command(["systemctl", "restart", "s2f-orchestrator.service"])
        st.rerun()
        
    st.markdown("---")
    
    # 2. Manual Submodule Execution Overrides
    st.subheader("⚡ Manual Script Execution Overrides")
    st.caption("Clicking these will run the script once in the background. The console output will print below.")
    
    col_s1, col_s2, col_s3 = st.columns(3)
    
    if col_s1.button("🚀 Run Outbox Campaign (bulk_sender.py)"):
        with st.spinner("Executing outbound campaign..."):
            out, err = run_shell_command(["/opt/b2b-agent/venv/bin/python3", "/opt/b2b-agent/scripts/bulk_sender.py"])
            st.text_area("Console Output", value=out if out else err)
            
    if col_s2.button("📥 Parse Inbox Replies (incoming_reply_handler.py)"):
        with st.spinner("Checking Maildir folders..."):
            out, err = run_shell_command(["/opt/b2b-agent/venv/bin/python3", "/opt/b2b-agent/scripts/incoming_reply_handler.py"])
            st.text_area("Console Output", value=out if out else err)
            
    if col_s3.button("📊 Post Summary Report (overnight_reporter.py)"):
        with st.spinner("Generating and posting daily report..."):
            out, err = run_shell_command(["/opt/b2b-agent/venv/bin/python3", "/opt/b2b-agent/scripts/overnight_reporter.py"])
            st.text_area("Console Output", value=out if out else err)

# ─── VIEW 3: .ENV CONFIG MANAGER ───
elif view == "🔑 .env Config Manager":
    st.title("🔑 .env Configuration Manager")
    st.caption("Edit and update system credentials securely from this interface.")
    
    env_path = "/opt/b2b-agent/.env"
    if not os.path.exists(env_path):
        env_path = "/opt/b2b-agent/scripts/.env"
        
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_content = f.read()
            
        st.subheader("Active Configuration Keys")
        updated_content = st.text_area("Secure .env Editor (chmod 600)", value=env_content, height=450)
        
        if st.button("💾 Save Configurations"):
            try:
                with open(env_path, "w") as f:
                    f.write(updated_content)
                st.success("✔ Configurations updated and saved successfully!")
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to write configuration file: {e}")
    else:
        st.error("Could not locate the system .env configuration file on disk.")

# ─── VIEW 4: REAL-TIME LOG VIEWER ───
elif view == "📝 Real-time Log Viewer":
    st.title("📝 Real-Time System Log Viewer")
    st.caption(f"Tailing operational logs from: {GLOBAL_LOG_PATH}")
    
    if os.path.exists(GLOBAL_LOG_PATH):
        # Read the last 150 lines of the consolidated log
        with open(GLOBAL_LOG_PATH, "r") as f:
            lines = f.readlines()
            tail_lines = lines[-150:]
            log_text = "".join(tail_lines)
            
        st.text_area("execution.log", value=log_text, height=550)
        if st.button("🔄 Refresh Logs"):
            st.rerun()
    else:
        st.info("Log file is currently empty or has not been initialized on disk yet.")
