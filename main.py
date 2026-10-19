import os
import json
import httpx
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GOOGLE_SHEET_URL = "https://script.google.com/macros/s/AKfycbxVDpsLm1fe0owpOLunLHziJHMQdRLF89EV7BcsRXU1gOmr8IoARmN5SU_m_QU1ChBQ/exec"

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    api_key = "นำ_API_KEY_ของคุณมาวางตรงนี้"

client = genai.Client(api_key=api_key)

class DiaryRequest(BaseModel):
    text: str = ""
    tags: Optional[List[str]] = []
    date: Optional[str] = None


# 💡 ฟังก์ชันทำงานเบื้องหลังสำหรับส่งลง Google Sheets โดยไม่ขัดจังหวะผู้ใช้
async def send_to_sheets_in_background(text: str, tags: list, reflection: str, date: str):
    try:
        async with httpx.AsyncClient() as http_client:
            await http_client.post(GOOGLE_SHEET_URL, json={
                "text": text,
                "tags": tags,
                "reflection": reflection,
                "date": date
            })
    except Exception as e:
        print(f"Failed to save to Google Sheets: {e}")


@app.post("/api/reflect")
async def reflect_diary(request: DiaryRequest, background_tasks: BackgroundTasks):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="กรุณากรอกข้อความไดอารี่ก่อนครับ")

    prompt = f"""
    คุณคือ AI ผู้เชี่ยวชาญด้านจิตวิทยาและการสะท้อนอารมณ์
    โปรดวิเคราะห์บันทึกประจำวันของผู้ใช้ต่อไปนี้:
    - วันที่: {request.date if request.date else 'ไม่ระบุ'}
    - แท็กอารมณ์ที่เลือก: {', '.join(request.tags) if request.tags else 'ไม่มี'}
    - ข้อความไดอารี่: "{request.text}"

    จงตอบกลับเป็นรูปแบบ JSON ภาษาไทย โครงสร้างนี้เท่านั้น:
    {{
      "comment1": "การวิเคราะห์และสะท้อนอารมณ์สั้นๆ 1-2 ประโยค (Emotional Reflection)",
      "comment2": "ข้อแนะนำหรือคำปลอบโยนอย่างเห็นอกเห็นใจ 1-2 ประโยค (Empathy & Guidance)"
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        result_json = json.loads(response.text)
        comment1 = result_json.get("comment1", "")
        comment2 = result_json.get("comment2", "")
        full_reflection = f"Comment 1: {comment1}\nComment 2: {comment2}"

        # ⚡ สั่งให้เซฟลง Google Sheets แบบ Background Task (หน้าเว็บไม่ต้องรอ)
        background_tasks.add_task(
            send_to_sheets_in_background, 
            request.text, 
            request.tags, 
            full_reflection, 
            request.date
        )

        # ส่งคำตอบกลับไปหน้าเว็บทันที
        return {
            "success": True,
            "comment1": comment1,
            "comment2": comment2,
            "reflection": full_reflection
        }

    except Exception as e:
        print(f"Error processing AI response: {e}")
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)
