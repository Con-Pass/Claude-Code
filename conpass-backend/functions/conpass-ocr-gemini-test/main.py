import functions_framework
import requests
from google.auth.transport.requests import Request
from google.oauth2 import id_token
import json

# エンティティ認識のエンドポイントを設定します
GEMINI_ENDPOINT = "https://asia-northeast1-purple-conpass.cloudfunctions.net/conpass-ocr-gemini"

@functions_framework.http
def hello_http(request):
    # Cloud Run/Cloud Functionsに向けたリクエスト用トークンを取得
    gemini_token = id_token.fetch_id_token(Request(), GEMINI_ENDPOINT)
    headers = {"Authorization": f"Bearer {gemini_token}"}

    # リクエストペイロードを作成
    payload = {
        "signed_url": "https://storage.googleapis.com/conpass-filedata-staging/gv_test/0002_1.pdf?x-goog-signature=530b4fc439204481eb3235a74d44e5aab7666af9d32d44d698cb941041c83829a32bc9bf144748237a9a9e706f65fa4fd78ba2554cd6d6aa69188cd1706e87b8c96a2c601227680a073af6c4870539e3393f21a7cedd64fd4dfca4871b87e1aca601e38c341bf3a532015d64ceddc5696886f8127ca0509f2acfe82e1e9d9e941c3c608bb8f127df8350df7b518e07c169f23e52745add04549e83949172b4ac21ef3a78b3417f78515fe2d42d3807dd0759acbade9d0bfa22ec36fcdfed0c18ecda6c0fdb386390c4e7880ea3b4d3b0e899504b996a66eb7d0b132fd1d4f9c377c89daccba4866691ed46bdef8fe996f513e95e7c86dc8dcf4296fb5246378a&x-goog-algorithm=GOOG4-RSA-SHA256&x-goog-credential=conpass-production%40purple-conpass.iam.gserviceaccount.com%2F20240913%2Fasia-northeast1%2Fstorage%2Fgoog4_request&x-goog-date=20240913T080447Z&x-goog-expires=604800&x-goog-signedheaders=host",
        "ocr_type": "html"
    }

    # エンティティ認識エンドポイントにリクエストを送信
    gemini_response = requests.post(GEMINI_ENDPOINT, json=payload, headers=headers)
    gemini_result = gemini_response.json()
    print(gemini_response.status_code)
    print(gemini_result)

    gemini_result['status_code'] = gemini_response.status_code
    
    if gemini_response.status_code == 200:
        return json.dumps(gemini_result, ensure_ascii=False, indent=2), 200
    
    elif gemini_response.status_code == 500:
        return json.dumps(gemini_result, ensure_ascii=False, indent=2), 500
    
    else: 
        return json.dumps(gemini_result, ensure_ascii=False, indent=2), gemini_response.status_code

    # # if gemini_response.status_code != 200:
    # #     return json.dumps(gemini_result), 500

    # gemini_result = gemini_response.json()
    # formatted_json = json.dumps(gemini_result, ensure_ascii=False, indent=2)

    # # エンコードされたJSONレスポンスを返却
    # return json.dumps(gemini_result, ensure_ascii=False), 200