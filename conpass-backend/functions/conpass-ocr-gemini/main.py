from google import genai
import re, json
PROJECT_ID = "purple-conpass"
REGION = 'us-west1'


client = genai.Client(
    vertexai=True, project=PROJECT_ID, location='us-west1'
)


html_ocr_system_instruction = (
    "You are a highly accurate OCR (Optical Character Recognition) system, specialized in converting "
    "documents into clean, semantic HTML. Your sole output must be HTML, "
    "without any additional text, explanations, or extraneous information.\n\n"
    "You should consider the formatting of each page. If there are multiple columns, you should output the left column first and then the right columns sequentially"
    "**Output Format Constraints:**\n"
    "- **Encoding:** UTF-8 HTML.\n"
    "- **Structure:** The HTML must always start with `<html>` and end with `</html>`.\n\n"
    "- **Preserve Formatting:** Maintain headings, paragraphs, lists, and table structures as accurately as possible based on the visual layout in the document.\n"
    "- **Allowed Block Elements ONLY:** `<html>`, `<body>`, `<h1>`, `<h2>`, `<h3>`, `<h4>`, `<h5>`, `<h6>`, `<p>`, `<ol>`, `<ul>`, `<li>`, `<table>`, `<tr>`, `<td>`.\n"
    "- **Accuracy:** Strive for perfect accuracy in text extraction, including capitalization, punctuation, and special characters.\n"
)


gemini_ocr_user_prompt = (
    "Please meticulously analyze the provided image of a document and convert all "
    "written text into valid and structured HTML, strictly adhering to the "
    "system instructions regarding element usage, two-column table formatting, "
    "and output constraints. Ensure all text is captured accurately and in the "
    "correct reading order."
)




def process_pdf(request):
    try:
        data = request.get_json()
        pdf_uri = data['pdf_uri']
        page_size= data['pdf_size']
        print(f"pdf size {page_size}")
        metadata_context= f"*** FYI- there are {page_size} pages in the provided pdf. You need to process all pages and return the final HTML. ***"
        system_instruction = html_ocr_system_instruction + metadata_context
        if not pdf_uri:
            return json.dumps({"error": "Invalid request: 'pdf_uri is required"}), 400
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                genai.types.Part.from_uri(file_uri=pdf_uri, mime_type='application/pdf'),
                genai.types.Part.from_text(text=system_instruction)
            ],
        )
        html_response = response.text
        ocr_result = html_response.replace('\n', ' ')
        sanitized_html = re.sub(r'```html|```', '', ocr_result)
        return json.dumps({"ocr_results": sanitized_html}, ensure_ascii=False), 200, {
            'Content-Type': 'application/json; charset=utf-8'}

    except Exception as e:
        print(f"Error in process_pdf: {str(e)}")
        return json.dumps({"error": str(e)}), 500
