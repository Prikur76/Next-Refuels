# core/bot/keyboards/refuel_method_keyboard.py
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)


class RefuelMethodKeyboard:
    def get(self):
        keyboard = [
            ["ТГ-бот", "Карта"],
            ["Топливозаправщик"],
            ["🔙 Назад", "❌ Отмена"],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    def get_inline(self):
        keyboard = [
            [
                InlineKeyboardButton(
                    "ТГ-бот", callback_data="refuel_method:tg_bot"
                ),
                InlineKeyboardButton(
                    "Карта", callback_data="refuel_method:fuel_card"
                ),
            ],
            [
                InlineKeyboardButton(
                    "Топливозаправщик", callback_data="refuel_method:truck"
                )
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
