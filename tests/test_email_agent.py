import pytest
from realtime_api_async_python.modules.email_agent import _lookup_contact, ContactSearchResults, GoogleServices, get_fresh_credentials
from pytest import fail
from typing import Any  
from logging import getLogger
import aiohttp 

logger = getLogger(__name__)

def to_legacy_format(result: ContactSearchResults) -> dict[str, Any]:
    """Convert new Pydantic model to old dictionary format"""
    return {
        "status": "success" if result.results else "error",
        "contacts": [
            {"name": contact.name, "email": contact.email}
            for contact in result.results
        ],
        "message": f"Found {len(result.results)} contacts" if result.results else "No contacts found"
    }

@pytest.mark.skip(reason="This test is not meant to be run in CI/CD pipelines")
@pytest.mark.asyncio
async def test_lookup_contact_real():
    """
    Integration test using legacy format.
    """
    # Test with a real name
    model_result = await _lookup_contact("greg nwosu")
    result = to_legacy_format(model_result)
    
    # Verify the structure of the response
    assert "status" in result
    assert "contacts" in result
    assert "message" in result
    
    if result["status"] == "success":
        # Verify each contact has the required fields
        for contact in result["contacts"]:
            assert "name" in contact
            assert "email" in contact
            assert "@" in contact["email"]  # Basic email format check
            
        print(f"\nFound {len(result['contacts'])} contacts:")
        for contact in result["contacts"]:
            print(f"Name: {contact['name']}, Email: {contact['email']}")
    else:
        print(f"\nNo contacts found or error occurred: {result['message']}")
        pytest.fail("die")
    


# @pytest.mark.skip(reason="This test is not meant to be run in CI/CD pipelines")
# @pytest.mark.asyncio
# async def test_find_contact_empty_query():
#     """Test with an empty string"""
#     result = await _lookup_contact("")
#     assert "status" in result
#     assert "message" in result

# @pytest.mark.skip(reason="This test is not meant to be run in CI/CD pipelines")
# @pytest.mark.asyncio
# async def test_find_contact_special_characters():
#     """Test with special characters"""
#     result = await _lookup_contact("!@#$%^")
#     assert "status" in result
#     assert "message" in result


@pytest.mark.asyncio
async def test_lookup_contact_real():
    """Integration test with detailed debugging"""
    # First check credentials
    creds = await get_fresh_credentials()
    assert "https://www.googleapis.com/auth/contacts" in creds.scopes, "Missing contacts scope"
    logger.info("Credentials loaded with scopes: %s", creds.scopes)
    
    # Try listing contacts first
    async with aiohttp.ClientSession() as session:
        # List contacts endpoint
        list_url = f"{GoogleServices.contacts.base_url}/{GoogleServices.contacts.version}/people/me/connections"
        list_params = {
            "pageSize": 10,
            "personFields": "names,emailAddresses,phoneNumbers"
        }
        headers = {
            "Authorization": f"Bearer {creds.token}",
            "Accept": "application/json",
        }
        
        logger.info("Attempting to list contacts first...")
        async with session.get(list_url, headers=headers, params=list_params) as response:
            list_status = response.status
            list_text = await response.text()
            logger.info("List contacts status: %d", list_status)
            logger.info("List contacts response: %s", list_text)
            
        # Now try search
        logger.info("Now attempting search...")
        search_url = f"{GoogleServices.contacts.base_url}/{GoogleServices.contacts.version}/people:searchContacts"
        search_params = {
            "query": "greg nwosu",
            "readMask": "names,emailAddresses,phoneNumbers"
        }
        
        async with session.get(search_url, headers=headers, params=search_params) as response:
            search_status = response.status
            search_text = await response.text()
            logger.info("Search status: %d", search_status)
            logger.info("Search response: %s", search_text)
    
    # Now try the actual function
    logger.info("Testing main lookup function...")
    result = await _lookup_contact("greg nwosu")
    
    # Print results for debugging
    logger.info("Final results: %s", result)
    
    # Basic assertion to force output
    assert True, "Test complete - check logs"