import json
import requests
import random
import string

from logging import getLogger

logger = getLogger('__name__')


def generate_random_string(length):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for _ in range(length))


def dumpRequest(req_id, url, method, headers, params):
    str_list = []
    str_list.append(f"\n------------------request start ({req_id})-------------\n")
    str_list.append(f"{method} {url}\n")
    if headers is not None:
        for key, val in headers.items():
            str_list.append(f"{key}: {val}\n")
    str_list.append("\n")
    str_list.append(json.dumps(params))
    str_list.append(f"\n------------------request finish ({req_id})-------------\n")

    log_str = "".join(str_list)
    logger.info(log_str)


def dumpResponse(req_id, status_code, body):
    str_list = []
    str_list.append(f"\n------------------response start ({req_id})-------------\n")
    str_list.append(f"Status Code: {status_code}\n\n")
    str_list.append("\n")
    str_list.append(body)
    str_list.append(f"\n------------------response finish ({req_id})-------------\n")

    log_str = "".join(str_list)
    logger.info(log_str)


def execute_http_post(url, data):
    try:
        req_id = generate_random_string(10)
        if data:
            headers = {'Content-Type': 'application/json; charset=UTF-8'}
            dumpRequest(req_id, url, 'POST', headers, data)
            response = requests.post(url=url, headers=headers, data=json.dumps(data), timeout=900)
        else:
            dumpRequest(req_id, url, 'POST', None, None)
            response = requests.post(url=url, timeout=900)
        dumpResponse(req_id, response.status_code, response.text)
        if response.status_code < 200 or response.status_code >= 300:
            err_msg = f"Error: Received non-success status code {response.status_code}"
            logger.error(err_msg)
            raise Exception(err_msg)
    except Exception as e:
        err_msg = f"execute request error: {e}"
        logger.error(err_msg)
        raise Exception(err_msg)
