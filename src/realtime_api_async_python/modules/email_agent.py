
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

class ContactSearchResult(BaseModel):
    name: str = Field(description="Full name of the contact")
    email: EmailStr = Field(description="Email address of the contact")
    
async def lookup_contact(name: str) -> List[ContactSearchResult]:
    """Look up contacts by name using Gmail API"""
    client = await create_gmail_client(await get_fresh_credentials())
    
    headers = {
        "Authorization": f"Bearer {client.credentials.token}",
        "Accept": "application/json",
    }
    
    # Use people API to search contacts
    people_url = "https://people.googleapis.com/v1/people:searchContacts"
    params = {
        "query": name,
        "readMask": "names,emailAddresses",
        "sources": ["READ_SOURCE_TYPE_CONTACT"]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(people_url, headers=headers, params=params) as response:
            result = await response.json()
            
            contacts = []
            if "results" in result:
                for person in result["results"]:
                    person_data = person.get("person", {})
                    names = person_data.get("names", [])
                    emails = person_data.get("emailAddresses", [])
                    
                    if names and emails:
                        contacts.append(ContactSearchResult(
                            name=names[0].get("displayName", ""),
                            email=emails[0].get("value", "")
                        ))
            
            return contacts

async def find_contact(prompt: str) -> dict:
    """Find a contact by name in Google Contacts"""
    try:
        contacts = await lookup_contact(prompt)
        return {
            "status": "success",
            "contacts": [contact.model_dump() for contact in contacts],
            "message": f"Found {len(contacts)} contacts matching '{prompt}'"
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Failed to look up contact: {str(e)}"
        }


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
    scopes = ['https://www.googleapis.com/auth/gmail.modify',
              'https://www.googleapis.com/auth/contacts.readonly']
    client_secrets_path: Path = Path(".client_secret.json")
    token_path: Path = Path(".gmail_token.json")
    
    creds = None
    # Check if we have saved token
    if token_path.exists():
        with open(token_path, 'r') as token_file:
            token_data = json.load(token_file)
            creds = Credentials.from_authorized_user_info(token_data, scopes)
    
    # If no valid creds available, let user login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), 
                scopes
            )
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for next run
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())
    
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

async def send_email_to_recipient(prompt: Annotated[str, {"description": "User instruction or prompt for sending the email"}], content:EmailContent) -> EmailSendResult:
    """ Sends an email to the recipient using the Gmail API"""
    return (await email_send_agent.run(prompt, deps=EmailContent(**content))).data.model_dump()
        

