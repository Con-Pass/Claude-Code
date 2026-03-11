import sys, os, io, base64, re
sys.path.insert(0, "/app/app")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django; django.setup()
from pdf2image import convert_from_bytes
from openai import OpenAI
api_key = os.environ.get("OPENAI_API_KEY","")
client = OpenAI(api_key=api_key)
with open("/app/media/uploads/develop_33.pdf","rb") as f: pdf_binary = f.read()
images = convert_from_bytes(pdf_binary, dpi=100, fmt="jpeg", first_page=1, last_page=2)
OCR_SYS = "You are a highly accurate OCR system specialized in semantic HTML. Use h1 for titles, p for body."
OCR_USER = "Transcribe ALL text in this document image into semantic HTML."
for i, img in enumerate(images):
    buf = io.BytesIO(); img.save(buf, format="JPEG", quality=85)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    resp = client.chat.completions.create(model="gpt-4o-mini",messages=[{"role":"system","content":OCR_SYS},{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+img_b64,"detail":"high"}},{"type":"text","text":OCR_USER}]}],max_tokens=4000,temperature=0)
    page_html = re.sub(r"```html|```","",resp.choices[0].message.content or "")
    tags = re.findall(r"<[a-zA-Z0-9]+>", page_html)
    print("=== Page %d: %d chars ===" % (i+1, len(page_html)))
    print("First tags: " + str(tags[:8]))
    print(page_html[:300])
    print()
