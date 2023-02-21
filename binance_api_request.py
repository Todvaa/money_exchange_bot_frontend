import json
import requests

from constants import COMMISSION_PERCENTAGE, BANKNOTE_DENOMINATION


def get_headers():
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Length": "123",
        "content-type": "application/json",
        "Host": "p2p.binance.com",
        "Origin": "https://p2p.binance.com",
        "Pragma": "no-cache",
        "TE": "Trailers",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0"
    }

    return headers


def get_data(bank, sold_exchange_amount, fiat, trade_type, rows):
    data = {
            "asset": "USDT",
            "fiat": fiat,
            "merchantCheck": True,
            "page": 1,
            "payTypes": [bank],
            "publisherType": None,
            "rows": rows,
            "tradeType": trade_type,
            "transAmount":  f"{sold_exchange_amount}"
        }

    return data


def average_rate(request):
    json_object = json.loads(request.text)

    prices = []
    for agent in json_object['data']:
        prices.append(float(agent['adv']['price']))

    return sum(prices) / len(prices)


def commission_calculation(amount_usdt):
    return COMMISSION_PERCENTAGE * amount_usdt


def exchange_options_calculation(result_rupee, result_rate, commission):
    result_rupee_1 = result_rupee // BANKNOTE_DENOMINATION * BANKNOTE_DENOMINATION
    sold_exchange_amount_1 = result_rupee_1 / result_rate

    result_rupee_2 = (result_rupee // BANKNOTE_DENOMINATION + 1) * BANKNOTE_DENOMINATION
    sold_exchange_amount_2 = result_rupee_2 / result_rate

    return [
        [result_rupee_1, result_rupee_2],
        [round(sold_exchange_amount_1, 2), round(sold_exchange_amount_2, 2)],
        round(result_rate, 2), round(commission, 2)
    ]


def request_sell_usdt(amount_usdt):
    bank = "BANK"
    fiat = "LKR"
    trade_type = "SELL"
    rows = 20
    data = get_data(
        bank=bank,
        sold_exchange_amount="",
        fiat=fiat,
        trade_type=trade_type,
        rows=rows
    )
    r = requests.post(
        'https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search',
        headers=get_headers(), json=data
    )

    average_rate_rupee = average_rate(request=r)
    commission = commission_calculation(amount_usdt)
    amount_rupee = (amount_usdt - commission) * average_rate_rupee

    return amount_rupee, commission


def exchange_rate_calculation_rubles(sold_exchange_amount):
    bank = "TinkoffNew"
    fiat = "RUB"
    trade_type = "BUY"
    rows = 8
    data = get_data(
        bank=bank,
        sold_exchange_amount=sold_exchange_amount,
        fiat=fiat,
        trade_type=trade_type,
        rows=rows
    )
    r = requests.post(
        'https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search',
        headers=get_headers(), json=data
    )

    average_rate_rubles = average_rate(request=r)
    amount_usdt = sold_exchange_amount / average_rate_rubles

    result_rupee, commission = request_sell_usdt(amount_usdt)
    result_rate = result_rupee / sold_exchange_amount

    return exchange_options_calculation(result_rupee, result_rate, commission)


def exchange_rate_calculation_usdt(sold_exchange_amount):
    result_rupee, commission = request_sell_usdt(sold_exchange_amount)
    result_rate = result_rupee / sold_exchange_amount

    return exchange_options_calculation(result_rupee, result_rate, commission)


def binance_request_main(currency_type, sold_exchange_amount):
    if currency_type == 'Рубли переводом':

        return exchange_rate_calculation_rubles(sold_exchange_amount)

    if currency_type == 'USDT Tether':

        return exchange_rate_calculation_usdt(sold_exchange_amount)
