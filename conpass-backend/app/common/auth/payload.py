from rest_framework_jwt.utils import jwt_payload_handler


def custom_jwt_payload_handler(user):
    """
    Custom JWT payload handler.
    This function is called whenever a token is created.
    It adds a 'scope' to the default payload.
    """
    payload = jwt_payload_handler(user)
    if user.account and  user.account.chatbot_access:
        payload['scope'] = 'write:chatbot'
    return payload
