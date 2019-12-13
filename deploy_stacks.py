from typing import Optional, List, Dict, Any
import configparser
import boto3
import logging
import os
import json
import asyncio


class StackTracker:

    def __init__(self, values: Optional[set]=None):
        """
        Sole purpose is to keep track of stacks so asynchronous tasks have a shared resource to pull
        from.
        """
        self.stacks = set() if not values else values


def create_logger(debug_mode: Optional[bool]=False) -> logging.getLogger:
    """
    Self-explanatory, create a logger for streaming output
    :param debug_mode: Is the developer debugging this or no?
    :return: The logging object.
    """
    logger = logging.getLogger(os.path.basename(__name__))
    logger.setLevel(logging.INFO if not debug_mode else logging.DEBUG)
    formatter = logging.Formatter('%(filename)s:%(funcName)s:%(levelname)s:%(message)s')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


async def create_stack(cf: boto3.client, st: StackTracker, stack_name: str, template_path: str,
                 params_path: str or None, capabilities: List[str], depends_on: List[str]) -> None:
    """
    Create the stack for cloudformation
    :param cf: The cloudformation client from boto3
    :param st: Keeps track of all completed stacks so dependent stacks encounter no errors upon creation.
    :param stack_name: The name to give the stack
    :param template_path: The path to the template (local file system only)
    :param params_path: The path to the parameters file (local file system only)
    :param capabilities: Special permissions to assign each stack
    :param depends_on: The stacks that need to be created before this stack is created.
    :return: Nothing
    """
    exists, proceed_creation = False, False if depends_on else True
    while not exists:
        if not proceed_creation:  # if there are dependencies, don't proceed until "parent" stacks created
            terminate_loop = True
            for dep in depends_on:
                if dep not in st.stacks:
                    logger.debug("Stack {} cannot be created since stack {} does not exist.".format(stack_name, dep))
                    terminate_loop = False
                    await asyncio.sleep(5)
                    break
            if not terminate_loop:
                continue
            else:
                proceed_creation = True
        response, created = check_stack(cf, stack_name)
        if created:
            stack_status = response['Stacks'][0]['StackStatus']
            if stack_status == 'CREATE_COMPLETE':
                exists = True
                st.stacks.add(stack_name)
                logger.info("Stack {} created.".format(stack_name))
            elif stack_status == 'CREATE_IN_PROGRESS':
                await asyncio.sleep(5)
            else:
                raise ValueError(response['Stacks'][0]['StackStatus'])
        else:
            logger.info("Creating stack {}.".format(stack_name))
            template = _read_local_template(cf, template_path)
            if params_path:
                with open(params_path) as f:
                    params = json.load(f)
            else:
                params = None
            cf.create_stack(StackName=stack_name, TemplateBody=template, Parameters=params, Capabilities=capabilities)
            logger.debug("Waiting for Cloudformation to finalize creation of {}...".format(stack_name))


def check_stack(cf: boto3.client, stack_name: str) -> (Dict[str, Any], bool):
    """
    Check if the stack exists
    :param cf: The cloudformation client from boto3
    :param stack_name: The name to give the stack
    :return: Whether the stack exists or not and the response that was given from cloudformation
    """
    try:
        response = cf.describe_stacks(StackName=stack_name)
    except cf.exceptions.ClientError:
        return {}, False
    if response['Stacks'][0]['StackStatus'] == 'DELETE_IN_PROGRESS':
        return {}, False
    return response, True


def read_config_file(path: str) -> List[Dict[str, Any]]:
    """
    Read from some INI file.
    :param path: The ini file path
    :return: The parsed config file.
    """
    c = configparser.ConfigParser(allow_no_value=True)
    with open(path, "r") as f:
        c.read_file(f)
    config = []
    for section in c.sections():
        depends_on = c.get(section, 'depends_on')
        stack_name = c.get(section, 'name')
        template_path = c.get(section, 'template_path')
        params_path = c.get(section, 'params_path')
        capabilities = c.get(section, 'capabilities')
        config.append(
            {
                'stack_name': stack_name,
                'template_path': template_path,
                'params_path': None if not params_path else params_path,
                'capabilities': [] if not capabilities else capabilities.split(','),
                'depends_on': [] if not depends_on else depends_on.split(',')
            }
        )
    return config


def load_aws_creds() -> (str, str, str):
    """
    Load AWS credentials from file
    path: file path to the credential file
    :return: AWS access key and AWS secret key
    """
    session = boto3.Session()
    credentials = session.get_credentials()
    return credentials.access_key, credentials.secret_key, session.region_name


def _read_local_template(cf: boto3.client, template_path: str) -> str:
    """
    Read and validate some template file.
    :param cf: The cloudformation client from boto3
    :param template_path: The path to the template (local file system only)
    :return: The contents of the file
    """
    with open(template_path) as f:
        template = f.read()
    cf.validate_template(TemplateBody=template)
    return template


def main():
    key, secret, region = load_aws_creds()
    cf = boto3.client('cloudformation', aws_access_key_id=key, aws_secret_access_key=secret, region_name=region)
    stack_tracker = StackTracker()
    config = read_config_file('stack_config.ini')
    loop = asyncio.get_event_loop()
    tasks = [create_stack(cf, stack_tracker, **c) for c in config]
    wait_tasks = asyncio.gather(*tasks)
    loop.run_until_complete(wait_tasks)


if __name__ == '__main__':
    logger = create_logger()
    main()
