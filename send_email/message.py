class Message:
    """
    Message format by email library
    - subject
    - text
    - html
    - receiver

    """
    def __init__(self, subject="", text="", html="",receiver=""):
        self.subject = subject
        self.text = text
        self.html = html
        self.receiver_email = receiver


def verificationTextFormatter(request_details,request_code):
    text = "Bleepy Request Alert: "+request_details
    text = text + "\n\n Use this verification code to confirm your request: "+request_code
    text = text + "\n\n DO NOT SHARE THE CODE WITH ANYONE. If you are not the one who are requesting the verification code, immediately update your account security by updating your email and password, and contact Bleepy Support Team."
    return text