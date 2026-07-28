"""OAuth endpoints and client settings observed from Nova Poshta Business Cabinet."""

OAUTH_ISSUER = "https://auth.novaposhta.ua:9001/"
OAUTH_AUTHORIZATION_ENDPOINT = "https://auth.novaposhta.ua:9001/oauth2/auth"
OAUTH_TOKEN_ENDPOINT = "https://auth.novaposhta.ua:9001/oauth2/token"
OAUTH_REVOCATION_ENDPOINT = "https://auth.novaposhta.ua:9001/oauth2/revoke"

OAUTH_CLIENT_ID = "c536b3fded75739b00bd8e2903b51aaa.auth.apps.novaposhta.ua"
OAUTH_CLIENT_SECRET = "745c52f6-ca73-11ea-97a1-0025b501a07b"
OAUTH_REDIRECT_URI = "https://new.novaposhta.ua/auth-processing"
OAUTH_SCOPE = "openid offline force-consent"
OAUTH_AUDIENCE = "https://id.novaposhta.ua https://api.novaposhta.ua"
OAUTH_DEFAULT_LANGUAGE = "uk"

# Refresh access token this many seconds before expires_at.
OAUTH_REFRESH_SKEW_SECONDS = 300
