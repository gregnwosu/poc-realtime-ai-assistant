
from pydantic_ai import Agent
from dataclasses import dataclass
from typing import Optional
from pydantic import BaseModel
from pydantic import EmailStr, BaseModel, model_validator, Field, AnyHttpUrl, PhoneNumber, HttpUrl
from pydantic_ai import Agent, RunContext 
from pydantic_ai.result import RunResult
from googleapiclient.discovery import build
from typing import Optional

from google.oauth2.credentials import Credentials
import aiofiles
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
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
from pydantic_extra_types.phone_numbers import PhoneNumber


from enum import Enum
from googleapiclient.discovery import build, Resource

class ContactSearchRequest(BaseModel):
    query: str = Field(description="""   
    <validQueries>
        <query type="simpleName">
            <example>John</example>
            <description>Single name search</description>
        </query>
        
        <query type="fullName">
            <example>John Smith</example>
            <description>Full name search</description>
        </query>
        
        <query type="email">
            <example>john@example.com</example>
            <description>Email address search</description>
        </query>
        
        <query type="phone">
            <example>+1-555-123-4567</example>
            <description>Phone number search</description>
        </query>
        
        <query type="organization">
            <example>Acme Corp</example>
            <description>Organization name search</description>
        </query>
        
        <query type="wildcard" supported="unknown">
            <example>j*</example>
            <description>Wildcard search</description>
        </query>
        
        <query type="exactMatch" supported="unknown">
            <example>"John Smith"</example>
            <description>Exact match search</description>
        </query>
    </validQueries>""")

class EmailSearchFilters(BaseModel):
    subject: Optional[str] = Field(default=None,description="Subject line to search for in emails")
    recipient_reference: Optional[str] = Field(default=None,description="Reference ID or string to search in recipient field")
    recipient_email: Optional[EmailStr] = Field(default=None,description="Email address of the recipient to search for")

class EmailRequest(BaseModel):
    recipient_email: EmailStr = Field(description="Email address of the recipient")
    recipient_name: str = Field(description="name of the recipient of the email, the email address should be looked up using the contacts agent")
    subject: str = Field(description="Subject line of the email")
    body: str = Field(description="Main content/body of the email")

class SearchEmailResult(BaseModel):
    date_received: dt = Field(description="Timestamp when the email was received")
    sender_email: EmailStr = Field(description="Email address of the sender")
    subject: str = Field(description="Subject line of the email")
    body: str = Field(description="Main content/body of the email")
    
class EmailSendDependencies(BaseModel):
    credentials: Credentials = Field(description="Gmail API credentials")
    email: EmailRequest = Field(description="Email content to send")
    
class EmailSearchResults(BaseModel):
    results: list[SearchEmailResult] = Field(description="List of email search results",default=[]) 
    
class EmailSendResult(BaseModel):
    email_sent: bool = Field(description="Flag indicating if the email was successfully sent", default=False)

class ContactSearchResult(BaseModel):
    name: str = Field(description="Full name of the contact")
    email: Optional[EmailStr] = Field(description="Email address of the contact")
    phone_number: Optional[PhoneNumber] = Field(description="Phone number of the contact")
    
class ContactSearchResults(BaseModel):
    results: list[ContactSearchResult] = Field(description="List of contact search results", default=[])
    
@alru_cache(maxsize=32)
async def get_fresh_credentials() -> Credentials:
    """Get fresh credentials using client secrets JSON. Will open browser first time."""
    print(f"\n\n\n {["*"]*10}\n Getting fresh credentials")
    scopes = ['https://www.googleapis.com/auth/gmail.modify',
              'https://www.googleapis.com/auth/contacts']

    client_secrets_path: Path = Path(".client_secret.json")
    token_path: Path = Path(".gmail_token.json")
    
    creds : Optional[Credentials] = None
    # Check if we have saved token
    if token_path.exists():
        async with aiofiles.open(token_path, 'r') as token_file:
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
       
    match creds:
        case None:
             raise Exception("Failed to get credentials")
        case _:
            async with aiofiles.open(token_path, 'w') as token_file:
                token_data = {
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    }
                json.dump(token_data, token_file)
            return creds
            

class GoogleServices(str, Enum):
    contacts = ("people", "v1", "https://people.googleapis.com")
    gmail = ("gmail", "v1", "https://gmail.googleapis.com/gmail/") 
    
    def __init__(self, service_name: str, version: str, base_url: str):
        super().__init__()
        self.service_name = service_name
        self.version = version
        self.base_url = base_url
    
    def get_google_service(self, credentials: Credentials) -> Resource:
        # Build and return the service
        return build(self.service_name, self.version, credentials=credentials)
    
def extract_contact(person: dict) -> Optional[ContactSearchResult]:
    """Extracts a ContactSearchResult from a person dict if names and emails exist."""
    
    person_data = person.get("person", {})
    names = person_data.get("names", [])
    emails = person_data.get("emailAddresses", [])
    phone_numbers = person_data.get("phoneNumbers", [])
    
    if names and emails:
        return ContactSearchResult(
            name=names[0].get("displayName", ""),
            email=emails[0].get("value", ""),
            phone_number=phone_numbers[0].get("value", "") if phone_numbers else None
        )
    return None
  
async def lookup_contact(name: str) -> ContactSearchResults:
    """Look up contacts by name using Gmail API"""
    creds: Credentials = await get_fresh_credentials()
    client:Resource  = await GoogleServices.contacts.get_google_service(creds)
    
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Accept": "application/json",
    }
    
    # Use people API to search contacts
    params = {
        "query": name,
        "readMask": "names,emailAddresses,phoneNumbers",
        #"sources": ["READ_SOURCE_TYPE_CONTACT"]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{GoogleServices.contacts.base_url}/{GoogleServices.contacts.version}/people:searchContacts",
                               headers=headers, params=params) as response:
            response.raise_for_status()
            result = await response.json()
            print(f"{response=}") 
            results = [contact for person in result.get("results", []) if (contact := extract_contact(person)) is not None]           
            return ContactSearchResults(results=results)








email_send_agent: Agent[EmailRequest, EmailSendResult] = Agent(  
    'openai:gpt-4o',  
    deps_type=EmailRequest,
    result_type=EmailSendResult,  
    system_prompt=(  
        'You are an email sending agent. Validate the email content '
        'and send it using the Gmail API.'
    ),
) 

contact_lookup_agent: Agent[ContactSearchRequest, list[ContactSearchResults]] = Agent(  
    'openai:gpt-4o',  
    deps_type=ContactSearchRequest,
    result_type=ContactSearchResults,  
    system_prompt=(  
    """
    <prompt>
    <role>
        <description>You are a contact searching agent.</description>
        <responsibility>Validate the contact search request and return the contact details.</responsibility>
    </role>
    
    <validQueries>
        <query type="simpleName">
            <example>John</example>
            <description>Single name search</description>
        </query>
        
        <query type="fullName">
            <example>John Smith</example>
            <description>Full name search</description>
        </query>
        
        <query type="email">
            <example>john@example.com</example>
            <description>Email address search</description>
        </query>
        
        <query type="phone">
            <example>+1-555-123-4567</example>
            <description>Phone number search</description>
        </query>
        
        <query type="organization">
            <example>Acme Corp</example>
            <description>Organization name search</description>
        </query>
        
        <query type="wildcard" supported="unknown">
            <example>j*</example>
            <description>Wildcard search</description>
        </query>
        
        <query type="exactMatch" supported="unknown">
            <example>"John Smith"</example>
            <description>Exact match search</description>
        </query>
    </validQueries>
</prompt>
    """
    ),
) 

    
        




@email_send_agent.tool  
async def send_email(
    ctx: RunContext[EmailRequest], 
) -> EmailSendResult:
    """sends an email using the Gmail API"""  
 
    creds = await get_fresh_credentials()
    content = ctx.deps

    headers = {
        "Authorization": f"Bearer {creds.token}",
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
        f"{GoogleServices.gmail.base_url}/{GoogleServices.gmail.version}/users/me/messages/send",
        headers=headers,
        json=message_data) as response:
            result = await response.json()
            print(f"\n\n\n {["*"]*10}\n Email send result: {result}")
            return EmailSendResult(email_sent=True)

from typing import Annotated , TypeVar, Awaitable, Callable, ParamSpec, Any
from typing import TypeVar, Callable, ParamSpec, Awaitable, Any, cast
from functools import wraps
from pydantic import BaseModel

# T = TypeVar('T', bound=BaseModel)
# P = ParamSpec('P')

# def model_dump_result() -> Callable[[Callable[P, Awaitable[BaseModel]], Callable[P, Awaitable[dict[str, Any]]]]]:
#     """
#     Decorator that takes the result of an async function returning a BaseModel
#     and automatically calls model_dump() on its .data attribute
#     """
#     def decorator(
#         func: Callable[P, Awaitable[BaseModel]]
#     ) -> Callable[P, Awaitable[dict[str, Any]]]:
#         @wraps(func)
#         async def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
#             result = await func(*args, **kwargs)
#             return result .model_dump()
#         return wrapper
        
#     return decorator


async def send_email_to_recipient(prompt: Annotated[str, {"description": "User instruction or prompt for sending the email"}], content:EmailRequest) -> EmailSendResult:
    """ Sends an email to the recipient using the Gmail API if the email address isnt found you must use the contacts agent to look up the email address"""
    return (await email_send_agent.run(prompt, deps=EmailRequest(**content))).data.model_dump()

async def find_contact_information(prompt: Annotated[str, {"description": "User instruction or prompt for finding Contact Information"}], content:ContactSearchRequest) -> ContactSearchResults:
    """ Finds the contact information for the recipient using the contacts agent"""
    return (await contact_lookup_agent.run(prompt, deps=ContactSearchRequest(**content))).data.model_dump()
        
