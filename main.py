import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI()

# 1. ตั้งค่า CORS เพื่ออนุญาตให้ Frontend (แอปของคุณ) ยิงเรียก API ได้โดยไม่ติดเรื่อง Security
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. ตั้งค่า Gemini Client (ดึงคีย์จาก $env:GEMINI_API_KEY)
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    # หากไม่ได้ตั้งค่า Environment Variable ให้ใส่คีย์ตรงๆ ในอัญประกาศด้านล่างนี้ได้ครับ
    api_key = "นำ_API_KEY_ของคุณมาวางตรงนี้"

client = genai.Client(api_key=api_key)

# 3. โครงสร้างข้อมูลที่รับมาจากหน้าแอป (Frontend)
class DiaryRequest(BaseModel):
    text: str
    tags: list[str] = []
    date: str = "Sep 16th, 2023"

# 4. API Endpoint รับข้อความไดอารี่ แล้วส่งให้ AI วิเคราะห์
@app.post("/api/reflect")
async def reflect_diary(request: DiaryRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="กรุณากรอกข้อความไดอารี่ก่อนครับ")

    # Prompt บังคับให้ AI สรุปตอบเป็น JSON สำหรับ comment1 และ comment2
    prompt = f"""
    คุณคือ AI ผู้เชี่ยวชาญด้านจิตวิทยาและการสะท้อนอารมณ์
    โปรดวิเคราะห์บันทึกประจำวันของผู้ใช้ต่อไปนี้:
    - วันที่: {request.date}
    - แท็กอารมณ์ที่เลือก: {', '.join(request.tags) if request.tags else 'ไม่มี'}
    - ข้อความไดอารี่: "{request.text}"

    จงตอบกลับเป็นรูปแบบ JSON ภาษาไทย โครงสร้างนี้เท่านั้น:
    {{
      "comment1": "การวิเคราะห์และสะท้อนอารมณ์สั้นๆ 1-2 ประโยค (Emotional Reflection)",
      "comment2": "ข้อแนะนำหรือคำปลอบโยนอย่างเห็นอกเห็นใจ 1-2 ประโยค (Empathy & Guidance)"
    }}
    """

    try:
        # เรียกใช้งาน Gemini 2.5 Flash เพื่อประมวลผล JSON
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        # แปลงผลลัพธ์เป็น JSON แล้วส่งกลับไปยังหน้าแอป
        result_json = json.loads(response.text)
        return {
            "success": True,
            "comment1": result_json.get("comment1", ""),
            "comment2": result_json.get("comment2", "")
        }

    except Exception as e:
        print(f"Error processing AI response: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}")

# 5. ส่วนสั่งรันเซิร์ฟเวอร์แบบครอบป้องกัน Bug บน Windows
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)