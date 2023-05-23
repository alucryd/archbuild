import requests
from buildbot.www.oauth2 import OAuth2Auth


class OpenIDAuth(OAuth2Auth):
    name = "OpenID"
    faIcon = "fa-openid"
    authUriAdditionalParams = {"scope": "openid"}

    def __init__(self, configurationUri, clientId, clientSecret, **kwargs):
        r = requests.get(configurationUri)
        r.raise_for_status()

        json = r.json()

        self.authUri = json["authorization_endpoint"]
        self.tokenUri = json["token_endpoint"]
        self.userInfoUri = json["userinfo_endpoint"]
        super(OpenIDAuth, self).__init__(clientId, clientSecret, **kwargs)

    def createSessionFromToken(self, token):
        s = requests.Session()
        s.headers = {"Authorization": f"Bearer {token['access_token']}"}
        return s

    def getUserInfoFromOAuthClient(self, session):
        r = session.get(self.userInfoUri)
        r.raise_for_status()

        json = r.json()

        return {
            "email": json["email"],
            "full_name": json["name"],
            "username": json["username"],
        }
