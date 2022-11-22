import os
import base64
import json
import logging

from zeebe_worker import WorkerError

from msgraph.core import GraphClient
from azure.identity import ClientSecretCredential

from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

import jinja2
import weasyprint

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

        if 'JSON_DUMP' in vars:         # Just do a JSON-dump of the whole stuff
            body = json.dumps(json.loads(vars['_JSON_BODY']),indent=2)      # Stupid way to format JSON?   
            rendered_content = f"<html><head></head><body><pre>{body}</pre></body></html>"
            if 'mailSubject' not in vars:
                vars['mailSubject'] = f"JSON DUMP from {self.queue_name} worker"        # We need a mail subject

        else:                           # Normal template parsing
            template_url = vars.get('mailTemplate',"empty_mail.html.jinja")
            if "https" not in template_url:
                template_url = f"{TEMPLATE_URL}/{template_url}"     # Add the TEMPLATE_URL prefix

            try:
                res = await httpx.AsyncClient().get(template_url)   # Read the teamplate from some external public storage (Github)
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
                render_variables = vars                     # Just grab whats there (probably nothing useful)

            try:
                rendered_content = email_template.render(render_variables)      # Render the template with Jinja2
            except Exception as e:         # Render will fail if data and template doesn't match!
                loggtext = f"Template render failed with error: {e}. Call contained a JSON body = {'_JSON_BODY' in vars}"
                logging.error(loggtext)
                if '_STANDALONE' in vars:   # This is a single worker
                    return {'_DIGIT_ERROR': loggtext}     # We can return an error
                raise WorkerError(loggtext, retries=0)       # Fatal! Halt the process

        if 'ATTACH_PDF' in vars:        # Ww can also check for things like "ATTACH_PDF=email" meaning the content of the email as PDF
            pdf = weasyprint.HTML(string=rendered_content).write_pdf()      # Which is the only thing we implemen right now
        else:
            pdf = None

        if 'mailSubject' in vars:
            mail_subject = vars['mailSubject']
        elif 'header' in render_variables:
            mail_subject = render_variables['header']
        else:
            mail_subject = "Meddelande från Haninge Kommun"

        message = MIMEMultipart('alternative')          # Create a MIME message
        message["From"] = "NoReply@haninge.se"
        message["To"] = vars['mailRecipient']           # Could be one or more comma-seperated recipients
        message["Subject"] = mail_subject
        message.attach(MIMEText("Kontakta digit@haninge.se om du ser den här texten!", 'plain'))
        message.attach(MIMEText(rendered_content, 'html'))      # Add the HTML formatted content
        if pdf:
            attachment = MIMEApplication(pdf,'application/pdf')
            attachment.add_header('Content-Disposition', 'attachment', filename=f"{mail_subject}.pdf")
            message.attach(attachment)            

        credential = ClientSecretCredential(AD_TENANT_ID, AD_CLIENT_ID, AD_CLIENT_SECRET)
        client = GraphClient(credential=credential)         # Get a authenticated Graph client. Might be better to have one for the whole worker?
        userPrincipalName = "noreply@haninge.se"            # This is the user account that our mail are sent from

        result = client.post(f"/users/{userPrincipalName}/sendMail", 
                            data=base64.b64encode(message.as_string().encode('utf-8')),
                            headers={'Content-Type': 'text/plain'})
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