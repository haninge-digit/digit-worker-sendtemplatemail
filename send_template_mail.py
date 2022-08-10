import os
import json
import httpx
import traceback

from worker import WorkerError

from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import jinja2

INT_MAIL = os.getenv('INT_MAIL',"")
TEMPLATE_URL = os.getenv('TEMPLATE_URL',"")

async def load_template(template_url:str):
    if "https" not in template_url:
        template_url = f"{TEMPLATE_URL}/{template_url}"     # Add the TEMPLATE_URL prefix

    try:
        res = await httpx.AsyncClient().get(template_url)
    except httpx.ReadTimeout as e:
        raise WorkerError(f"load_template() raised httpx.ReadTimeout", retry_in=10)       # Timeout. Try again in 10 seconds
    if res.status_code != 200:
        raise WorkerError(f"get template returned {res.status_code}", retries=0)          # Something is wrong. Don't try anymore 

    return res.text


async def send_template_mail(vars):
    template_str = await load_template(vars['mail_template'])
    email_template = jinja2.Environment().from_string(template_str)

    rendered_content = email_template.render(vars)      # Pass all vaiables to template

    # message = EmailMessage()
    message = MIMEMultipart('alternative')
    message["From"] = "NoReply@haninge.se"
    message["To"] = vars['mail_recipient']
    message["Subject"] = vars['mail_subject'] if 'mail_subject' in vars else "Meddelande från Haninge Kommun"
    # message.set_content(rendered_content)
    message.attach(MIMEText("Kontakta digit@haninge.se om du ser den här texten!", 'plain'))
    message.attach(MIMEText(rendered_content, 'html'))

    async with httpx.AsyncClient(timeout=10, verify=False) as client:       # Proxy cert is selfsigned
        try:
            await client.post(INT_MAIL, json={'EmailMessage':message.as_string()})       # Send to proxy
        except httpx.ReadTimeout as e:
            raise WorkerError(f"send email to proxy raised httpx.ReadTimeout", retry_in=10)       # Timeout. Try again in 10 seconds

    return {}
