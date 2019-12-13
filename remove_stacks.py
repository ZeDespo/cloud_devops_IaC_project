from typing import Optional, Dict, Any

import boto3
import asyncio
import logging
import os


class Counter:

    def __init__(self, size: int):
        self.counter = size


def check_stack(cf: boto3.client, stack_name: str) -> (Dict[str, Any], bool):
    """

    :param cf:
    :param stack_name:
    :return: Whether the stack exists or not and the response that was given from cloudformation
    """
    try:
        response = cf.describe_stacks(StackName=stack_name)
    except cf.exceptions.ClientError:
        return {}, False
    return response, True


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


async def delete_stack(cf: boto3.client, stack_name: str, counter: Counter) -> None:
    """

    :param cf:
    :param stack_name:
    :param counter: A shared resource between coroutines which trigger the root stack's deletion.
    :return:
    """
    exists = True
    while exists:
        if stack_name == root_stack:
            if counter.counter != 0:
                await asyncio.sleep(5)
                continue
        response, exists = check_stack(cf, stack_name)
        if exists:
            if response['Stacks'][0]['StackStatus'] != 'DELETE_IN_PROGRESS':
                logger.info("Deleting {}".format(stack_name))
                cf.delete_stack(StackName=stack_name)
            else:
                await asyncio.sleep(5)
        else:
            counter.counter -= 1
            logger.info("Finished deleting {}".format(stack_name))


def load_aws_creds() -> (str, str, str):
    """
    Load AWS credentials from file
    path: file path to the credential file
    :return: AWS access key and AWS secret key
    """
    session = boto3.Session()
    credentials = session.get_credentials()
    return credentials.access_key, credentials.secret_key, session.region_name


def main():
    """

    :return:
    """
    counter = Counter(len(nested_stacks))
    key, secret, region = load_aws_creds()
    cf = boto3.client('cloudformation', aws_access_key_id=key, aws_secret_access_key=secret, region_name=region)
    loop = asyncio.get_event_loop()
    tasks = [delete_stack(cf, nest_name, counter) for nest_name in nested_stacks]
    tasks.append(delete_stack(cf, root_stack, counter))
    wait_tasks = asyncio.gather(*tasks)
    loop.run_until_complete(wait_tasks)


if __name__ == '__main__':
    root_stack = 'udagramNetworking'
    nested_stacks = ['udagramIAM', 'udagramEC2', 'udagramS3']
    logger = create_logger()
    main()
