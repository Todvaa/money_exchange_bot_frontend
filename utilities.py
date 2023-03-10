import json
import os
import pytz
import requests
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime


load_dotenv()

domain = os.getenv('DOMAIN')
timezone = pytz.timezone('Asia/Colombo')

BAN_LIST = []


def parse_json(json_object):
    return json.loads(json_object)


def ban(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id in cached_ban_list():
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='Вы были забанены.',
            )
            return
        return func(update, context, *args, **kwargs)
    return wrapped


def get_ban_list():
    banned_users = parse_json(requests.get(f'{domain}v1/user-admin/?search=banned').text)
    for banned_user in banned_users:
        BAN_LIST.append(banned_user['id'])


def cached_ban_list():
    if len(BAN_LIST) == 0:
        get_ban_list()
    return BAN_LIST


def get_current_time(date):
    return datetime.strptime(
        date, "%Y-%m-%dT%H:%M:%S.%f%z"
    ).astimezone(timezone).strftime(
        '%d.%m.%Y %H:%M'
    )


def exchange_request_dictionary_validator(update, context, key):
    if update.effective_chat.id not in context.chat_data:
        return False
    if key not in context.chat_data[update.effective_chat.id]:
        return False
    return True


def chat_data_validator(context):
    if (
            'interaction_object' not in context.chat_data
            and 'active_requests' not in context.chat_data
    ):
        return False
    return True


def request_interaction_object_validator(context):

    if (
            'request_id' not in context.chat_data['interaction_object']
            and 'user_id' not in context.chat_data['interaction_object']
    ):
        return False
    return True


def reward_interaction_object_validator(context):

    if (
            'payment' not in context.chat_data['interaction_object']
            and 'user_id' not in context.chat_data['interaction_object']
    ):
        return False
    return True
