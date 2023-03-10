import os

from dotenv import load_dotenv

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from admin_logic import (
    start_command_admin, active_requests_information,
    requests_history_handler, active_requests_handler,
    change_status_handler, user_add_to_ban, admin_menu,
    rewards_handler, payment_confirmation, remuneration_fee,
    chat_with_user, user_history
)
from user_logic import (
    start_command_user, main_menu, location_handler, exchange_cancellation,
    operations_history, referrer_information, invitation_method,
    invitation_handler, exchange_creation, currency_handler,
    calculation_method_handler, exchange_information_handler
)


load_dotenv()

secret_token = os.getenv('TELEGRAM_TOKEN')
admin_id = int(os.getenv('ADMIN_ID'))
developer_id = int(os.getenv('DEVELOPER_ID'))
staff_access = [admin_id, developer_id]

updater = Updater(token=secret_token)
dispatcher = updater.dispatcher


def main():
    dispatcher.add_handler(CommandHandler(
        'start', start_command_admin, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Открытые запросы'), active_requests_information,
        Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('История запросов'), requests_history_handler,
        Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex(
            r'^№ \d+ \| id \d+ \d{2}.\d{2}.\d{4} \d{2}'
            r':\d{2} \D+\d+.\d{2}\D+\d+ \| \d+.\d{2}$'
        ),
        active_requests_handler, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex(
            r'^id: \d+ \| Пользователь: \w+ \| Роль: \w+. '
            r'Невыплачено: \d+.\d{2} \| Выплачено: \d+.\d{2}.$'
        ),
        payment_confirmation, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Canceled') |
        Filters.regex('Completed'),
        change_status_handler, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Вернуться в меню'),
        admin_menu, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Забанить пользователя'),
        user_add_to_ban, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Вознаграждение выплачено'),
        remuneration_fee, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Чат с клиентом'),
        chat_with_user, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('История клиента'),
        user_history, Filters.user(user_id=staff_access))
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Пользовательские вознаграждения') |
        Filters.regex('Вознаграждения персонала'),
        rewards_handler, Filters.user(user_id=staff_access))
    )

    dispatcher.add_handler(CommandHandler(
        'start', start_command_user)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Вернуться в главное меню'), main_menu)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Обмен'), location_handler)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Отменить запрос'), exchange_cancellation)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('История операций'), operations_history)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Рефералы'), referrer_information)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Пригласить друга'), invitation_method)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Сгенерировать QR-код') |
        Filters.regex('Сгенерировать ссылку'), invitation_handler)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Создать запрос №1') |
        Filters.regex('Создать запрос №2'), exchange_creation)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Матара') | Filters.regex('Велигама') |
        Filters.regex('Мирисса') | Filters.regex('Ахангама'),
        currency_handler)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex('Рубли переводом') |
        Filters.regex('USDT Tether'), calculation_method_handler)
    )
    dispatcher.add_handler(MessageHandler(
        Filters.regex(r'^[0-9]*$'), exchange_information_handler)
    )

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
