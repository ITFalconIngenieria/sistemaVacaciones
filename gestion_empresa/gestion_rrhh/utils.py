import requests
from msal import ConfidentialClientApplication
from django.conf import settings

class MicrosoftGraphEmail:
    def __init__(self):
        self.client_id = settings.CLIENT_ID
        self.client_secret = settings.CLIENT_SECRET
        self.tenant_id = settings.TENANT_ID
        self.email_from = settings.EMAIL_FROM
        self.base_url = "https://graph.microsoft.com/v1.0"

        self.app = ConfidentialClientApplication(
            self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.client_secret,
        )

    def get_access_token(self):
        """Obtain an access token from Azure AD"""
        result = self.app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in result:
            return result["access_token"]
        else:
            raise Exception("Could not obtain access token")

    def send_email(self, subject, content, to_recipients, cc_recipients=None, bcc_recipients=None):
        """Send an email using Microsoft Graph API"""
        access_token = self.get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        email_payload = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML",
                    "content": content,
                },
                "toRecipients": [{"emailAddress": {"address": email}} for email in to_recipients],
                "ccRecipients": [{"emailAddress": {"address": email}} for email in cc_recipients] if cc_recipients else [],
                "bccRecipients": [{"emailAddress": {"address": email}} for email in bcc_recipients] if bcc_recipients else [],
            },
        }

        response = requests.post(
            f"{self.base_url}/users/{self.email_from}/sendMail",
            headers=headers,
            json=email_payload,
        )

        if response.status_code == 202:
            return True
        else:
            raise Exception(f"Failed to send email: {response.status_code}, {response.text}")
