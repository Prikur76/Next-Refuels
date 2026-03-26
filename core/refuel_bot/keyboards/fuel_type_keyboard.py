# core/refuel_bot/keyboards/fuel_type_keyboard.py
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)


class FuelTypeKeyboard:
    def get(self):
        keyboard = [
            ["Бензин", "Дизель"],
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
                    "Бензин", callback_data="fuel_type:GASOLINE"
                ),
                InlineKeyboardButton(
                    "Дизель", callback_data="fuel_type:DIESEL"
                ),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)
