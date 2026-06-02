import re
import pandas as pd
from datetime import datetime, timedelta

# إعداد التوقيت المحلي للسعودية (UTC+3)
def now_str():
    utc_now = datetime.utcnow()
    saudi_time = utc_now + timedelta(hours=3)
    return saudi_time.strftime("%Y-%m-%d %H:%M:%S")

def get_saudi_time():
    utc_now = datetime.utcnow()
    saudi_time = utc_now + timedelta(hours=3)
    return saudi_time.strftime("%H:%M:%S %d-%m-%Y")

def get_saudi_date():
    utc_now = datetime.utcnow()
    saudi_time = utc_now + timedelta(hours=3)
    return saudi_time.strftime("%Y-%m-%d")

def normalize_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()

def normalize_city(value) -> str:
    city = normalize_text(value).upper()
    city = city.replace("-", " ").replace("_", " ")
    city = re.sub(r"\s+", " ", city)
    return city

def is_cancelled_or_returned_status(status_text: str) -> bool:
    status = normalize_text(status_text)
    return any(token in status for token in ["ملغي", "مسترجع"])

def is_pending_payment_status(status_text: str) -> bool:
    status = normalize_text(status_text)
    return "بانتظار الدفع" in status

def is_gift_or_promotion(customer_name: str) -> bool:
    name = normalize_text(customer_name)
    gift_keywords = ["هدية", "دعاية", "gift", "promotion", "free", "sample", "اختبار", "test"]
    for keyword in gift_keywords:
        if keyword in name.lower():
            return True
    return False

def cancel_status_label(status_text: str) -> str:
    status = normalize_text(status_text)
    if "مسترجع" in status:
        return "مسترجع"
    if "ملغي" in status:
        return "ملغي"
    return ""

def normalize_order_number(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    text = text.replace(".0", "")
    if text.lower() in {"nan", "none", "null"}:
        return ""
    match = re.search(r"\d+", text)
    return match.group(0) if match else text

def normalize_sku(value) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace(".0", "")
    invalid_skus = {"0", "1", "200"}
    if text in invalid_skus:
        return ""
    if re.fullmatch(r"\d+", text):
        return text
    return ""

def numeric_value(value) -> float:
    try:
        return float(pd.to_numeric(value, errors="coerce").fillna(0))
    except:
        return 0.0

def extract_branch_from_status(status_text):
    if not status_text or pd.isna(status_text):
        return ""
    match = re.search(r"فرع\s*(\d+)", str(status_text))
    if match:
        return f"{int(match.group(1)):02d}"
    return ""

def determine_branch(order_status: str, city: str) -> tuple[str, str]:
    branch_num = extract_branch_from_status(order_status)
    if branch_num:
        return f"Balsam Alula Pharmacy {branch_num}", branch_num

    normalized_city = normalize_city(city)
    delivered_statuses = ["تم التوصيل", "ملغي", "مسترجع", "محذوف"]
    if any(status in normalize_text(order_status) for status in delivered_statuses):
        if normalized_city in {"AL ULA", "ALULA", "AL-ULA"}:
            return "Balsam Alula Pharmacy 09", "09"
        return "Balsam Alula Pharmacy 13", "13"

    return "Balsam Alula Pharmacy 13", "13"

def get_branch_number(pharmacy_name: str) -> str:
    match = re.search(r"(\d{2})$", normalize_text(pharmacy_name))
    return match.group(1) if match else ""

def get_branch_location(branch_number: str) -> str:
    branch_num = int(branch_number) if branch_number.isdigit() else 0
    if branch_num in [1, 2, 3, 4, 5, 6, 7, 9]:
        return "العلا"
    elif branch_num in [8, 10, 11, 12, 13, 14, 15, 16, 17]:
        return "تبوك"
    else:
        return "غير محدد"

def status_pill(status: str) -> str:
    if status == "تم":
        return '<span class="pill pill-completed">✅ مغلق</span>'
    return '<span class="pill pill-amber">⏳ قيد المتابعة</span>'

def case_pill(case_type: str) -> str:
    CASE_LABELS = {
        "addition": "إضافة",
        "return": "إرجاع",
        "orphan_salla": "طلب بدون فاتورة",
        "orphan_abc": "فاتورة بدون طلب",
        "post_cutoff_abc": "فاتورة بعد آخر طلب",
        "branch_mismatch": "اختلاف فرع",
        "special_review": "مراجعة رقم طلب خاص",
    }
    mapping = {
        "addition": "pill-blue",
        "return": "pill-red",
        "orphan_salla": "pill-amber",
        "orphan_abc": "pill-slate",
        "post_cutoff_abc": "pill-slate",
        "branch_mismatch": "pill-red",
        "special_review": "pill-slate",
    }
    css_class = mapping.get(case_type, "pill-slate")
    return f'<span class="pill {css_class}">{CASE_LABELS.get(case_type, case_type)}</span>'

def status_alert_pill(order_status: str) -> str:
    label = cancel_status_label(order_status)
    return f'<span class="pill pill-cancel">{label}</span>' if label else ""

def payment_alert_pill(order_status: str) -> str:
    return '<span class="pill pill-payment">💰 بانتظار الدفع</span>' if is_pending_payment_status(order_status) else ""

def get_tab_label(label: str, completed: int, total: int) -> str:
    if total > 0:
        return f"{label} ({completed}/{total})"
    return label
