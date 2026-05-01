from mozilla_django_oidc.auth import OIDCAuthenticationBackend


class CustomOIDCBackend(OIDCAuthenticationBackend):
    """Custom OIDC backend that maps Keycloak claims to CustomUser fields."""

    def get_userinfo(self, access_token, id_token, payload):
        """Merge realm_access from the token payload into userinfo claims.

        Keycloak includes realm_access only in the ID token, not in the
        userinfo endpoint response.  We need it for role syncing.
        """
        claims = super().get_userinfo(access_token, id_token, payload)
        if 'realm_access' not in claims and 'realm_access' in payload:
            claims['realm_access'] = payload['realm_access']
        return claims

    def create_user(self, claims):
        email = claims.get('email', '')
        user = self.UserModel.objects.create_user(
            username=claims.get('preferred_username', email),
            email=email,
            first_name=claims.get('given_name', ''),
            last_name=claims.get('family_name', ''),
        )
        self._sync_role(user, claims)
        user.save()
        return user

    def update_user(self, user, claims):
        user.first_name = claims.get('given_name', user.first_name)
        user.last_name = claims.get('family_name', user.last_name)
        user.email = claims.get('email', user.email)
        self._sync_role(user, claims)
        user.save()
        return user

    def filter_users_by_claims(self, claims):
        email = claims.get('email')
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email=email)

    def _sync_role(self, user, claims):
        realm_access = claims.get('realm_access')
        if realm_access is None:
            return
        roles = realm_access.get('roles', [])
        if 'superuser' in roles:
            user.role = user.Role.SUPERUSER
        else:
            user.role = user.Role.VERWALTER
