import json
import os
from functools import wraps
from urllib.request import urlopen

from flask import request, jsonify, _request_ctx_stack, session, redirect, url_for
from jose import jwt
from six.moves.urllib.parse import urlencode

# Auth0 Configuration
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "")
AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET", "")
AUTH0_CALLBACK_URL = os.environ.get("AUTH0_CALLBACK_URL", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", "")
AUTH0_API_AUDIENCE = AUTH0_AUDIENCE
ALGORITHMS = ["RS256"]

# Error handler
class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code

# Format error response and append status code
def get_token_auth_header():
    """Obtains the Access Token from the Authorization Header or from session"""
    auth = request.headers.get("Authorization", None)
    
    # First try to get token from Authorization header
    if auth:
        parts = auth.split()

        if parts[0].lower() != "bearer":
            raise AuthError({"code": "invalid_header",
                            "description": "Authorization header must start with Bearer"}, 401)
        elif len(parts) == 1:
            raise AuthError({"code": "invalid_header",
                            "description": "Token not found"}, 401)
        elif len(parts) > 2:
            raise AuthError({"code": "invalid_header",
                            "description": "Authorization header must be Bearer token"}, 401)

        token = parts[1]
        return token
    
    # If no Authorization header, try to get token from session
    if 'access_token' in session:
        return session['access_token']
    
    # If token is not found in either place
    raise AuthError({"code": "authorization_header_missing",
                     "description": "Authorization header is expected or user must be logged in"}, 401)

def check_permissions(permission, payload):
    if 'permissions' not in payload:
        raise AuthError({
            'code': 'invalid_claims',
            'description': 'Permissions not included in JWT.'
        }, 400)

    if permission not in payload['permissions']:
        raise AuthError({
            'code': 'unauthorized',
            'description': 'Permission not found.'
        }, 403)
    return True

def verify_decode_jwt(token):
    jsonurl = urlopen(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
    jwks = json.loads(jsonurl.read())
    unverified_header = jwt.get_unverified_header(token)
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=AUTH0_API_AUDIENCE,
                issuer=f"https://{AUTH0_DOMAIN}/"
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthError({"code": "token_expired",
                            "description": "token is expired"}, 401)
        except jwt.JWTClaimsError:
            raise AuthError({"code": "invalid_claims",
                            "description":
                                "incorrect claims, please check the audience and issuer"}, 401)
        except Exception:
            raise AuthError({"code": "invalid_header",
                            "description":
                                "Unable to parse authentication token."}, 401)

        _request_ctx_stack.top.current_user = payload
        return f(*args, **kwargs)
    raise AuthError({"code": "invalid_header",
                    "description": "Unable to find appropriate key"}, 401)

def requires_auth(f):
    """Determines if the Access Token is valid"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            token = get_token_auth_header()
            payload = verify_decode_jwt(token)
            _request_ctx_stack.top.current_user = payload
            return f(*args, **kwargs)
        except AuthError as e:
            return jsonify(e.error), e.status_code
    return decorated

def requires_permission(permission=''):
    def requires_permission_decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = get_token_auth_header()
            payload = verify_decode_jwt(token)
            check_permissions(permission, payload)
            return f(*args, **kwargs)
        return decorated
    return requires_permission_decorator 