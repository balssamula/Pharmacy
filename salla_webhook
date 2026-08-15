from flask import Flask, request, jsonify
import pymysql

app = Flask(__name__)

# إعدادات الاتصال بقاعدة البيانات الخاصة بك
DB_HOST = "offersapp.duckdns.org"
DB_USER = "root"
DB_PASSWORD = "@Balsam1990"
DB_NAME = "salla_db"

@app.route('/salla-webhook', methods=['POST'])
def salla_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "No data received"}), 400

    # التقاط التوكن عند تفعيل التطبيق (النمط السهل)
    if data.get('event') == 'app.store.authorize':
        payload = data.get('data', {})
        merchant_id = str(data.get('merchant', ''))
        access_token = payload.get('access_token')
        store_name = payload.get('store_name', f"متجر {merchant_id}")

        if access_token and merchant_id:
            try:
                connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
                with connection.cursor() as cursor:
                    # إضافة المتجر أو تحديث الـ Access Token إذا كان المتجر موجوداً مسبقاً
                    sql = """
                    INSERT INTO stores (merchant_id, store_name, access_token, updated_at) 
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP) 
                    ON DUPLICATE KEY UPDATE 
                    access_token = VALUES(access_token), updated_at = CURRENT_TIMESTAMP
                    """
                    cursor.execute(sql, (merchant_id, store_name, access_token))
                connection.commit()
                connection.close()
                print(f"✅ تم حفظ Token المتجر: {merchant_id} في قاعدة البيانات salla_db")
                return jsonify({"status": "success"}), 200
            except Exception as e:
                print(f"Database Error: {e}")
                return jsonify({"error": "Database error"}), 500

    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    # البورت 5000 مفتوح لديك في Oracle Cloud حسب صورتك
    app.run(host='0.0.0.0', port=5000)
