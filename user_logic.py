import os
from functools import wraps

from dotenv import load_dotenv
import requests
import pyqrcode
from datetime import datetime
from io import BytesIO

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import CallbackContext
from telegram.utils.helpers import create_deep_linked_url

from binance_api_request import binance_request_main
from constants import MAX_USDT, MIN_USDT, MAX_RUBLES, MIN_RUBLES
from utilities import parse_json, ban, exchange_request_dictionary_validator

load_dotenv()

domain = os.getenv('DOMAIN')
admin_id = int(os.getenv('ADMIN_ID'))
developer_id = int(os.getenv('DEVELOPER_ID'))


def user_access(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id == admin_id or user_id == developer_id:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text='Доступ закрыт.',
            )
            return
        return func(update, context, *args, **kwargs)
    return wrapped


@ban
@user_access
def main_menu(update: Update, context: CallbackContext):
    context.chat_data[update.effective_chat.id] = {}
    buttons = [
        [KeyboardButton('Обмен')],
        [KeyboardButton('Пригласить друга')],
        [KeyboardButton('Рефералы')],
        [KeyboardButton('История операций')],
    ]
    message = (
        f'Обмен от 20.000 Рублей или 300 USDT на Рупии.\n\n'
        f'Можно получать вознаграждения по реферальной программе, подробнее во вкладке "Рефералы"\n\n'
        f'Одновременно может существовать не более трех запросов на обмен.\n\n'
        f'После создания запроса с Вами свяжется оператор. \n\n'
        f'Работаем в населенных пунктах:\n'
        f'1. Матара\n2. Велигама\n3. Мирисса\n4. Ахангама\n\n'
        f'По всем вопросам https://t.me/HeliosFinTech'
    )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@ban
@user_access
def start_command_user(update: Update, context: CallbackContext):
    referrer = None
    if len(context.args) != 0:
        referrer_candidate = context.args[0]
        if update.effective_chat.id != referrer_candidate:
            referrer = referrer_candidate
    data = {
        'username': update.effective_chat.username,
        'id': update.effective_chat.id,
        'referrer': referrer,
    }
    new_user = requests.post(f'{domain}v1/user/', json=data)

    if new_user and referrer is not None:
        context.bot.send_message(
            chat_id=referrer,
            text=(
                'Вас указали в качестве реферера. За каждый завершенный'
                ' обмен рефералом Вам будет начислено вознаграждение.'
                ' Подробнее во вкладке "Рефералы".'
            )
        )
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f'Добро пожаловать, {update.message.from_user.first_name}!'
    )

    main_menu(update, context)


@ban
@user_access
def location_handler(update: Update, context: CallbackContext):
    user_chat_id = update.effective_chat.id
    request = requests.get(f'{domain}v1/{user_chat_id}/request-user/?search=active')
    if len(parse_json(request.text)) >= 3:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Не может быть более трех активных запросов. Дождитесь ответа оператора.',
        )
        return main_menu(update, context)
    location_buttons = [
        [KeyboardButton('Матара')],
        [KeyboardButton('Велигама')],
        [KeyboardButton('Мирисса')],
        [KeyboardButton('Ахангама')],
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Выберите удобную локацию',
        reply_markup=ReplyKeyboardMarkup(location_buttons, resize_keyboard=True)
    )


@ban
@user_access
def currency_handler(update: Update, context: CallbackContext):
    context.chat_data[update.effective_chat.id] = {}
    context.chat_data[update.effective_chat.id]['city'] = update.message.text
    currency_buttons = [
        [KeyboardButton('Рубли переводом')],
        [KeyboardButton('USDT Tether')],
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Выберите продаваемую валюту',
        reply_markup=ReplyKeyboardMarkup(currency_buttons, resize_keyboard=True)
    )


@ban
@user_access
def calculation_method_handler(update: Update, context: CallbackContext):
    if not exchange_request_dictionary_validator(update, context, 'city'):
        return main_menu(update, context)

    context.chat_data[update.effective_chat.id]['sold_currency'] = update.message.text
    menu_button = [
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Введите сумму обмена. Значение должно быть целым',
        reply_markup=ReplyKeyboardMarkup(menu_button, resize_keyboard=True)
    )


@ban
@user_access
def exchange_information_handler(update: Update, context: CallbackContext):
    if not exchange_request_dictionary_validator(update, context, 'sold_currency'):
        return main_menu(update, context)

    exchange_amount = int(update.message.text)
    currency_type = context.chat_data[update.effective_chat.id]['sold_currency']

    if (
            (currency_type == 'USDT Tether' and not MAX_USDT >= exchange_amount >= MIN_USDT)
            or (currency_type == 'Рубли переводом' and not MAX_RUBLES >= exchange_amount >= MIN_RUBLES)
    ):
        update.message.reply_text(text='Некорректная сумма.')
        return main_menu(update, context)

    context.chat_data[update.effective_chat.id]['sold_currency_amount'] = exchange_amount
    sold_currency_amount = context.chat_data[update.effective_chat.id]['sold_currency_amount']
    binance_response = binance_request_main(currency_type, sold_currency_amount)
    context.chat_data[update.effective_chat.id]['purchased_currency_amount'] = binance_response[0]
    context.chat_data[update.effective_chat.id]['sold_currency_amount'] = binance_response[1]
    context.chat_data[update.effective_chat.id]['currency_rate'] = binance_response[2]
    context.chat_data[update.effective_chat.id]['commission_fee'] = binance_response[3]
    purchased_currency_amount = context.chat_data[update.effective_chat.id]['purchased_currency_amount']
    sold_currency_amount = context.chat_data[update.effective_chat.id]['sold_currency_amount']
    exchange_information = (
        f"Локация: {context.chat_data[update.effective_chat.id]['city']}\n"
        f"Курс: {context.chat_data[update.effective_chat.id]['currency_rate']}\n\n"
        f"Для удобства Вам предложено два варианта обмена:\n\n"
        f"Вариант №1:\n"
        f"Сумма: {sold_currency_amount[0]}"
        f" ({currency_type})\n"
        f"Сумма к получению: {purchased_currency_amount[0]}\n\n"
        f"Вариант №2:\n"
        f"Сумма: {sold_currency_amount[1]}"
        f" ({currency_type})\n"
        f"Сумма к получению: {purchased_currency_amount[1]}"
    )
    exchange_buttons = [
        [KeyboardButton('Создать запрос №1')],
        [KeyboardButton('Создать запрос №2')],
        [KeyboardButton('Отменить запрос')],
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=exchange_information,
        reply_markup=ReplyKeyboardMarkup(exchange_buttons, resize_keyboard=True)
    )


@ban
@user_access
def operations_history(update: Update, context: CallbackContext):
    user_chat_id = update.effective_chat.id
    request = requests.get(f'{domain}v1/{user_chat_id}/request-user/?ordering=-creation_date')
    exchange_requests = parse_json(request.text)
    message = 'История последних пяти операций:\n\n'
    for exchange_request in exchange_requests:
        date = datetime.strptime(
            exchange_request['creation_date'], "%Y-%m-%dT%H:%M:%S.%f%z"
        ).date()
        message += (
            f"{date}\nСтатус: {exchange_request['status']}\nГород: {exchange_request['city']}\n"
            f"Продано: {exchange_request['sold_currency_amount']} {exchange_request['sold_currency']}\n"
            f"Куплено: {exchange_request['purchased_currency_amount']} Рупий.\n"
            f"Курс: {exchange_request['currency_rate']}\n\n"
        )
    menu_button = [
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        reply_markup=ReplyKeyboardMarkup(menu_button, resize_keyboard=True)
    )


@ban
@user_access
def exchange_cancellation(update: Update, context: CallbackContext):
    if not exchange_request_dictionary_validator(update, context, 'sold_currency_amount'):
        return main_menu(update, context)

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Запрос отменен',
    )
    main_menu(update, context)


@ban
@user_access
def exchange_creation(update: Update, context: CallbackContext):
    if not exchange_request_dictionary_validator(update, context, 'sold_currency_amount'):
        return main_menu(update, context)
    user_chat_id = update.effective_chat.id

    user = parse_json(requests.get(f'{domain}v1/user/{user_chat_id}/').text)
    if update.effective_chat.username != user['username']:
        data = {
            'username': update.effective_chat.username,
        }
        requests.patch(f'{domain}v1/user/{user_chat_id}/', data=data)

    if update.message.text == 'Создать запрос №1':
        context.chat_data[user_chat_id]['sold_currency_amount'] = (
            context.chat_data[user_chat_id]['sold_currency_amount'][0]
        )
        context.chat_data[user_chat_id]['purchased_currency_amount'] = (
            context.chat_data[user_chat_id]['purchased_currency_amount'][0]
        )
    elif update.message.text == 'Создать запрос №2':
        context.chat_data[user_chat_id]['sold_currency_amount'] = (
            context.chat_data[user_chat_id]['sold_currency_amount'][1]
        )
        context.chat_data[user_chat_id]['purchased_currency_amount'] = (
            context.chat_data[user_chat_id]['purchased_currency_amount'][1]
        )
    exchange_data = context.chat_data[user_chat_id]
    exchange_request = requests.post(
        f'{domain}v1/{user_chat_id}/request-user/',
        json=exchange_data
    )
    if exchange_request:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Запрос успешно создан, в ближайшее время с Вами свяжется оператор. ',
        )
    else:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Произошла ошибка, создайте запрос заново',
        )
    main_menu(update, context)


@ban
@user_access
def referrer_information(update: Update, context: CallbackContext):
    user_chat_id = update.effective_chat.id
    request_referrals = requests.get(f'{domain}v1/user/?search={user_chat_id}')
    referrals = parse_json(request_referrals.text)
    message = (
        f'За каждый обмен средств приглашенным пользователем Вам будет начисляться '
        f'вознаграждение. Реферальная ссылка работает только для новых пользователей\n\n'
        f'Ваши рефералы:\n'
    )
    if len(referrals) == 0:
        message = 'По вашей ссылке нет приглашенных пользователей.\n'
    else:
        for i in range(len(referrals)):
            message += f"{i + 1}. {referrals[i]['username']}\n"
    request_user = requests.get(f'{domain}v1/user/{user_chat_id}')
    user = parse_json(request_user.text)
    message += (
        f"\nБаланс невыплаченного вознаграждения: {user['fee']} USDT"
        f"\nБаланс невыплаченного вознаграждения: {user['paid_fee']} USDT"
    )
    buttons = [
        [KeyboardButton('Пригласить друга')],
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    )


@ban
@user_access
def invitation_method(update: Update, context: CallbackContext):
    invite_buttons = [
        [KeyboardButton('Сгенерировать QR-код')],
        [KeyboardButton('Сгенерировать ссылку')],
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Выберите метод приглашения',
        reply_markup=ReplyKeyboardMarkup(invite_buttons, resize_keyboard=True)
    )


@ban
@user_access
def invitation_handler(update: Update, context: CallbackContext):
    user_chat_id = update.effective_chat.id
    url = create_deep_linked_url(context.bot.get_me().username, str(user_chat_id))
    message = ''
    if update.message.text == 'Сгенерировать QR-код':
        qr_code_obj = pyqrcode.create(url)
        buffer = BytesIO()
        qr_code_obj.png(buffer, scale=5)
        context.bot.send_photo(
            chat_id=user_chat_id,
            photo=buffer.getvalue(),
        )
        message = 'QR-код сгенерирован'

    elif update.message.text == 'Сгенерировать ссылку':
        message = (
            f'Поделитесь этой ссылкой со своими друзьями.\n{url}\n'
            f'За каждый обмен средств Вашим другом, вы будете получать вознаграждение. '
            f'Размер текущего вознаграждения можно посмотреть во вкладке "Рефералы".'
        )

    menu_button = [
        [KeyboardButton('Вернуться в главное меню')]
    ]
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        reply_markup=ReplyKeyboardMarkup(menu_button, resize_keyboard=True)
    )
