from ninja.security import HttpBearer

from users.api_keys import authenticate_api_key


class APIKeyAuth(HttpBearer):
    def authenticate(self, request, token):
        user = authenticate_api_key(token)
        if user is not None:
            request.user = user
        return user
