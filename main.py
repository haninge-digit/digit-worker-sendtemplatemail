import os
import logging
import asyncio

import grpc
from zeebe_grpc import gateway_pb2_grpc
from zeebe_grpc.gateway_pb2 import (
    Resource,
    DeployResourceRequest)

from worker import worker_loop
from send_template_mail import send_template_mail


""" 
Environment
"""
ZEEBE_ADDRESS = os.getenv('ZEEBE_ADDRESS',"camunda-zeebe-gateway.camunda-zeebe:26500")

DEBUG_MODE = os.getenv('DEBUG','false') == "true"                       # Global DEBUG logging

LOGFORMAT = "%(asctime)s %(funcName)-10s [%(levelname)s] %(message)s"   # Log format


"""
Deploy BPMN-worflow(s)
"""
def deployAllToCamunda():
    with grpc.insecure_channel(ZEEBE_ADDRESS) as channel:
        stub = gateway_pb2_grpc.GatewayStub(channel)
        for f in os.listdir():      # Find all .bpmn-files
            if ".bpmn" in f:
                logging.info(f"Trying to deploy {f} to Camunda")
                with open(f, "rb") as process_definition_file:
                    process_definition = process_definition_file.read()
                    process = Resource(name=f,content=process_definition)
                    response = stub.DeployResource(DeployResourceRequest(resources=[process]))
                    logging.info(f"Deployed BPMN process {response.deployments[0].process.bpmnProcessId} as version {response.deployments[0].process.version}")


"""
MAIN function (starting point)
"""
def main():
    # Enable logging. INFO is default. DEBUG if requested
    logging.basicConfig(level=logging.DEBUG if DEBUG_MODE else logging.INFO, format=LOGFORMAT)

    deployAllToCamunda()        # Deploy worker process

    asyncio.run(worker_loop(send_template_mail))     # Run worker in an async loop


if __name__ == "__main__":
    main()
