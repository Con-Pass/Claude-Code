import json
import os
from openai import OpenAI
from pydantic import BaseModel

# Set your OpenAI API key
client = OpenAI(api_key = os.getenv("api_key"))

class LeaseMatch(BaseModel):
    keyword: str
    match: str       # e.g. "85%"
    matched_with: str

class Result(BaseModel):
    matches: list[LeaseMatch]

class IsNDA(BaseModel):
    is_nda: bool





system_prompt = """
You are an expert in contract management, fluent in both Japanese and English, and highly skilled in Japanese semantic analysis.

You will receive:
1. A JSON array of **Japanese or english keywords** (mostly in Kanji).
2. A **Japanese-language contract document** as plain text.

Your task:
- For each keyword, search the document for semantically similar expressions or phrases (not just exact matches).
- If the keyword is in Kanji and the contract uses the equivalent **Furigana** (Hiragana or Katakana), consider it a **100% match**.
- Consider synonym phrases, rewordings, and semantically equivalent terms in professional or legal contexts.
- Compute a **semantic similarity score (as a percentage)** between the keyword and the closest matching expression in the contract.
- Do NOT split compound keywords (e.g., 鉄道車両 must only be matched as a whole or with a semantically equivalent full phrase, not partially with 鉄道 or 車両).
- If no matching term or phrase is found with at least **80% semantic similarity**, skip the keyword.
- For each keyword, return only the **highest-scoring match**.
- You **must not fabricate the keywords** that is provided to you.
- Ignore company names entirely (any term that begins with or ends with 株式会社 should not be matched).

Return the result in the following JSON format (strictly).

[
  {
    "keyword": "<original_keyword>",
    "match": "<similarity_score>%",
    "matched_with": "<matched_term_or_phrase_from_document>"
  }
]
"""

NDA_PROMPT = """
You are a semantic text classifier for Japanese document titles.
Task: Compare the given document title to a list of NDA-related titles.

Rules:
- If the document title is semantically similar to any in the list, return: {"is_nda": true}
- Otherwise, return: {"is_nda": false}
- Output must be valid JSON only. No extra text.

List of NDA-related titles:
- 秘密保持契約書（NDA: Nondisclosure Agreement）
- 機密保持覚書
- 機密保持に関する覚書
- 守秘義務契約書
- 情報開示に関する合意書
- 機密保持に関する誓約書
"""

def openai_llm_query(messages, response_format):
    response = client.chat.completions.parse(
        model="gpt-4o-2024-08-06",
        messages=messages,
        response_format=response_format,
        max_tokens=4095,
        temperature=0
    )
    message = response.choices[0].message
    return message



def identify_nda(document_title):
    messages = [
        {"role": "system", "content": NDA_PROMPT},
        {"role": "user", "content": f"Document title: {document_title}"}
    ]
    message=openai_llm_query(messages, IsNDA)
    if (message.refusal):
        return message.refusal, None

    else:
        response = message.parsed.is_nda
        print(f"is NDA {response}")
        return None, response



def identify_lease(request):
    try:
        data= request.get_json()
        contract_body = data["contract_body"]
        keywords=data["keywords"]
        title= data["title"]
        error=''
        is_nda=False
        if title:
            error, is_nda=identify_nda(title)
        if not error and not is_nda:

            print(f"keywords- {keywords}")

            user_content = f"""
                            Keywords:
                            {json.dumps(keywords, ensure_ascii=False)}


                            Document text:
                            \"\"\"{contract_body}\"\"\"
                            """
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_content
                }
            ]
            message=openai_llm_query(messages, Result)
            print(f"message- {message}")
            if (message.refusal):
                return json.dumps({"error": str(message.refusal)}), 400
            else:
                matched_keywords=message.parsed.matches
                formatted_json_string = json.dumps([keyword.model_dump() for keyword in matched_keywords], ensure_ascii=False)
                return formatted_json_string, 200
        return json.dumps({"error": str(error)}), 400
    except Exception as e:
        print(f"Error in processing lease: {str(e)}")
        return json.dumps({"error": str(e)}), 400



