
from pydantic_ai import Agent
from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel
from pydantic import EmailStr, BaseModel, model_validator, Field, AnyHttpUrl
from pydantic_ai import Agent, RunContext 
from pydantic_ai.result import RunResult

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import datetime as dt
import base64
import aiohttp 
from google.oauth2.credentials import Credentials
from pathlib import Path
import json
from async_lru import alru_cache

class GmailCredentials(BaseModel):
    token: str = Field(description="Current access token")
    token_uri: AnyHttpUrl = Field(description="Token endpoint",  default=AnyHttpUrl("https://oauth2.googleapis.com/token"))
    expiry: dt = Field(description="Token expiry timestamp")

class GmailClient(BaseModel):
    credentials: GmailCredentials = Field(description="Gmail API credentials")
    base_url: AnyHttpUrl = Field(description="Base URL for Gmail API endpoints",default=AnyHttpUrl("https://gmail.googleapis.com/gmail/v1/users/me"))

class EmailSearchFilters(BaseModel):
    subject: Optional[str] = Field(default=None,description="Subject line to search for in emails")
    recipient_reference: Optional[str] = Field(default=None,description="Reference ID or string to search in recipient field")
    recipient_email: Optional[EmailStr] = Field(default=None,description="Email address of the recipient to search for")

class EmailContent(BaseModel):
    recipient_email: EmailStr = Field(description="Email address of the recipient")
    subject: str = Field(description="Subject line of the email")
    body: str = Field(description="Main content/body of the email")

class SearchEmailResult(BaseModel):
    date_received: dt = Field(description="Timestamp when the email was received")
    sender_email: EmailStr = Field(description="Email address of the sender")
    subject: str = Field(description="Subject line of the email")
    body: str = Field(description="Main content/body of the email")
    
class EmailSendDependencies(BaseModel):
    credentials: GmailCredentials = Field(description="Gmail API credentials")
    email: EmailContent = Field(description="Email content to send")
    
class EmailSearchResults(BaseModel):
    results: list[SearchEmailResult] = Field(description="List of email search results",default=[]) 
    
class EmailSendResult(BaseModel):
    email_sent: bool = Field(description="Flag indicating if the email was successfully sent", default=False)


async def create_gmail_client(creds: GmailCredentials) -> GmailClient:
    print(f"\n\n\n {["*"]*10}\n Create Gmail client")
    if creds.expiry <= dt.now():
        # Implement refresh logic
        pass
    
    return GmailClient(
        credentials=creds,
        base_url=AnyHttpUrl("https://gmail.googleapis.com/gmail/v1/users/me")
    )


email_send_agent: Agent[EmailContent, EmailSendResult] = Agent(  
    'openai:gpt-4o',  
    deps_type=EmailContent,
    result_type=EmailSendResult,  
    system_prompt=(  
        'You are an email sending agent. Validate the email content '
        'and send it using the Gmail API.'
    ),
)


@alru_cache(maxsize=32)
async def get_fresh_credentials() -> GmailCredentials:
    """Get fresh credentials using client secrets JSON. Will open browser first time."""
    print(f"\n\n\n {["*"]*10}\n Getting fresh credentials")
    scopes = ['https://www.googleapis.com/auth/gmail.modify']
    client_secrets_path: Path = Path(".client_secret.json")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_path), 
        scopes
    )
    creds = flow.run_local_server(port=0)
    
    return GmailCredentials(
        token=creds.token,
        expiry=creds.expiry
    )

@email_send_agent.tool  
async def send_email(
    ctx: RunContext[EmailContent], 
) -> EmailSendResult:
    """sends an email using the Gmail API"""  
 
    client = await create_gmail_client(await get_fresh_credentials())
    content = ctx.deps

    headers = {
        "Authorization": f"Bearer {client.credentials.token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    message_data = {
        "raw": base64.urlsafe_b64encode(
            f"To: {content.recipient_email}\n"
            f"Subject: {content.subject}\n\n"
            f"{content.body}"
            .encode()
        ).decode()
    }
    message_data = {
        "raw": base64.urlsafe_b64encode(
            f"To: greg.nwosu@gmail.com\n"
            f"Subject: {content.subject}\n\n"
            f"{content.body}"
            .encode()
        ).decode()
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
        f"{client.base_url}/messages/send",
        headers=headers,
        json=message_data) as response:
            result = await response.json()
            print(f"\n\n\n {["*"]*10}\n Email send result: {result}")
            return EmailSendResult(email_sent=True)

from typing import Annotated
from pydantic.functional_validators import BeforeValidator

async def send_email_to_recipient(prompt:str, content:dict) -> bool:
    """ Sends an email to the recipient using the Gmail API"""
    return (await email_send_agent.run(prompt, deps=EmailContent(**content))).data.email_sent
        
def get_send_email_descriptor():
    return { "type": "function",
    "name": "send_email_to_recipient",
    "description": "Sends an email to the recipient using the Gmail API. And Returns a boolean flag indicating if the email was successfully sent",
    "parameters": {
        "type": "object",
        "properties": {
        "prompt": {
            "type": "string",
            "description": "User instruction or prompt for sending the email"
        },
        "content": {
            "type": "object",
            "properties": {
            "recipient_email": {
                "type": "string",
                "description": "Email address of the recipient"
            },
            "subject": {
                "type": "string",
                "description": "Subject line of the email"
            },
            "body": {
                "type": "string",
                "description": "Main content/body of the email"
            }
            },
            "required": ["recipient_email", "subject", "body"]
        }
        },
        "required": ["prompt", "content"]
    }
    }
    
