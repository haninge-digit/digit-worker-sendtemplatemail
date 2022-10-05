import os
import base64
import json
import logging

from zeebe_worker import WorkerError

from msgraph.core import GraphClient
from azure.identity import ClientSecretCredential

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import jinja2

import httpx


""" 
Environment
"""
TEMPLATE_URL = os.getenv('TEMPLATE_URL',"")

AD_TENANT_ID = os.getenv('AD_TENANT_ID')
AD_CLIENT_ID = os.getenv('AD_CLIENT_ID')
AD_CLIENT_SECRET = os.getenv('AD_CLIENT_SECRET')

INT_MAIL = os.getenv('INT_MAIL',"")


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
        stand_alone = '_STANDALONE' in vars

        if 'mailRecipient' not in vars:
            return self._handle_error(stand_alone, "Variable 'mailRecipient' is missing")
        template_url = vars.get('mailTemplate',"empty_mail.html.jinja")
        if "https" not in template_url:
            template_url = f"{TEMPLATE_URL}/{template_url}"     # Add the TEMPLATE_URL prefix

        try:
            res = await httpx.AsyncClient().get(template_url)
        except httpx.ReadTimeout as e:
            return self._handle_error(stand_alone, f"load_template() raised httpx.ReadTimeout")
        if res.status_code != 200:
            if res.status_code == 404:
                return self._handle_error(stand_alone, f"Template {template_url} not found!")
            else:
                return self._handle_error(stand_alone, f"get template returned {res.status_code}")

        email_template = jinja2.Environment().from_string(res.text)     # Load template into Jinja

        if '_JSON_BODY' in vars:
            render_variables = json.loads(vars['_JSON_BODY'])       # All render variables are in the JSON body as a string
        else:
            render_variables = vars                     # Just grab whats there (probably noting useful)

        try:
            rendered_content = email_template.render(render_variables)      # Pass all variables to template
        except:
            loggtext = f"Render failed. Call contained _JSON_BODY = {'_JSON_BODY' in vars}"
            logging.error(loggtext)
            if '_STANDALONE' in vars:   # This is a single worker
                return {'_DIGIT_ERROR': loggtext}     # We can return an error
            raise WorkerError(loggtext, retries=0)       # Fatal! Halt the process

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

        # async with httpx.AsyncClient(timeout=10, verify=False) as client:       # Proxy cert is selfsigned
        #     try:
        #         await client.post(INT_MAIL, json={'EmailMessage':message.as_string()})       # Send to proxy
        #     except httpx.ReadTimeout as e:
        #         raise WorkerError(f"send email to proxy raised httpx.ReadTimeout", retry_in=10)       # Timeout. Try again in 10 seconds

        credential = ClientSecretCredential(AD_TENANT_ID, AD_CLIENT_ID, AD_CLIENT_SECRET)
        client = GraphClient(credential=credential)
        userPrincipalName = "noreply@haninge.se"

        result = client.post(f"/users/{userPrincipalName}/sendMail", data=base64.b64encode(message.as_string().encode('utf-8')), headers={'Content-Type': 'text/plain'})
        if 'error' in result:
            loggtext = f"sendMail failed! {result['error']['code']: {result['error']['message']}}"
            logging.error(loggtext)
            if '_STANDALONE' in vars:
                return {'_DIGIT_ERROR': loggtext}       # This can be returned to the caller
            else:
                raise WorkerError(loggtext, retries=0)          # In a worklfow so cancel further processeing

        return {}


    def _handle_error(self,stand_alone,loggtext):
        logging.error(loggtext)
        if stand_alone:
            return {'_DIGIT_ERROR': loggtext}       # This can be returned to the caller
        else:
            raise WorkerError(loggtext, retries=0)          # In a worklfow so cancel further processeing
        pass