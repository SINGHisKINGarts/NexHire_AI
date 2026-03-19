from fastapi import FastAPI, UploadFile
import pdfplumber
import ollama

app = FastAPI()

def extract_text(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

@app.post("/analyze")
async def analyze(file: UploadFile):
    with open("temp.pdf", "wb") as f:
        f.write(await file.read())

    text = extract_text("temp.pdf")

    response = ollama.chat(
        model='phi',
        messages=[
            {"role": "user", "content": f"""
            Analyze this resume:
            - strengths
            - weaknesses
            - improvements
            
            Resume:
            {text}
            """}
        ]
    )

    return {"result": response['message']['content']}