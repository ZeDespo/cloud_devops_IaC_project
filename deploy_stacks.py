from typing import Optional, List, Dict, Any
import configparser
import boto3
import time
import logging
import os
import json


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


def create_stack(cf: boto3.client, wait_for_creation: bool, stack_name: str, template_path: str,
                 params_path: str or None, capabilities: List[str]) -> None:
    """
    Create the stack for cloudformation
    :param cf: The cloudformation client from boto3
    :param wait_for_creation: Whether we wait for the stack to be created before moving on with the program or not.
    :param stack_name: The name to give the stack
    :param template_path: The path to the template (local file system only)
    :param params_path: The path to the parameters file (local file system only)
    :param capabilities: Special permissions to assign each stack
    :return: Nothing
    """
    exists = False
    while not exists:
        response, created = check_stack(cf, stack_name)
        if created:
            if response['Stacks'][0]['StackStatus'] == 'CREATE_COMPLETE':
                exists = True
            elif response['Stacks'][0]['StackStatus'] == 'CREATE_IN_PROGRESS':
                if wait_for_creation:
                    time.sleep(5)
                else:
                    break
            else:
                raise ValueError(response['Stacks'][0]['StackStatus'])
        else:
            logger.info("Creating stack.")
            template = _read_local_template(cf, template_path)
            if params_path:
                with open(params_path) as f:
                    params = json.load(f)
            else:
                params = None
            cf.create_stack(StackName=stack_name, TemplateBody=template, Parameters=params, Capabilities=capabilities)
            logger.debug("Waiting for Cloudformation to finalize creation...")


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
    return response, True


def read_config_file(path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Read from some INI file.
    :param path: The ini file path
    :return: The parsed config file.
    StackName=stack_name, TemplateBody=template, Parameters=params, Capabilities=capabilities
    """
    c = configparser.ConfigParser(allow_no_value=True)
    with open(path, "r") as f:
        c.read_file(f)
    config = {'root': [], 'nested': []}
    for section in c.sections():
        if section == 'root_stack':
            c_ptr = config['root']
        else:
            c_ptr = config['nested']
        stack_name = c.get(section, 'name')
        template_path = c.get(section, 'template_path')
        params_path = c.get(section, 'params_path')
        capabilities = c.get(section, 'capabilities')
        c_ptr.append(
            {
                'stack_name': stack_name,
                'template_path': template_path,
                'params_path': None if not params_path else params_path,
                'capabilities': [] if not capabilities else capabilities.split(',')
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
    config = read_config_file('stack_config.ini')
    root = config['root'][0]
    logger.info("Checking for root stack's existence.")
    create_stack(cf, wait_for_creation=True, **root)
    logger.info("Root stack verified.")
    nested_stacks = config['nested']
    for nest in nested_stacks:
        logger.info("Creating {} stack".format(nest['stack_name']))
        create_stack(cf, wait_for_creation=False, **nest)
        logger.info("Finished creating {}".format(nest['stack_name']))


if __name__ == '__main__':
    logger = create_logger(False)
    main()
