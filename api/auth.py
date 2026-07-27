from functools import wraps

from django.http import JsonResponse
from ninja.security import HttpBearer

from users.api_keys import authenticate_api_key, parse_bearer_api_key


class APIKeyAuth(HttpBearer):
    def authenticate(self, request, token):
        user = authenticate_api_key(token)
        if user is not None:
            request.user = user
        return user


def api_key_required(view):
    @wraps(view)
    def wrapped_view(request, *args, **kwargs):
        api_key = parse_bearer_api_key(request.headers.get("Authorization"))
        user = authenticate_api_key(api_key)
        if user is None:
            response = JsonResponse({"detail": "Unauthorized"}, status=401)
            response["WWW-Authenticate"] = "Bearer"
            return response

        request.user = user
        return view(request, *args, **kwargs)

    return wrapped_view
