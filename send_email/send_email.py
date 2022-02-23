import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv
load_dotenv()

from .message import Message

#Sender credentials
sender_email = os.environ.get("bleepy_email")
sender_pwd = os.environ.get("bleepy_pwd")

def sendEmail(msg:Message):
    message = MIMEMultipart("alternative")
    message["Subject"] = msg.subject
    message["From"] = sender_email
    message["To"] = msg.receiver_email

    # Turn these into plain/html MIMEText objects
    textmsg = MIMEText(msg.text, "plain")
    htmlmsg = MIMEText(msg.html, "html")

    # Add HTML/plain-text parts to MIMEMultipart message
    # The email client will try to render the last part first
    message.attach(textmsg)
    message.attach(htmlmsg)

    #Server
    try:
        server = smtplib.SMTP("smtp.gmail.com",587) 
        server.starttls() #run server
        server.login(sender_email,sender_pwd) #log in
        server.sendmail(sender_email,msg.receiver_email,message.as_string())
        server.quit()
    except Exception as e:
        print(e)
        return False
    else:
        print("Done sending email!")
        return True
