"""Lets Swagger (/api/docs/) show the 'Authorize' button for our JWT authentication class."""

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme


class JWTWithContextScheme(SimpleJWTScheme):
    target_class = "apps.accounts.authentication.JWTAuthenticationWithContext"
    name = "jwtAuth"
