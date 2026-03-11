import base64
import json
import os
import tempfile
import requests
from google.cloud import storage
import fitz
# import openai
from openai import OpenAI

# Set your OpenAI API key
client = OpenAI(api_key=os.getenv("api_key"))

# Initialize Google Cloud Storage client
storage_client = storage.Client()


def get_prompt_by_type(contract_type):
    prompt_file_map = {
        1: 'prompt1.txt',
        2: 'prompt2.txt',
        3: 'prompt3.txt',
        4: 'prompt4.txt',
        5: 'prompt5.txt',
        6: 'prompt6.txt',
        7: 'prompt7.txt',
        8: 'prompt8.txt',
        9: 'prompt9.txt',
        10: 'prompt10.txt',
        11: 'prompt11.txt',
        12: 'prompt12.txt',
        13: 'prompt13.txt',
        14: 'prompt14.txt',
        15: 'prompt15.txt',
        16: 'prompt16.txt',
        17: 'prompt17.txt',
        18: 'prompt18.txt',
    }
    print(f"contract type: {contract_type}")

    prompt_file = prompt_file_map.get(contract_type)
    if prompt_file:
        with open(prompt_file, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        raise ValueError("Invalid ocr_type provided.")


def pdf_to_images(pdf_path):
    doc = fitz.open(pdf_path)
    base64_images = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for i in range(len(doc)):
            page = doc.load_page(i)
            zoom_x = 3.0
            zoom_y = 3.0
            mat = fitz.Matrix(zoom_x, zoom_y)
            pix = page.get_pixmap(matrix=mat)
            image_path = os.path.join(temp_dir, f"page_{i + 1}.png")
            pix.save(image_path)
            with open(image_path, "rb") as image_file:
                # 画像を読み込み、Base64エンコードし、最初の10文字をリストに追加
                base64_images.append(base64.b64encode(image_file.read()).decode('utf-8'))

    return base64_images


def download_pdf_via_signed_url(signed_url):
    """Downloads a PDF file from GCS using a signed URL and returns its local path."""
    response = requests.get(signed_url)
    if response.status_code == 200:
        _, temp_pdf_path = tempfile.mkstemp(suffix=".pdf")
        with open(temp_pdf_path, 'wb') as f:
            f.write(response.content)
        return temp_pdf_path
    else:
        raise Exception(f"Failed to download PDF, status code: {response.status_code}")


def process_pdf(request):
    try:
        data = request.get_json()
        signed_url = data["signed_url"]
        contract_type = data["contract_type"]
        contract_body = data["contract_body"]  # 契約書本文（VisionAPIで抽出したテキストを指定する）

        prompt = get_prompt_by_type(contract_type)

        # Download PDF using the signed URL
        # pdf_path = download_pdf_via_signed_url(signed_url)

        # Convert PDF to images
        # base64_images = pdf_to_images(pdf_path)

        messages = [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Contract:",
                    },
                    {
                        "type": "text",
                        "text": contract_body,
                    },
                ]
            },
        ]

        # for base64_image in base64_images:
        #     messages[1]["content"].append({
        #         "type": "image_url",
        #         "image_url": {
        #             "url": f"data:image/jpeg;base64,{base64_image}"
        #         }
        #     })

        response = client.chat.completions.create(
            model="gpt-4.1-mini-2025-04-14",
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=4095,
            temperature=0,
        )

        content = response.choices[0].message.content

        # エスケープされたJSON文字列をPythonの辞書に変換
        json_data = json.loads(content)
        print(json_data)

        # 再びJSON形式としてエンコード（エスケープなし）
        formatted_json_string = json.dumps(json_data, ensure_ascii=False)

        # 改行文字を削除
        formatted_json_string = formatted_json_string.replace('\n', ' ')
        return formatted_json_string, 200

    except Exception as e:
        print(f"Error in process_pdf: {str(e)}")
        return json.dumps({"error": str(e)}), 500
