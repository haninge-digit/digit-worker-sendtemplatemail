import os
import logging
import asyncio

from worker import worker_loop
from send_template_mail import send_template_mail


""" 
Environment
"""
DEBUG_MODE = os.getenv('DEBUG','false') == "true"                       # Global DEBUG logging

LOGFORMAT = "%(asctime)s %(funcName)-10s [%(levelname)s] %(message)s"   # Log format


"""
MAIN function (starting point)
"""
def main():
    # Enable logging. INFO is default. DEBUG if requested
    logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO, format=LOGFORMAT)

    asyncio.run(worker_loop(send_template_mail))     # Run worker in an async loop


if __name__ == "__main__":
    main()
