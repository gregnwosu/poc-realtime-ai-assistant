from realtime_api_async_python.modules.gen_descriptor import build_function_descriptor   
from realtime_api_async_python.modules.email_agent import send_email_to_recipient, get_send_email_descriptor
    
def test_create_descriptors():
    assert build_function_descriptor(send_email_to_recipient) ==  get_send_email_descriptor()