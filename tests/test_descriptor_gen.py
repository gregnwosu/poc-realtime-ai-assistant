from realtime_api_async_python.modules.gen_descriptor import build_function_descriptor   
from realtime_api_async_python.modules.email_agent import send_email_to_recipient
send_email_descriptor = { "type": "function",
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
    
def test_create_descriptors():
    assert build_function_descriptor(send_email_to_recipient) ==  send_email_descriptor