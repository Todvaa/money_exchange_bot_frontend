import os
from functools import wraps
import requests
from dotenv import load_dotenv

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import CallbackContext
from telegram.utils.helpers import create_deep_linked_url

from constants import DEVELOPER_PERCENT, REFERRER_PERCENT, LAST_REQUESTS
from utilities import (
    parse_json, get_ban_list, get_current_time,
    chat_data_validator, request_interaction_object_validator,
    reward_interaction_object_validator
)

load_dotenv()

domain = os.getenv('DOMAIN')
admin_id = int(os.getenv('ADMIN_ID'))
developer_id = int(os.getenv('DEVELOPER_ID'))


def get_all_active_requests():
    status = 'active'
    request = requests.get(f'{domain}v1/request-admin/?ordering=creation_date&search={status}')

    return parse_json(request.text)


def admin_access(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != admin_id and user_id != developer_id:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='Доступ закрыт.',
            )
            return
        return func(update, context, *args, **kwargs)

    return wrapped


@admin_access
def start_command_admin(update: Update, context: CallbackContext):
    referrer = None
    role = 'Admin'
    if update.effective_chat.id == developer_id:
        role = 'Developer'
    data = {
        'username': update.effective_chat.username,
        'id': update.effective_chat.id,
        'referrer': referrer,
        'role': role
    }
    requests.post(f'{domain}v1/user/', json=data)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Добро пожаловать, {update.message.from_user.first_name}!'
    )
    admin_menu(update, context)


@admin_access
def admin_menu(update: Update, context: CallbackContext):
    context.chat_data['interaction_object'] = {}
    context.chat_data['active_requests'] = {}
    buttons = [
        [KeyboardButton('Открытые запросы')],
        [KeyboardButton('История запросов')],
        [KeyboardButton('Пользовательские вознаграждения')],
        [KeyboardButton('Вознаграждения персонала')],
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Выберите нужную операцию',
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@admin_access
def active_requests_information(update: Update, context: CallbackContext):
    context.chat_data['active_requests'] = {}
    context.chat_data['interaction_object'] = {}
    active_requests = get_all_active_requests()
    buttons = []
    for active_request in active_requests:
        context.chat_data['active_requests'][str(active_request['id'])] = active_request
        datetime_sri = get_current_time(active_request['creation_date'])
        buttons.append([KeyboardButton(
            f"№ {active_request['id']} | "
            f"id {active_request['owner']} "
            f"{datetime_sri} {active_request['city']} "
            f"{active_request['sold_currency_amount']} "
            f"{active_request['sold_currency'][:5]} "
            f"{active_request['purchased_currency_amount']} "
            f"| {active_request['currency_rate']}")]
        )
    buttons.append([KeyboardButton('Вернуться в меню')])
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Всего активных запросов {len(active_requests)}',
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@admin_access
def active_requests_handler(update: Update, context: CallbackContext):
    message = update.effective_message.text.split()
    context.chat_data['interaction_object']['request_id'] = message[1]
    context.chat_data['interaction_object']['user_id'] = message[4]
    buttons = [
        [KeyboardButton('Чат с клиентом')],
        [KeyboardButton('Canceled')],
        [KeyboardButton('Completed')],
        [KeyboardButton('История клиента')],
        [KeyboardButton('Забанить пользователя')],
        [KeyboardButton('Вернуться в меню')],
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Выберите действие',
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@admin_access
def change_status_handler(update: Update, context: CallbackContext):
    if not chat_data_validator(context):
        return admin_menu(update, context)

    if not request_interaction_object_validator(context):
        return admin_menu(update, context)

    status = update.effective_message.text
    data = {
        'status': status
    }
    request_id = context.chat_data['interaction_object']['request_id']
    requests.patch(f"{domain}v1/request-admin/{request_id}/", data=data)
    if status == 'Completed' and context.chat_data['active_requests'][request_id]['status'] == 'Active':
        user = requests.get(f"{domain}v1/user-admin/{context.chat_data['active_requests'][request_id]['owner']}/")
        commission = float(context.chat_data['active_requests'][request_id]['commission_fee'])
        referrer_fee = 0
        referrer = parse_json(user.text)['referrer']
        if referrer is not None:
            referrer_fee = REFERRER_PERCENT * commission

            referrer_data = {
                'fee': referrer_fee
            }
            requests.patch(f"{domain}v1/user-admin/{referrer}/", data=referrer_data)

        developer_fee = DEVELOPER_PERCENT * commission
        admin_fee = commission - (referrer_fee + developer_fee)
        developer_data = {
            'fee': developer_fee
        }
        requests.patch(f"{domain}v1/user-admin/{developer_id}/", data=developer_data)

        admin_data = {
            'fee': admin_fee
        }
        requests.patch(f"{domain}v1/user-admin/{admin_id}/", data=admin_data)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Статус запроса №{request_id} изменен на "Completed". Вознаграждения начислены.'
        )
    if status == 'Canceled':
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Статус запроса №{request_id} изменен на "Canceled". Вознаграждения не начисляются.'
        )
    admin_menu(update, context)


@admin_access
def user_add_to_ban(update: Update, context: CallbackContext):
    if not chat_data_validator(context):
        return admin_menu(update, context)

    if not request_interaction_object_validator(context):
        return admin_menu(update, context)

    user_id = int(context.chat_data['interaction_object']['user_id'])
    user_data = {
        'role': 'Banned'
    }
    user_ban = requests.patch(f'{domain}v1/user-admin/{user_id}/', data=user_data)
    if user_ban:
        get_ban_list()
        active_requests = get_all_active_requests()
        data = {
            'status': 'Canceled'
        }
        for active_request in active_requests:
            if active_request['owner'] == user_id:
                request_id = active_request['id']
                requests.patch(f'{domain}v1/request-admin/{request_id}/', data=data)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f'Пользователь с id {user_id} добавлен в бан. Все его активные запросы отменены.'
        )
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Произошла ошибка. Попробуйте позже или сообщите разработчику.',
        )

    admin_menu(update, context)


@admin_access
def requests_history_handler(update: Update, context: CallbackContext):
    requests_history = parse_json(requests.get(f'{domain}v1/request-admin/?ordering=-creation_date').text)
    message = 'История обменов:\n\n'
    len_history = len(requests_history)
    if len(requests_history) > LAST_REQUESTS:
        len_history = LAST_REQUESTS
    for index in range(len_history):
        request_history = requests_history[index]
        datetime_sri = get_current_time(request_history['creation_date'])
        message += (
            f"{index + 1}. {datetime_sri}. Клиент: {request_history['owner']}. "
            f"Текущий статус: {request_history['status']}. "
            f"{request_history['sold_currency_amount']} "
            f"{request_history['sold_currency']}. "
            f"Курс: {request_history['currency_rate']}. "
            f"{request_history['purchased_currency_amount']} Рупий. "
            f"Локация: {request_history['city']}\n\n"
        )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message
    )

    admin_menu(update, context)


@admin_access
def rewards_handler(update: Update, context: CallbackContext):
    users_with_unpaid_fee = []
    if update.message.text == 'Пользовательские вознаграждения':
        users_with_unpaid_fee = parse_json(
            requests.get(f'{domain}v1/user-admin/?search=user&ordering=-fee').text
        )
    elif update.message.text == 'Вознаграждения персонала':
        users_with_unpaid_fee = parse_json(
            requests.get(f'{domain}v1/user-admin/?search=admin&ordering=-fee').text
        )
        users_with_unpaid_fee += parse_json(
            requests.get(f'{domain}v1/user-admin/?search=developer&ordering=-fee').text
        )
    buttons = []
    for user in users_with_unpaid_fee:
        buttons.append([KeyboardButton(
            f"id: {user['id']} | Пользователь: {user['username']} |"
            f" Роль: {user['role']}. Невыплачено: {user['fee']} |"
            f" Выплачено: {user['paid_fee']}."
        )])
    buttons.append([KeyboardButton('Вернуться в меню')])
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Выберите, кому было выплачено вознаграждение.',
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@admin_access
def payment_confirmation(update: Update, context: CallbackContext):
    information = update.effective_message.text.split()
    context.chat_data['interaction_object']['user_id'] = information[1]
    context.chat_data['interaction_object']['payment'] = float(information[9])
    buttons = [
        [KeyboardButton('Вознаграждение выплачено')],
        [KeyboardButton('Вернуться в меню')],
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Проверьте информаницию по данной выплате повторно. К выплате {information[9]} USDT',
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@admin_access
def remuneration_fee(update: Update, context: CallbackContext):
    if not chat_data_validator(context):
        return admin_menu(update, context)

    if not reward_interaction_object_validator(context):
        return admin_menu(update, context)

    user_id = context.chat_data['interaction_object']['user_id']
    payment = context.chat_data['interaction_object']['payment']
    data = {
        'paid_fee': payment
    }
    user_payment = requests.patch(f'{domain}v1/user-admin/{user_id}/', data=data)
    if user_payment:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Вознаграждение отмечено как выплаченное.',
        )
        context.bot.send_message(
            chat_id=user_id,
            text=f'Вам выплатили вознаграждение в размере {payment} USDT',
        )
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Произошла ошибка. Попробуйте позже или сообщите разработчику.',
        )

    admin_menu(update, context)


@admin_access
def chat_with_user(update: Update, context: CallbackContext):
    if not chat_data_validator(context):
        return admin_menu(update, context)

    if not request_interaction_object_validator(context):
        return admin_menu(update, context)

    user_id = context.chat_data['interaction_object']['user_id']
    user = parse_json(requests.get(f'{domain}v1/user-admin/{user_id}/').text)
    url = create_deep_linked_url(user['username'])
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=url,
    )

    admin_menu(update, context)


@admin_access
def user_history(update: Update, context: CallbackContext):
    if not chat_data_validator(context):
        return admin_menu(update, context)

    if not request_interaction_object_validator(context):
        return admin_menu(update, context)

    user_id = context.chat_data['interaction_object']['user_id']
    user_requests = parse_json(requests.get(
        f'{domain}v1/{user_id}/request-user/?ordering=-creation_date'
    ).text)
    message = 'Все запросы пользователя:\n\n'
    for user_request in user_requests:
        date = get_current_time(user_request["creation_date"])
        message += (
            f'id: {user_request["id"]}. Дата: {date} Статус: '
            f'{user_request["status"]}. Локация: {user_request["city"]}.'
            f' Продано: {user_request["sold_currency_amount"]}'
            f' {user_request["sold_currency"]}. Получено: '
            f'{user_request["purchased_currency_amount"]} Рупий.'
            f' Курс: {user_request["currency_rate"]}\n\n'
        )
    user = parse_json(requests.get(
        f'{domain}v1/user-admin/{user_id}/'
    ).text)
    message += (
        f"Баланс невыплаченного вознаграждения: {user['fee']} USDT"
        f"\nБаланс невыплаченного вознаграждения: {user['paid_fee']} USDT"
    )

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
    )

    admin_menu(update, context)
