from flask import Flask, request, jsonify
import json
import os
import hmac
import hashlib
import tempfile
from datetime import datetime

app = Flask(__name__)

# مسار ملف قاعدة بيانات المتاجر
STORES_FILE = 'stores.json'

@app.route('/salla-webhook', methods=['POST'])
def salla_webhook():
    # سلة تقوم بإرسال البيانات بصيغة JSON عند حدوث أي حدث
    webhook_secret = os.environ.get("SALLA_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        return jsonify({"error": "Webhook verification not configured"}), 503
    sent = request.headers.get("X-Salla-Signature", "")
    calculated = hmac.new(webhook_secret.encode("utf-8"), request.get_data(), hashlib.sha256).hexdigest()
    if not sent or not hmac.compare_digest(sent.lower(), calculated):
        return jsonify({"error": "Invalid Salla signature"}), 401
    data = request.get_json(silent=True)
    
    if not data:
        return jsonify({"error": "No data received"}), 400

    # 1. التحقق من أن الحدث هو حدث منح الصلاحيات (النمط السهل)
    if data.get('event') == 'app.store.authorize':
        payload = data.get('data', {})
        merchant_id = str(data.get('merchant', ''))
        access_token = payload.get('access_token')
        
        # إذا لم تقم سلة بإرسال اسم المتجر في هذا الحدث، نضع اسماً مؤقتاً
        store_name = payload.get('store_name', f"متجر {merchant_id}")

        if access_token and merchant_id:
            # 2. قراءة ملف المتاجر الحالي (إن وجد)
            stores = []
            if os.path.exists(STORES_FILE):
                with open(STORES_FILE, 'r', encoding='utf-8') as f:
                    try: stores = json.load(f)
                    except: stores = []

            # 3. تحديث الـ Token إذا كان المتجر موجوداً مسبقاً (عند ضغط: إعادة إرسال)
            found = False
            for store in stores:
                if str(store.get('merchant_id')) == merchant_id:
                    store['access_token'] = access_token
                    store['installed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    found = True
                    break

            # 4. أو إضافة المتجر كمتجر جديد إذا لم يكن موجوداً
            if not found:
                stores.append({
                    "merchant_id": merchant_id,
                    "store_name": store_name,
                    "access_token": access_token,
                    "installed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            # 5. حفظ البيانات الجديدة
            # Atomic replace prevents truncated JSON on interrupted writes.
            temporary = None
            try:
                fd, temporary = tempfile.mkstemp(prefix=".webhook-", suffix=".tmp", dir=os.path.dirname(os.path.abspath(STORES_FILE)))
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(stores, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(temporary, STORES_FILE)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)

            print(f"✅ تم استقبال وحفظ Token جديد للمتجر: {merchant_id}")
            return jsonify({"status": "success", "message": "Token saved"}), 200

    # الرد بالنجاح لأي أحداث أخرى حتى لا تقوم سلة بإعادة الإرسال
    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    # تشغيل السيرفر على منفذ 5000
    app.run(host='0.0.0.0', port=5000)
