import functions_framework
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token
import json

# エンティティ認識のエンドポイントを設定します
ENTITY_ENDPOINT = "https://asia-northeast1-purple-conpass.cloudfunctions.net/conpass-entity-extraction-gpt"

@functions_framework.http
def hello_http(request):
    # Cloud Run/Cloud Functionsに向けたリクエスト用トークンを取得
    entity_token = id_token.fetch_id_token(Request(), ENTITY_ENDPOINT)
    headers = {"Authorization": f"Bearer {entity_token}"}

    # リクエストペイロードを作成
    payload = {
        "signed_url": "https://storage.googleapis.com/foldername/xxx",
        "contract_type": { "type": 1, "name": "contract"}
    }

    # エンティティ認識エンドポイントにリクエストを送信
    entity_response = requests.post(ENTITY_ENDPOINT, json=payload, headers=headers)

    if entity_response.status_code != 200:
        return f"Entity recognition request failed: {entity_response.text}", entity_response.status_code

    entity_result = entity_response.json()

    formatted_json = json.dumps(entity_result, ensure_ascii=False, indent=2)

    # エンコードされたJSONレスポンスを返却
    return formatted_json, 200, {'Content-Type': 'application/json; charset=utf-8'}