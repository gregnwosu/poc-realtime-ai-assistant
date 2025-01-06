
import base64
import json
from dataclasses import dataclass
from datetime import datetime as dt
from enum import Enum
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from async_lru import alru_cache
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from pydantic import (AnyHttpUrl, BaseModel, EmailStr, Field, HttpUrl, model_validator)
from pydantic_ai import Agent, RunContext
from pydantic_ai.result import RunResult
from pydantic_extra_types.phone_numbers import PhoneNumber



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
              "https://www.googleapis.com/auth/contacts"
              ]

    client_secrets_path: Path = Path(".client_secret.json")
    token_path: Path = Path(".gmail_token.json")
    
    creds : Optional[Credentials] = None
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
       
    match creds:
        case None:
             raise Exception("Failed to get credentials")
        case _:
            with open(token_path, 'w') as token_file:
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
            

class GoogleServices( Enum):
    contacts = ("people", "v1", "https://people.googleapis.com")
    gmail = ("gmail", "v1", "https://gmail.googleapis.com/gmail") 
    
    def __init__(self, service_name: str, version: str, base_url: str):
        super().__init__()
        self.service_name = service_name
        self.version = version
        self.base_url = base_url
    
    def get_google_service(self, credentials: Credentials) -> Resource:
        # Build and return the service
        return build(self.service_name, self.version, credentials=credentials)
    








email_send_agent: Agent[EmailRequest, EmailSendResult] = Agent(  
    'openai:gpt-4o',  
    deps_type=EmailRequest,
    result_type=EmailSendResult,  
    system_prompt=(  
        'You are an email sending agent. Validate the email content '
        'and send it using the Gmail API.'
    ),
) 

contact_lookup_agent: Agent[ContactSearchRequest, ContactSearchResults] = Agent(  
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


import json
import logging
from typing import Optional

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def extract_contact(person: dict) -> Optional[ContactSearchResult]:
    """Extracts a ContactSearchResult from a person dict if names and emails exist."""
    logger.debug("Extracting contact from person data: %s", json.dumps(person, indent=2))
    
    person_data = person.get("person", {})
    logger.debug("Person data: %s", json.dumps(person_data, indent=2))
    
    names = person_data.get("names", [])
    emails = person_data.get("emailAddresses", [])
    phone_numbers = person_data.get("phoneNumbers", [])
    
    logger.debug("Extracted fields:")
    logger.debug("Names: %s", names)
    logger.debug("Emails: %s", emails)
    logger.debug("Phone numbers: %s", phone_numbers)
    
    if names and ( phone_numbers or emails):
        contact = ContactSearchResult(
            name=names[0].get("displayName", None),
            email=emails[0].get("value", None) if phone_numbers else None,
            phone_number=phone_numbers[0].get("value", None) if phone_numbers else None
        )
        logger.debug("Created contact: %s", contact)
        return contact
    
    logger.debug("No valid contact data found")
    return None

def extract_contact(person: dict) -> Optional[ContactSearchResult]:
    """
    Extracts a ContactSearchResult from a person dict if required fields exist.
    Now handles missing email addresses properly.
    """
    logger.debug("Extracting contact from person data: %s", json.dumps(person, indent=2))
    
    person_data = person.get("person", {})
    names = person_data.get("names", [])
    emails = person_data.get("emailAddresses", [])
    phone_numbers = person_data.get("phoneNumbers", [])
    
    logger.debug("Extracted fields:")
    logger.debug("Names: %s", names)
    logger.debug("Emails: %s", emails)
    logger.debug("Phone numbers: %s", phone_numbers)
    
    # Must have at least a name
    if not names:
        logger.debug("No name found, skipping contact")
        return None
        
    # Extract basic info - name is required
    name = names[0].get("displayName", "")
    if not name:
        logger.debug("Empty name found, skipping contact")
        return None
        
    # Email is optional
    email = emails[0].get("value", "") if emails else ""
    
    # Phone is optional
    phone_number = phone_numbers[0].get("value", "") if phone_numbers else ""
    
    contact = ContactSearchResult(
        name=name,
        email=email,
        phone_number=phone_number
    )
    
    logger.debug("Created contact: %s", contact)
    return contact

async def _lookup_contact(query: str) -> ContactSearchResults:
    """Look up contacts by name using Gmail API"""
    logger.info("Looking up contact with query: %s", query)
    
    creds: Credentials = await get_fresh_credentials()
    logger.debug("Got credentials with token: %s...", creds.token[:10])
    
    client: Resource = GoogleServices.contacts.get_google_service(creds)
    logger.debug("Created Google service client")
    
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Accept": "application/json",
    }
    
    params = {
        "query": query,
        "readMask": "names,emailAddresses,phoneNumbers",
        # "sources": [  # Will be properly encoded as multiple query params
        #     "READ_SOURCE_TYPE_CONTACT",
        #     "READ_SOURCE_TYPE_DOMAIN_CONTACT",
        #     "READ_SOURCE_TYPE_PROFILE",
        #     "READ_SOURCE_TYPE_OTHER_CONTACT"
        # ]
    }
    
    url = f"{GoogleServices.contacts.base_url}/{GoogleServices.contacts.version}/people:searchContacts"
    logger.debug("Making request to URL: %s", url)
    logger.debug("Request params: %s", params)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, params=params) as response:
            response.raise_for_status()
            logger.debug("Response status: %s", response.status)
            logger.debug("Response headers: %s", dict(response.headers))
            
            result = await response.json()
            logger.debug("Raw API response: %s", json.dumps(result, indent=2))
            
            results = []
            for person in result.get("results", []):
                logger.debug("Processing person: %s", json.dumps(person, indent=2))
                if contact := extract_contact(person):
                    results.append(contact)
                    logger.debug("Added contact to results: %s", contact)
            
            search_results = ContactSearchResults(results=results)
            logger.info("Found %d contacts", len(results))
            return search_results

async def list_contacts(creds: Credentials) -> dict:
    """List first few contacts to verify access"""
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Accept": "application/json",
    }
    
    params = {
        "pageSize": 10,
        "personFields": "names,emailAddresses,phoneNumbers"
    }
    
    async with aiohttp.ClientSession() as session:
        url = f"{GoogleServices.contacts.base_url}/{GoogleServices.contacts.version}/people/me/connections"
        logger.debug("Making list request to: %s", url)
        logger.debug("With params: %s", params)
        
        async with session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"List contacts error: {error_text}")
            response.raise_for_status()
            return await response.json()

async def _lookup_contact(query: str) -> ContactSearchResults:
    """Look up contacts by name using Gmail API"""
    logger.info("Looking up contact with query: %s", query)
    
    creds: Credentials = await get_fresh_credentials()
    
    # Try finding contacts by partial name match from the connections list
    async with aiohttp.ClientSession() as session:
        url = f"{GoogleServices.contacts.base_url}/{GoogleServices.contacts.version}/people/me/connections"
        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Accept": "application/json",
        }
        params = {
            "pageSize": 1000,  # Get more contacts
            "personFields": "names,emailAddresses,phoneNumbers"
        }
        
        async with session.get(url, headers=headers, params=params) as response:
            response.raise_for_status()
            result = await response.json()
            
            # Do our own filtering since search API isn't working
            query_terms = query.lower().split()
            matched_contacts = []
            
            for connection in result.get("connections", []):
                names = connection.get("names", [])
                if not names:
                    continue
                    
                name = names[0].get("displayName", "").lower()
                # Check if all query terms are in the name
                if all(term in name for term in query_terms):
                    if contact := extract_contact({"person": connection}):
                        matched_contacts.append(contact)
                        
            return ContactSearchResults(results=matched_contacts)

@contact_lookup_agent.tool  
async def lookup_contact( ctx: RunContext[ContactSearchRequest], ) -> ContactSearchResults:
    """Look up contacts via query using Gmail API"""
    query = ctx.deps.query
    return await _lookup_contact(query)




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
    
    # this is for debugging purposes
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

from functools import wraps
from typing import (Annotated, Any, Awaitable, Callable, ParamSpec, TypeVar,
                    cast)

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
        
