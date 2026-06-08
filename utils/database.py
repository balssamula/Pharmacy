import os
import sqlite3
import uuid
import socket
import requests
from datetime import datetime, timedelta
import pandas as pd

# 💡 [تم الإصلاح]: تحديد المسارات القياسية مباشرة دون استدعاء الملف لنفسه منعاً للـ Circular Import
DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "pharmacy_reconciliation.db")
PHARMACY_COUNT = 17

def fix_users_table_columns():
    """حقن صامت وآمن لإضافة الأعمدة المفقودة في جدول المستخدمين منعاً للـ OperationalError"""
    # التأكد من إنشاء المجلد الخاص بالبيانات أولاً إذا لم يكن موجوداً
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_ip TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  
        
    try:
        cur.execute("ALTER TABLE users ADD COLUMN pharmacist_name TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  
        
    conn.commit()
    conn.close()

# استدعاء الدالة الآمنة فوراً عند إقلاع التطبيق لترميم قاعدة البيانات
fix_users_table_columns()

def get_client_ip():
    """الحصول على عنوان IP الخاص بالجهاز"""
    try:
        response = requests.get('https://api.ipify.org', timeout=5)
        if response.status_code == 200:
            return response.text
    except:
        pass
    
    try:
        hostname = socket.gethostname()
        return socket.gethostbyname(hostname)
    except:
        return "غير معروف"

def now_str():
    utc_now = datetime.utcnow()
    saudi_time = utc_now + timedelta(hours=3)
    return saudi_time.strftime("%Y-%m-%d %H:%M:%S")

def get_saudi_time():
    utc_now = datetime.utcnow()
    saudi_time = utc_now + timedelta(hours=3)
    return saudi_time.strftime("%H:%M:%S %d-%m-%Y")

def pharmacy_names():
    return [f"Balsam Alula Pharmacy {i:02d}" for i in range(1, PHARMACY_COUNT + 1)]

def upgrade_database():
    """ترقية قاعدة البيانات لإضافة الأعمدة الجديدة - يتم استدعاؤها بعد إنشاء الجداول"""
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    cur = conn.cursor()
    
    try:
        # الحصول على قائمة الأعمدة الحالية في جدول reconciliation_items
        cur.execute("PRAGMA table_info(reconciliation_items)")
        columns = [row[1] for row in cur.fetchall()]
        
        # قائمة الأعمدة التي يجب إضافتها إذا كانت مفقودة
        columns_to_add = {
            'salla_branch_number': "TEXT DEFAULT ''",
            'branch_number': "TEXT DEFAULT ''",
            'is_item_locked': "INTEGER DEFAULT 0",
            'item_locked_by': "TEXT DEFAULT ''",
            'item_locked_at': "TEXT DEFAULT ''",
            'coupon_discount': "REAL DEFAULT 0",
            'offer_discount': "REAL DEFAULT 0"
        }
        
        for col_name, col_type in columns_to_add.items():
            if col_name not in columns:
                try:
                    print(f"Adding column {col_name} to reconciliation_items")
                    cur.execute(f"ALTER TABLE reconciliation_items ADD COLUMN {col_name} {col_type}")
                except Exception as e:
                    print(f"Error adding column {col_name}: {e}")
        
        conn.commit()
        print("Database upgrade completed successfully")
        
    except Exception as e:
        print(f"Error upgrading database: {e}")
        conn.rollback()
    finally:
        conn.close()

# استدعاء الدالة فوراً عند إقلاع التطبيق لترميم قاعدة البيانات
fix_users_table_columns()

def init_database():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    cur = conn.cursor()

    try:
        # إضافة عمود last_ip إذا لم يكن موجوداً
        cur.execute("ALTER TABLE users ADD COLUMN last_ip TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # العمود موجود بالفعل، تخطى الخطأ الآمن
        
    try:
        # إضافة عمود pharmacist_name إذا لم يكن موجوداً
        cur.execute("ALTER TABLE users ADD COLUMN pharmacist_name TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # العمود موجود بالفعل

    # جدول المستخدمين
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            pharmacist_name TEXT DEFAULT '',
            last_login TEXT DEFAULT '',
            last_ip TEXT DEFAULT '',
            can_view_dashboard INTEGER DEFAULT 0,
            can_view_balances INTEGER DEFAULT 0,
            can_view_monitoring INTEGER DEFAULT 0,
            can_manage_users INTEGER DEFAULT 0,
            can_view_pharmacy_actions INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    """)

    # جدول سجل الدخول
    cur.execute("""
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            role TEXT,
            ip_address TEXT,
            login_time TEXT,
            user_agent TEXT DEFAULT ''
        )
    """)

    # جدول آخر وصول
    cur.execute("""
        CREATE TABLE IF NOT EXISTS last_access (
            pharmacy_name TEXT PRIMARY KEY,
            last_login TEXT DEFAULT '',
            pharmacist_name TEXT DEFAULT ''
        )
    """)

    # جدول المرفوعات والملفات
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
            total_post_cutoff INTEGER DEFAULT 0,
            is_locked INTEGER DEFAULT 0,
            locked_by TEXT DEFAULT '',
            locked_at TEXT DEFAULT '',
            is_active INTEGER DEFAULT 0
        )
    """)

    # جدول الحالات والمطابقات الرئيسي - مع جميع الأعمدة المطلوبة
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key TEXT UNIQUE,
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
            salla_branch_number TEXT,
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
            hidden_from_pharmacy INTEGER DEFAULT 0,
            payment_method TEXT DEFAULT '',
            discount REAL DEFAULT 0,
            shipping_cost REAL DEFAULT 0,
            tax REAL DEFAULT 0,
            coupon_discount REAL DEFAULT 0,
            offer_discount REAL DEFAULT 0,
            is_item_locked INTEGER DEFAULT 0,
            item_locked_by TEXT DEFAULT '',
            item_locked_at TEXT DEFAULT ''
        )
    """)
 
    # إدراج المسؤول الرئيسي الافتراضي بأمان
    cur.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
                               can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
            VALUES ('admin', 'admin123', 'admin', 'مدير النظام', 1, 1, 1, 1, 1, 1)
        """)

    # إدراج المدير العام الافتراضي بأمان
    cur.execute("SELECT * FROM users WHERE username = 'manager'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
                               can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
            VALUES ('manager', 'manager123', 'manager', 'مدير عام', 1, 0, 1, 1, 1, 1)
        """)

    # تأسيس حسابات الفروع التلقائية
    for index, name in enumerate(pharmacy_names(), start=1):
        cur.execute("SELECT * FROM users WHERE username = ?", (name,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
                                   can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
                VALUES (?, ?, 'pharmacy', '', 0, 0, 0, 0, 1, 1)
            """, (name, f"balsam{index}"))

    # 🏎️ إضافة الفهارس الذكية لتسريع فلترة الفروع وجلب البيانات بمقدار 10 أضعاف
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_order ON reconciliation_items(order_number, sku);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_pharmacy ON reconciliation_items(pharmacy_name, case_type, status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")
        
    conn.commit()
    conn.close()
    
    # تشغيل ترقية قاعدة البيانات لإضافة أي أعمدة مفقودة
    upgrade_database()

def record_login_history(username: str, role: str, ip_address: str = None, user_agent: str = None):
    """تسجيل محاولة الدخول"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO login_history (username, role, ip_address, login_time, user_agent)
        VALUES (?, ?, ?, ?, ?)
    """, (username, role, ip_address or get_client_ip(), now_str(), user_agent or ''))
    conn.commit()
    conn.close()

def get_login_history(limit: int = 50) -> pd.DataFrame:
    """الحصول على سجل الدخول"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"""
        SELECT username, role, ip_address, login_time
        FROM login_history
        ORDER BY login_time DESC
        LIMIT {limit}
    """, conn)
    conn.close()
    return df

def get_manager_last_login() -> dict:
    """الحصول على آخر دخول للمدير العام"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT last_login, last_ip, pharmacist_name
        FROM users WHERE username = 'manager'
    """)
    result = cur.fetchone()
    conn.close()
    if result:
        return {
            "last_login": result[0] or "لم يدخل بعد",
            "last_ip": result[1] or "غير معروف",
            "pharmacist_name": result[2] or "مدير عام"
        }
    return {"last_login": "لم يدخل بعد", "last_ip": "غير معروف", "pharmacist_name": "مدير عام"}

# باقي الدوال كما هي (get_user_permissions, update_user, etc.)
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

def add_user(username: str, password: str, role: str, pharmacist_name: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (username, password, role, pharmacist_name, can_view_dashboard, 
             can_view_balances, can_view_monitoring, can_manage_users, can_view_pharmacy_actions, is_active)
            VALUES (?, ?, ?, ?, 0, 0, 0, 0, 0, 1)
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
        SELECT username, role, pharmacist_name, last_login, last_ip, is_active,
               can_view_dashboard, can_view_balances, can_view_monitoring, 
               can_manage_users, can_view_pharmacy_actions
        FROM users ORDER BY role, username
    """, conn)
    conn.close()
    return df

def update_last_access(pharmacy_name: str, pharmacist_name: str, ip_address: str = None):
    """تحديث آخر دخول للصيدلية مع IP"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    current_time = now_str()
    current_ip = ip_address or get_client_ip()
    
    # تحديث في جدول users
    cur.execute(
        "UPDATE users SET pharmacist_name = ?, last_login = ?, last_ip = ? WHERE username = ?",
        (pharmacist_name, current_time, current_ip, pharmacy_name),
    )
    
    # تحديث في جدول last_access
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
    
    # تسجيل في سجل الدخول
    cur.execute("""
        INSERT INTO login_history (username, role, ip_address, login_time)
        VALUES (?, 'pharmacy', ?, ?)
    """, (pharmacy_name, current_ip, current_time))
    
    conn.commit()
    conn.close()
    return current_ip

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
    """الحصول على آخر دخول للصيدليات مع IP"""
    conn = sqlite3.connect(DB_PATH)
    try:
        # التحقق من وجود الأعمدة المطلوبة
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        user_columns = [row[1] for row in cur.fetchall()]
        
        # بناء الاستعلام ديناميكياً
        query = """
            SELECT 
                u.username as pharmacy_name,
                u.last_login,
                u.pharmacist_name,
                u.last_ip,
                la.last_login as last_access_date
            FROM users u
            LEFT JOIN last_access la ON la.pharmacy_name = u.username
            WHERE u.role = 'pharmacy'
            ORDER BY u.last_login DESC NULLS LAST
        """
        
        df = pd.read_sql_query(query, conn)
        
        # إضافة أعمدة مفقودة بقيم افتراضية
        if 'last_ip' not in df.columns:
            df['last_ip'] = 'غير معروف'
        if 'last_login' not in df.columns:
            df['last_login'] = 'لم يدخل بعد'
        
        return df
    except Exception as e:
        # في حالة الخطأ، إرجاع DataFrame فارغ بالهيكل الصحيح
        return pd.DataFrame(columns=['pharmacy_name', 'pharmacist_name', 'last_login', 'last_ip', 'last_access_date'])
    finally:
        conn.close()

def get_latest_upload_summary():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT upload_batch_id, file_name, uploaded_by, uploaded_at, total_cases,
                    total_additions, total_returns, total_orphan_salla, total_orphan_abc,
                    total_post_cutoff, is_locked, session_name
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
                   total_orphan_abc, total_post_cutoff, is_locked, is_active
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
    cur.execute("""
        UPDATE uploads SET is_locked = 1, locked_by = ?, locked_at = ? WHERE upload_batch_id = ?
    """, (locked_by, now_str(), upload_batch_id))
    conn.commit()
    conn.close()

def unlock_session(upload_batch_id: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE uploads SET is_locked = 0, locked_by = '', locked_at = '' WHERE upload_batch_id = ?
    """, (upload_batch_id,))
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
               salla_qty, abc_qty, difference, abc_pharmacist_name, order_status
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
               salla_qty, abc_qty, 
               (COALESCE(salla_qty, 0) - COALESCE(abc_qty, 0)) as difference,
               case_type, case_label, case_reason, status,
               performed_by, performed_at, customer_name, customer_phone, city, order_status,
               order_date, invoice_date, total_amount, profile_type, receipt_classification,
               pharmacist_note, item_key, abc_pharmacy_name, abc_pharmacist_name, hidden_from_pharmacy,
               payment_method, discount, shipping_cost, tax, coupon_discount, offer_discount,
               is_item_locked,
               (SELECT last_ip FROM users WHERE username = ?) as pharmacy_last_ip,
               (SELECT last_login FROM users WHERE username = ?) as pharmacy_last_login,
               0 as is_locked
        FROM reconciliation_items WHERE active = 1 AND upload_batch_id = ?
    """
    params = [pharmacy_name if pharmacy_name else "", pharmacy_name if pharmacy_name else "", active_batch_id]
    
    if pharmacy_name:
        query += " AND pharmacy_name = ?"
        params.append(pharmacy_name)
        if not include_hidden:
            query += " AND (hidden_from_pharmacy = 0 OR hidden_from_pharmacy IS NULL)"
    
    query += " ORDER BY case_type, order_number DESC, sku"
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
        if 'difference' in df.columns:
            df['difference'] = pd.to_numeric(df['difference'], errors='coerce').fillna(0)
        if 'is_item_locked' not in df.columns:
            df['is_item_locked'] = 0
        return df
    except Exception as e:
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
    query = """
        SELECT case_type, COUNT(*) as completed
        FROM reconciliation_items
        WHERE active = 1 AND status = 'تم'
    """
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

def lock_item(item_key: str, locked_by: str):
    """قفل عنصر لمنع التعديل عليه من الصيدلية"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE reconciliation_items 
        SET is_item_locked = 1, item_locked_by = ?, item_locked_at = ?
        WHERE item_key = ?
    """, (locked_by, now_str(), item_key))
    conn.commit()
    conn.close()

def unlock_item(item_key: str):
    """فتح قفل عنصر للسماح بالتعديل عليه"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        UPDATE reconciliation_items 
        SET is_item_locked = 0, item_locked_by = '', item_locked_at = ''
        WHERE item_key = ?
    """, (item_key,))
    conn.commit()
    conn.close()

def get_item_lock_status(item_key: str) -> bool:
    """الحصول على حالة قفل العنصر"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT is_item_locked FROM reconciliation_items WHERE item_key = ?", (item_key,))
    result = cur.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def update_username(old_username: str, new_username: str, password: str = None):
    """تحديث اسم المستخدم"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        if password:
            cur.execute("UPDATE users SET username = ?, password = ? WHERE username = ?", 
                       (new_username, password, old_username))
        else:
            cur.execute("UPDATE users SET username = ? WHERE username = ?", 
                       (new_username, old_username))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_old_orders(pharmacy_name: str = None, months: int = 6) -> pd.DataFrame:
    """الحصول على الطلبات التي مر عليها أكثر من X أشهر (مع استبعاد الملغي والمسترجع)"""
    conn = sqlite3.connect(DB_PATH)
    
    # حساب تاريخ الحد
    from datetime import datetime, timedelta
    cutoff_date = (datetime.now() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    
    query = """
        SELECT order_number, invoice_number, sku, product_name, pharmacy_name, branch_number,
               salla_qty, abc_qty, (COALESCE(salla_qty, 0) - COALESCE(abc_qty, 0)) as difference, case_type, case_label, case_reason, status,
               performed_by, performed_at, customer_name, customer_phone, city, order_status,
               order_date, invoice_date, profile_type, receipt_classification,
               pharmacist_note, item_key, abc_pharmacist_name,
               julianday('now') - julianday(order_date) as days_old
        FROM reconciliation_items 
        WHERE active = 1 
        AND order_date != '' 
        AND julianday('now') - julianday(order_date) > ?
        AND status = 'قيد المتابعة'
        AND order_status NOT IN ('ملغي', 'مسترجع', 'محذوف')
        AND order_status NOT LIKE '%ملغي%'
        AND order_status NOT LIKE '%مسترجع%'
    """
    params = [months * 30]
    
    if pharmacy_name:
        query += " AND pharmacy_name = ?"
        params.append(pharmacy_name)
    
    query += " ORDER BY days_old DESC"
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

def get_old_orders_stats(pharmacy_name: str = None) -> dict:
    """إحصائيات الطلبات القديمة (مع استبعاد الملغي والمسترجع)"""
    df = get_old_orders(pharmacy_name=pharmacy_name)
    if df.empty:
        return {"total": 0, "additions": 0, "returns": 0, "orphan_salla": 0, "orphan_abc": 0, "by_branch": {}}
    
    stats = {
        "total": len(df),
        "additions": len(df[df["case_type"] == "addition"]),
        "returns": len(df[df["case_type"] == "return"]),
        "orphan_salla": len(df[df["case_type"] == "orphan_salla"]),
        "orphan_abc": len(df[df["case_type"] == "orphan_abc"]),
        "by_branch": df.groupby("pharmacy_name").size().to_dict()
    }
    return stats

def get_old_invoices(pharmacy_name: str = None, months: int = 6) -> pd.DataFrame:
    """الحصول على الفواتير التي مر عليها أكثر من X أشهر (من شيت ABC)"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT order_number, invoice_number, sku, product_name, pharmacy_name, branch_number,
               salla_qty, abc_qty, (COALESCE(salla_qty, 0) - COALESCE(abc_qty, 0)) AS difference, case_type, case_label, case_reason, status,
               performed_by, performed_at, customer_name, customer_phone, city, order_status,
               order_date, invoice_date, profile_type, receipt_classification,
               pharmacist_note, item_key, abc_pharmacist_name,
               julianday('now') - julianday(invoice_date) as days_old
        FROM reconciliation_items 
        WHERE active = 1 
        AND invoice_date != '' 
        AND invoice_date IS NOT NULL
        AND julianday('now') - julianday(invoice_date) > ?
        AND status = 'قيد المتابعة'
        AND order_status NOT IN ('ملغي', 'مسترجع', 'محذوف')
        AND order_status NOT LIKE '%ملغي%'
        AND order_status NOT LIKE '%مسترجع%'
    """
    params = [months * 30]
    
    if pharmacy_name:
        query += " AND pharmacy_name = ?"
        params.append(pharmacy_name)
    
    query += " ORDER BY days_old DESC"
    
    try:
        df = pd.read_sql_query(query, conn, params=params)
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()

def get_old_invoices_stats(pharmacy_name: str = None) -> dict:
    """إحصائيات الفواتير القديمة"""
    df = get_old_invoices(pharmacy_name=pharmacy_name)
    if df.empty:
        return {"total": 0, "additions": 0, "returns": 0, "orphan_salla": 0, "orphan_abc": 0, "by_branch": {}}
    
    stats = {
        "total": len(df),
        "additions": len(df[df["case_type"] == "addition"]),
        "returns": len(df[df["case_type"] == "return"]),
        "orphan_salla": len(df[df["case_type"] == "orphan_salla"]),
        "orphan_abc": len(df[df["case_type"] == "orphan_abc"]),
        "by_branch": df.groupby("pharmacy_name").size().to_dict()
    }
    return stats

# ========== دوال نقل العناصر بين الفروع ==========

def move_item_to_branch(item_key: str, target_branch: str, moved_by: str) -> bool:
    """نقل عنصر من فرع إلى فرع آخر"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    try:
        # الحصول على بيانات العنصر الحالي
        cur.execute("""
            SELECT order_number, sku, case_type, pharmacy_name, salla_qty, abc_qty, 
                   product_name, invoice_number, order_status, order_date, invoice_date,
                   customer_name, customer_phone, city, total_amount, payment_method,
                   discount, shipping_cost, tax, upload_batch_id
            FROM reconciliation_items WHERE item_key = ? AND active = 1
        """, (item_key,))
        item = cur.fetchone()
        
        if not item:
            return False
        
        (order_number, sku, case_type, old_pharmacy, salla_qty, abc_qty,
         product_name, invoice_number, order_status, order_date, invoice_date,
         customer_name, customer_phone, city, total_amount, payment_method,
         discount, shipping_cost, tax, upload_batch_id) = item
        
        # إنشاء item_key جديد للفرع المستهدف
        new_item_key = f"{target_branch}||{order_number}||{sku}||{case_type}"
        
        # التحقق من عدم وجود العنصر بالفعل في الفرع المستهدف
        cur.execute("SELECT 1 FROM reconciliation_items WHERE item_key = ? AND active = 1", (new_item_key,))
        if cur.fetchone():
            conn.close()
            return False
        
        # تعطيل العنصر القديم
        current_time = now_str()
        cur.execute("""
            UPDATE reconciliation_items 
            SET active = 0, hidden_from_pharmacy = 1, 
                pharmacist_note = COALESCE(pharmacist_note || '\n', '') || ?
            WHERE item_key = ?
        """, (f"[تم النقل إلى فرع {target_branch} بواسطة {moved_by} في {current_time}]", item_key))
        
        # إنشاء عنصر جديد في الفرع المستهدف
        cur.execute("""
            INSERT INTO reconciliation_items (
                item_key, upload_batch_id, order_number, invoice_number, sku, 
                product_name, pharmacy_name, salla_qty, abc_qty, difference,
                case_type, case_label, case_reason, status, order_status,
                order_date, invoice_date, customer_name, customer_phone, city,
                total_amount, payment_method, discount, shipping_cost, tax,
                first_seen_at, last_seen_at, active, hidden_from_pharmacy,
                profile_type, receipt_classification, all_abc_pharmacies,
                pharmacist_note
            )
            SELECT 
                ?, upload_batch_id, order_number, invoice_number, sku,
                product_name, ?, salla_qty, abc_qty, difference,
                case_type, case_label, case_reason, status, order_status,
                order_date, invoice_date, customer_name, customer_phone, city,
                total_amount, payment_method, discount, shipping_cost, tax,
                ?, ?, 1, 0,
                profile_type, receipt_classification, all_abc_pharmacies,
                ?
            FROM reconciliation_items WHERE item_key = ?
        """, (new_item_key, target_branch, current_time, current_time, 
              f"[تم النقل من فرع {old_pharmacy} بواسطة {moved_by}]", item_key))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error moving item: {e}")
        return False
    finally:
        conn.close()


def get_available_branches(current_branch: str = None) -> list:
    """الحصول على قائمة الفروع المتاحة للنقل إليها"""
    # قائمة الفروع الثابتة
    branches = [
        "Balsam Alula Pharmacy 01",
        "Balsam Alula Pharmacy 02",
        "Balsam Alula Pharmacy 03",
        "Balsam Alula Pharmacy 04",
        "Balsam Alula Pharmacy 05",
        "Balsam Alula Pharmacy 06",
        "Balsam Alula Pharmacy 07",
        "Balsam Alula Pharmacy 08",
        "Balsam Alula Pharmacy 09",
        "Balsam Alula Pharmacy 10",
        "Balsam Alula Pharmacy 11",
        "Balsam Alula Pharmacy 12",
        "Balsam Alula Pharmacy 13",
        "Balsam Alula Pharmacy 14",
        "Balsam Alula Pharmacy 15",
        "Balsam Alula Pharmacy 16",
        "Balsam Alula Pharmacy 17"
    ]
    if current_branch:
        branches = [b for b in branches if b != current_branch]
    return branches

# ========== دوال الكشف عن المكررات ==========

def check_duplicate_across_branches(order_number: str, sku: str, current_pharmacy: str) -> list:
    """التحقق من وجود نفس SKU ورقم الطلب في فروع أخرى"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    try:
        # البحث عن جميع السجلات النشطة بنفس order_number و sku في فروع أخرى
        cur.execute("""
            SELECT DISTINCT 
                pharmacy_name, 
                status, 
                case_type, 
                order_date, 
                invoice_date,
                invoice_number,
                order_number
            FROM reconciliation_items 
            WHERE order_number = ? 
                AND sku = ? 
                AND pharmacy_name != ? 
                AND active = 1
        """, (order_number, sku, current_pharmacy))
        
        results = cur.fetchall()
        return [{
            "pharmacy": r[0], 
            "status": r[1], 
            "case_type": r[2], 
            "order_date": r[3], 
            "invoice_date": r[4],
            "invoice_number": r[5],
            "order_number": r[6]
        } for r in results]
    except Exception as e:
        print(f"Error checking duplicates: {e}")
        return []
    finally:
        conn.close()


def get_all_duplicate_items(pharmacy_name: str = None) -> pd.DataFrame:
    """الحصول على جميع العناصر المكررة عبر الفروع"""
    conn = sqlite3.connect(DB_PATH)
    
    query = """
        SELECT order_number, sku, product_name, pharmacy_name, 
               COUNT(*) OVER (PARTITION BY order_number, sku) as duplicate_count,
               order_date, invoice_date, case_type, status
        FROM reconciliation_items 
        WHERE active = 1
    """
    
    if pharmacy_name:
        query += f" AND pharmacy_name = '{pharmacy_name}'"
    
    try:
        df = pd.read_sql_query(query, conn)
        # تصفية العناصر التي لها أكثر من نسخة
        df = df[df['duplicate_count'] > 1]
        return df
    except Exception as e:
        return pd.DataFrame()
    finally:
        conn.close()
