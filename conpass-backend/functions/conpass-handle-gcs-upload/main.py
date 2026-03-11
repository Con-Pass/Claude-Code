import functions_framework
import os
import json
import requests

# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def hundle_gcs_upload(cloud_event):
    data = cloud_event.data

    event_id = cloud_event["id"]
    event_type = cloud_event["type"]
    bucket = data["bucket"]
    name = data["name"]
    size = data['size']
    timeCreated = data["timeCreated"]
    updated = data["updated"]

    print(f"Event ID: {event_id}")
    print(f"Event type: {event_type}")
    print(f"Bucket: {bucket}")
    print(f"File: {name}")
    print(f"size: {size}")
    print(f"Created: {timeCreated}")
    print(f"Updated: {updated}")

    # アップロードファイルのパスチェック
    file_dir = os.path.dirname(name)
    if file_dir != os.environ['PDF_UPLOAD_DIR'] and file_dir != os.environ['ZIP_UPLOAD_DIR']:
        print(f"excluded file: {name}")
        return

    # ログイン
    print("----------login start----------")
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
    }
    params = {
        'login_name': os.environ['LOGIN_NAME'],
        'password': os.environ['LOGIN_PASSWORD']
    }
    url = f"{os.environ['API_SERVER_URL']}/api/auth/login"
    token = None
    try:
        dumpRequest(url, 'POST', headers, params)
        r = requests.post(url=url, data=json.dumps(params), headers=headers)
        dumpResponse(r.status_code, r.text)
        rj = json.loads(r.text)
        token = rj['token']
    except Exception as e:
        print(f"login api error: {e}")
        return
    print("----------login end----------")
    
    # アップロード通知API
    print("----------start notify upload----------")
    headers = {
        'Content-Type': 'application/json; charset=UTF-8',
        'Authorization': f"JWT {token}"
    }
    file_name = os.path.basename(name)
    ext = file_name.rsplit('.', 1)[1]
    file_path = '' if ext.lower() == 'zip' else name
    zip_path = name if ext.lower() == 'zip' else ''
    params = {
        'id': file_name.rsplit('.', 1)[0],
        'filePath': file_path,
        'zipPath': zip_path,
        'size': size
    }
    url = f"{os.environ['API_SERVER_URL']}/api/notify/uploaded-to-gcs"
    try:
        dumpRequest(url, 'POST', headers, params)
        r = requests.post(url=url, data=json.dumps(params), headers=headers)
        dumpResponse(r.status_code, r.text)
    except Exception as e:
        print(f"login api error: {e}")
        return
    print("----------end notify upload----------")
    
    print('finish notify upload!!')


def dumpRequest(url, method, headers, params):
    str_list = []
    str_list.append("\n----------------request start-------------\n")
    str_list.append(f"{method} {url}\n")
    if headers is not None:
        for key, val in headers.items():
            str_list.append(f"{key}: {val}\n")
    str_list.append("\n")
    str_list.append(json.dumps(params))
    str_list.append("\n----------------request finish------------\n")

    log_str = "".join(str_list)
    print(log_str)

def dumpResponse(status_code, res_body):
    str_list = []
    str_list.append("\n----------------response start-------------\n")
    str_list.append(f"Status Code: {status_code}\n\n")
    str_list.append("\n")
    str_list.append(res_body)
    str_list.append("\n----------------response finish------------\n")

    log_str = "".join(str_list)
    print(log_str)
    