import json
import os
from datetime import datetime
import requests
from flask import Flask, request

app = Flask(__name__)

# ==========================================
# 🔐 بيانات تطبيقك من منصة شركاء سلة
# ==========================================
CLIENT_ID = "92c8725e-8d39-4516-bb00-3908fe5339b3"
CLIENT_SECRET = "e84d33ca4ecd7399a1a76292bae92bdd97a438d4c48caf935fa17a8f18ef1ad2"
REDIRECT_URI = "https://accounts.salla.sa/callback/277610741" # يجب أن يطابق الرابط في بوابة سلة تماماً

DB_FILE = "stores.json"

def save_to_db(store_data):
    """دالة لحفظ بيانات المتجر في ملف JSON"""
    stores = []
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            try:
                stores = json.load(f)
            except:
                pass
                
    # التحديث إذا كان المتجر موجوداً، أو إضافته كمتجر جديد
    updated = False
    for i, store in enumerate(stores):
        if store["merchant_id"] == store_data["merchant_id"]:
            stores[i] = store_data
            updated = True
            break
            
    if not updated:
        stores.append(store_data)
        
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(stores, f, ensure_ascii=False, indent=4)

@app.route('/callback')
def salla_callback():
    """هذا هو الرابط الذي ستوجه سلة التاجر إليه بعد التثبيت"""
    code = request.args.get('code')
    if not code:
        return "❌ خطأ: لم يتم استلام كود الربط من سلة.", 400

    # 1. طلب التوكن من سلة باستخدام الكود
    token_url = "https://accounts.salla.sa/oauth2/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    
    response = requests.post(token_url, data=payload)
    if response.status_code != 200:
        return f"❌ فشل في استخراج التوكن: {response.text}", 400
        
    token_data = response.json()
    access_token = token_data.get("access_token")
    
    # 2. جلب معلومات المتجر لكي نعرض اسمه في لوحة التحكم
    headers = {"Authorization": f"Bearer {access_token}"}
    info_res = requests.get("https://api.salla.dev/admin/v2/store/info", headers=headers)
    
    store_name = "متجر غير معروف"
    merchant_id = "غير متوفر"
    
    if info_res.status_code == 200:
        info_data = info_res.json().get("data", {})
        store_name = info_data.get("name", "متجر غير معروف")
        merchant_id = str(info_data.get("id", "غير متوفر"))
        
    # 3. تجهيز البيانات وحفظها في stores.json
    now_str = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    new_store = {
        "merchant_id": merchant_id,
        "store_name": store_name,
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "installed_at": now_str
    }
    
    save_to_db(new_store)
    
    # 4. رسالة تظهر للتاجر بعد نجاح العملية
    return f"""
    <div style='text-align: center; margin-top: 50px; font-family: Tahoma, sans-serif;'>
        <h1 style='color: green;'>✅ تمت عملية الربط بنجاح!</h1>
        <h3>أهلاً بك يا {store_name}</h3>
        <p>تم تفعيل المنظومة لمتجرك. يمكنك إغلاق هذه الصفحة الآن.</p>
    </div>
    """

if __name__ == '__main__':
    # تشغيل السيرفر على البورت 5000
    app.run(host='0.0.0.0', port=5000)
