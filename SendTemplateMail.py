import os
import traceback
import json
import logging
import uuid

from zeebe_worker import WorkerError

import httpx

from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import jinja2

""" 
Environment
"""
INT_MAIL = os.getenv('INT_MAIL',"")
TEMPLATE_URL = os.getenv('TEMPLATE_URL',"")


"""
This is the SendTemplateMail worker class.

The API i described in (the non existent) tasks_api.yaml

Input header variables are the basic set (documented elseware...)
"""


class SendTemplateMail(object):

    queue_name = "sendtemplatemail"        # Name of the Zeebe task queue. Will also influence the worker process ID and name


    """
    Init function. Nothing here so far.
    """
    def __init__(self, async_loop):
        pass


    async def worker(self, vars):
        template_str = await self._load_template(vars['mailTemplate'])
        email_template = jinja2.Environment().from_string(template_str)

        if '_JSON_BODY' in vars:
            render_variables = json.loads(vars['_JSON_BODY'])       # All render variables are in the JSON body as a string
        else:
            render_variables = vars                     # Just grab whats there (probably noting useful)

        try:
            rendered_content = email_template.render(render_variables)      # Pass all variables to template
        except:
            if '_STANDALONE' in vars:   # This is a single worker
                return {'_DIGIT_ERROR':f"Render failed. Call contained _JSON_BODY = {'_JSON_BODY' in vars}"}     # We can return an error
            raise WorkerError(f"Render failed. Call contained _JSON_BODY = {'_JSON_BODY' in vars}", retries=0)       # Fatal! Halt the process

        if 'mailSubject' in vars:
            mail_subject = vars['mailSubject']
        elif 'header' in render_variables:
            mail_subject = render_variables['header']
        else:
            mail_subject = "Meddelande från Haninge Kommun"

        # message = EmailMessage()
        message = MIMEMultipart('alternative')
        message["From"] = "NoReply@haninge.se"
        message["To"] = vars['mailRecipient']
        message["Subject"] = mail_subject
        # message.set_content(rendered_content)
        message.attach(MIMEText("Kontakta digit@haninge.se om du ser den här texten!", 'plain'))
        message.attach(MIMEText(rendered_content, 'html'))

        async with httpx.AsyncClient(timeout=10, verify=False) as client:       # Proxy cert is selfsigned
            try:
                await client.post(INT_MAIL, json={'EmailMessage':message.as_string()})       # Send to proxy
            except httpx.ReadTimeout as e:
                raise WorkerError(f"send email to proxy raised httpx.ReadTimeout", retry_in=10)       # Timeout. Try again in 10 seconds

        return {}


    async def _load_template(self, template_url:str):
        if "https" not in template_url:
            template_url = f"{TEMPLATE_URL}/{template_url}"     # Add the TEMPLATE_URL prefix

        try:
            res = await httpx.AsyncClient().get(template_url)
        except httpx.ReadTimeout as e:
            raise WorkerError(f"load_template() raised httpx.ReadTimeout", retry_in=10)       # Timeout. Try again in 10 seconds
        if res.status_code != 200:
            raise WorkerError(f"get template returned {res.status_code}", retries=0)          # Something is wrong. Don't try anymore 

        return res.text


