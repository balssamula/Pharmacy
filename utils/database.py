import os
import sqlite3
import uuid
import pandas as pd
from datetime import datetime, timedelta

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pharmacy_reconciliation.db")
PHARMACY_COUNT = 17

def now_str():
    utc_now = datetime.utcnow()
    saudi_time = utc_now + timedelta(hours=3)
    return saudi_time.strftime("%Y-%m-%d %H:%M:%S")

def pharmacy_names():
    return [f"Balsam Alula Pharmacy {i:02d}" for i in range(1, PHARMACY_COUNT + 1)]

def init_database():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Users table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            pharmacist_name TEXT DEFAULT '',
            last_login TEXT DEFAULT '',
            can_view_dashboard INTEGER DEFAULT 0,
            can_view_balances INTEGER DEFAULT 0,
            can_view_monitoring INTEGER DEFAULT 0,
            can_manage_users INTEGER DEFAULT 0,
            can_view_pharmacy_actions INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Last access table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS last_access (
            pharmacy_name TEXT PRIMARY KEY,
            last_login TEXT DEFAULT '',
            pharmacist_name TEXT DEFAULT ''
        )
    """)

    # Uploads table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            upload_batch_id TEXT PRIMARY KEY,
            session_name TEXT DEFAULT '',
            file_name TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT,
            total_cases INTEGER DEFAULT 0,
            total_additions INTEGER DEFAULT 0,
            total_returns INTEGER DEFAULT 0,
            total_orphan_salla INTEGER DEFAULT 0,
            total_orphan_abc INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0,
            locked_by TEXT DEFAULT '',
            locked_at TEXT DEFAULT '',
            is_active INTEGER DEFAULT 0
        )
    """)

    # Reconciliation items table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_items (
            item_key TEXT PRIMARY KEY,
            upload_batch_id TEXT,
            order_number TEXT,
            invoice_number TEXT,
            sku TEXT,
            product_name TEXT,
            salla_product_name TEXT,
            abc_product_name TEXT,
            pharmacy_name TEXT,
            salla_pharmacy_name TEXT,
            abc_pharmacy_name TEXT,
            abc_pharmacist_name TEXT,
            branch_number TEXT,
            salla_qty REAL DEFAULT 0,
            abc_qty REAL DEFAULT 0,
            difference REAL DEFAULT 0,
            case_type TEXT,
            case_label TEXT,
            case_reason TEXT,
            status TEXT DEFAULT 'قيد المتابعة',
            performed_by TEXT DEFAULT '',
            performed_at TEXT DEFAULT '',
            customer_name TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            city TEXT DEFAULT '',
            order_status TEXT DEFAULT '',
            order_date TEXT DEFAULT '',
            invoice_date TEXT DEFAULT '',
            profile_type TEXT DEFAULT '',
            receipt_classification TEXT DEFAULT '',
            all_abc_pharmacies TEXT DEFAULT '',
            other_branch_details TEXT DEFAULT '',
            pharmacist_note TEXT DEFAULT '',
            total_amount REAL DEFAULT 0,
            first_seen_at TEXT,
            last_seen_at TEXT,
            active INTEGER DEFAULT 1,
            hidden_from_pharmacy INTEGER DEFAULT 0
        )
    """)

    # Insert default admin
    cur.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
             can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
            VALUES ('admin', 'admin123', 'admin', 'مدير النظام', 1, 1, 1, 1, 1, 1)
        """)

    # Insert default manager
    cur.execute("SELECT * FROM users WHERE username = 'manager'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
             can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
            VALUES ('manager', 'manager123', 'manager', 'مدير عام', 1, 1, 1, 0, 1, 1)
        """)

    # Insert default pharmacies
    for index, name in enumerate(pharmacy_names(), start=1):
        cur.execute("SELECT * FROM users WHERE username = ?", (name,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
                 can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
                VALUES (?, ?, 'pharmacy', '', 1, 0, 0, 0, 0, 1)
            """, (name, f"balsam{index}"))

    conn.commit()
    conn.close()

def get_user_permissions(username: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT role, can_view_dashboard, can_view_balances, can_view_monitoring, 
               can_manage_users, can_view_pharmacy_actions, pharmacist_name, is_active
        FROM users WHERE username = ?
    """, (username,))
    result = cur.fetchone()
    conn.close()
    if result:
        return {
            "role": result[0],
            "can_view_dashboard": bool(result[1]),
            "can_view_balances": bool(result[2]),
            "can_view_monitoring": bool(result[3]),
            "can_manage_users": bool(result[4]),
            "can_view_pharmacy_actions": bool(result[5]),
            "pharmacist_name": result[6] or "",
            "is_active": bool(result[7])
        }
    return None

def update_user_permissions(username: str, permissions: dict):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE users 
        SET can_view_dashboard = ?, can_view_balances = ?, can_view_monitoring = ?, 
            can_manage_users = ?, can_view_pharmacy_actions = ?, pharmacist_name = ?
        WHERE username = ?
    """, (
        permissions.get("can_view_dashboard", 0),
        permissions.get("can_view_balances", 0),
        permissions.get("can_view_monitoring", 0),
        permissions.get("can_manage_users", 0),
        permissions.get("can_view_pharmacy_actions", 0),
        permissions.get("pharmacist_name", ""),
        username
    ))
    conn.commit()
    conn.close()

def update_user(username: str, password: str = None, pharmacist_name: str = None, role: str = None, is_active: bool = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    updates = []
    params = []
    if password:
        updates.append("password = ?")
        params.append(password)
    if pharmacist_name:
        updates.append("pharmacist_name = ?")
        params.append(pharmacist_name)
    if role:
        updates.append("role = ?")
        params.append(role)
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)
    if updates:
        params.append(username)
        cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE username = ?", params)
    conn.commit()
    conn.close()
    return True

def add_user(username: str, password: str, role: str, pharmacist_name: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
             can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
            VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 1)
        """, (username, password, role, pharmacist_name))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_user(username: str):
    if username in ["admin", "manager"]:
        return False
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return True

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT username, role, pharmacist_name, last_login, is_active,
               can_view_dashboard, can_view_balances, can_view_monitoring, 
               can_manage_users, can_view_pharmacy_actions
        FROM users ORDER BY role, username
    """, conn)
    conn.close()
    return df

def update_last_access(pharmacy_name: str, pharmacist_name: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    current_time = now_str()
    cur.execute(
        "UPDATE users SET pharmacist_name = ?, last_login = ? WHERE username = ?",
        (pharmacist_name, current_time, pharmacy_name),
    )
    cur.execute(
        """
        INSERT INTO last_access (pharmacy_name, last_login, pharmacist_name)
        VALUES (?, ?, ?)
        ON CONFLICT(pharmacy_name) DO UPDATE SET
            last_login = excluded.last_login,
            pharmacist_name = excluded.pharmacist_name
        """,
        (pharmacy_name, current_time, pharmacist_name),
    )
    conn.commit()
    conn.close()

def fetch_user(username: str, password: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT username, role, pharmacist_name FROM users WHERE username = ? AND password = ? AND is_active = 1",
        (username, password),
    )
    user = cur.fetchone()
    conn.close()
    return user

def get_all_last_logins() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query("SELECT pharmacy_name, last_login, pharmacist_name FROM last_access ORDER BY last_login DESC", conn)
    finally:
        conn.close()

def get_latest_upload_summary():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT upload_batch_id, file_name, uploaded_by, uploaded_at, total_cases,
                   total_additions, total_returns, total_orphan_salla, total_orphan_abc,
                   is_locked, session_name
            FROM uploads WHERE is_active = 1 ORDER BY uploaded_at DESC LIMIT 1
        """)
        return cur.fetchone()
    except:
        return None
    finally:
        conn.close()

def get_all_sessions() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query("""
            SELECT upload_batch_id, session_name, file_name, uploaded_by, uploaded_at, 
                   total_cases, total_additions, total_returns, total_orphan_salla, 
                   total_orphan_abc, is_locked, is_active
            FROM uploads ORDER BY uploaded_at DESC
        """, conn)
    finally:
        conn.close()

def get_session_items(upload_batch_id: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query("""
            SELECT order_number, sku, product_name, case_label, status, performed_by, pharmacy_name
            FROM reconciliation_items WHERE upload_batch_id = ?
        """, conn, params=(upload_batch_id,))
    finally:
        conn.close()

def lock_session(upload_batch_id: str, locked_by: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE uploads SET is_locked = 1, locked_by = ?, locked_at = ? WHERE upload_batch_id = ?",
                (locked_by, now_str(), upload_batch_id))
    conn.commit()
    conn.close()

def unlock_session(upload_batch_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE uploads SET is_locked = 0, locked_by = '', locked_at = '' WHERE upload_batch_id = ?",
                (upload_batch_id,))
    conn.commit()
    conn.close()

def activate_session(upload_batch_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE uploads SET is_active = 0")
    cur.execute("UPDATE uploads SET is_active = 1 WHERE upload_batch_id = ?", (upload_batch_id,))
    conn.commit()
    conn.close()

def delete_session(upload_batch_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM uploads WHERE upload_batch_id = ?", (upload_batch_id,))
    cur.execute("DELETE FROM reconciliation_items WHERE upload_batch_id = ?", (upload_batch_id,))
    conn.commit()
    conn.close()

def get_completed_items(pharmacy_name: str = None) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT order_number, invoice_number, sku, product_name, case_type, case_label,
               performed_by, performed_at, status, item_key, pharmacy_name, branch_number,
               salla_qty, abc_qty, difference, abc_pharmacist_name
        FROM reconciliation_items WHERE active = 1 AND status = 'تم'
    """
    params = []
    if pharmacy_name:
        query += " AND pharmacy_name = ?"
        params.append(pharmacy_name)
    query += " ORDER BY performed_at DESC"
    try:
        return pd.read_sql_query(query, conn, params=params if params else None)
    finally:
        conn.close()

def fetch_active_items(pharmacy_name: str = None, include_hidden: bool = False) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT upload_batch_id FROM uploads WHERE is_active = 1 ORDER BY uploaded_at DESC LIMIT 1")
    active_session = cur.fetchone()
    if not active_session:
        conn.close()
        return pd.DataFrame()
    active_batch_id = active_session[0]
    
    query = """
        SELECT order_number, invoice_number, sku, product_name, pharmacy_name, branch_number,
               salla_qty, abc_qty, difference, case_type, case_label, case_reason, status,
               performed_by, performed_at, customer_name, customer_phone, city, order_status,
               order_date, invoice_date, total_amount, profile_type, receipt_classification,
               pharmacist_note, item_key, abc_pharmacy_name, abc_pharmacist_name, hidden_from_pharmacy,
               0 as is_locked
        FROM reconciliation_items WHERE active = 1 AND upload_batch_id = ?
    """
    params = [active_batch_id]
    if pharmacy_name:
        query += " AND pharmacy_name = ?"
        params.append(pharmacy_name)
        if not include_hidden:
            query += " AND (hidden_from_pharmacy = 0 OR hidden_from_pharmacy IS NULL)"
    query += " ORDER BY case_type, order_number DESC, sku"
    try:
        df = pd.read_sql_query(query, conn, params=params)
        if 'difference' in df.columns:
            df['difference'] = df['difference'].fillna(0)
        return df
    except:
        return pd.DataFrame()
    finally:
        conn.close()

def hide_item_from_pharmacy(item_key: str, hidden_by: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE reconciliation_items SET hidden_from_pharmacy = 1 WHERE item_key = ?", (item_key,))
    conn.commit()
    conn.close()

def unhide_item_from_pharmacy(item_key: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE reconciliation_items SET hidden_from_pharmacy = 0 WHERE item_key = ?", (item_key,))
    conn.commit()
    conn.close()

def save_case_note(order_number: str, sku: str, pharmacy_name: str, case_type: str, note: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE reconciliation_items SET pharmacist_note = ?
        WHERE active = 1 AND order_number = ? AND sku = ? AND pharmacy_name = ? AND case_type = ?
    """, (note, order_number, sku, pharmacy_name, case_type))
    conn.commit()
    conn.close()

def mark_case_done(order_number: str, sku: str, pharmacy_name: str, case_type: str, performed_by: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE reconciliation_items SET status = 'تم', performed_by = ?, performed_at = ?
        WHERE active = 1 AND order_number = ? AND sku = ? AND pharmacy_name = ? AND case_type = ?
    """, (performed_by, now_str(), order_number, sku, pharmacy_name, case_type))
    conn.commit()
    conn.close()

def reopen_case(order_number: str, sku: str, pharmacy_name: str, case_type: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE reconciliation_items SET status = 'قيد المتابعة', performed_by = '', performed_at = ''
        WHERE active = 1 AND order_number = ? AND sku = ? AND pharmacy_name = ? AND case_type = ?
    """, (order_number, sku, pharmacy_name, case_type))
    conn.commit()
    conn.close()

def reopen_case_by_item_key(item_key: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE reconciliation_items SET status = 'قيد المتابعة', performed_by = '', performed_at = '' WHERE item_key = ?", (item_key,))
    conn.commit()
    conn.close()

def get_tab_completed_counts(pharmacy_name: str = None) -> dict:
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT case_type, COUNT(*) as completed FROM reconciliation_items WHERE active = 1 AND status = 'تم'"
    params = []
    if pharmacy_name:
        query += " AND pharmacy_name = ?"
        params.append(pharmacy_name)
    query += " GROUP BY case_type"
    try:
        df = pd.read_sql_query(query, conn, params=params if params else None)
        return df.set_index('case_type')['completed'].to_dict()
    except:
        return {}
    finally:
        conn.close()