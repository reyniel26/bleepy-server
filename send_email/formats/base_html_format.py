from .read_html import read_html
def base_format(title,body_content):
    return read_html("./send_email/formats/parts/base_html_format.html").format(title = title,content = body_content)