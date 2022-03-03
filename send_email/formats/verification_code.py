from .base_html_format import base_format
from .read_html import read_html

def verification_code_msg(title,request_details,request_code):
    body_content = read_html("./send_email/formats/parts/format_verification_code.html").format(request_details=request_details,request_code=request_code)
    return base_format(title,body_content)