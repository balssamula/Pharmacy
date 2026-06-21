from fastapi import FastAPI, Request
import json

app = FastAPI()

@app.post("/webhook")
async def salla_webhook(request: Request):
    # استقبال البيانات القادمة من سلة
    payload = await request.json()
    
    # التحقق من أن الحدث هو منح الصلاحية
    if payload.get("event") == "app.store.authorize":
        access_token = payload["data"]["access_token"]
        merchant_id = payload["merchant"]
        
        # حفظ المفتاح فوراً لاستخدامه في تطبيق العروض الخاص بك
        token_data = {
            "merchant": merchant_id,
            "access_token": access_token
        }
        
        with open("salla_tokens.json", "w") as f:
            json.dump(token_data, f)
            
        print("✨ تم استقبال وحفظ مفتاح الوصول بنجاح!")
        
    return {"success": True}
