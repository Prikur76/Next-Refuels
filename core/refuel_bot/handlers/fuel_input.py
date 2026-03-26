# core/bot/handlers/fuel_input.py
import logging
from decimal import Decimal, InvalidOperation
from warnings import filterwarnings

from asgiref.sync import sync_to_async
from django.utils import timezone as dj_tz
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.warnings import PTBUserWarning

from core.models import Car, FuelRecord
from core.refuel_bot.keyboards.cancel_keyboard import CancelKeyboard
from core.refuel_bot.keyboards.fuel_type_keyboard import FuelTypeKeyboard
from core.refuel_bot.keyboards.main_keyboard import MainKeyboard
from core.refuel_bot.keyboards.refuel_method_keyboard import (
    RefuelMethodKeyboard,
)
from core.refuel_bot.utils.validate_state_plate import (
    is_valid_plate,
    normalize_plate_input,
)
from core.services.fuel_service import FuelCreatePayload, FuelService

# Игнорируем предупреждения PTB о коллизиях callback
filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)

logger = logging.getLogger(__name__)

# States
WAITING_CAR, WAITING_LITERS, WAITING_REFUEL_METHOD, WAITING_FUEL_TYPE = range(
    4
)
# Экземпляры клавиатур
cancel_kb = CancelKeyboard()
refuel_kb = RefuelMethodKeyboard()
fuel_type_kb = FuelTypeKeyboard()
main_kb = MainKeyboard()


# --- DB helpers ---
@sync_to_async
def find_car_by_state_number(state_number: str):
    return Car.objects.filter(
        state_number__iexact=state_number, is_active=True
    ).first()


@sync_to_async
def get_car_by_id(cid: int):
    return Car.objects.filter(id=cid).first()


@sync_to_async
def create_fuel_record(
    *,
    car_id: int,
    user_id: int,
    liters: Decimal,
    fuel_type: str,
    source: str,
    filled_at,
    notes: str = "",
):
    """Создаёт запись через общий сервисный слой."""
    return FuelService.create_fuel_record(
        FuelCreatePayload(
            car_id=car_id,
            user_id=user_id,
            liters=liters,
            fuel_type=fuel_type,
            source=source,
            filled_at=filled_at,
            notes=notes,
        )
    )


def user_has_input_access(user) -> bool:
    if not user:
        return False
    return bool(
        user.has_group("Заправщик")
        or user.has_group("Менеджер")
        or user.has_group("Администратор")
    )


# Helper for state stack ("Back" functionality)
def push_state(context: ContextTypes.DEFAULT_TYPE, state):
    stack = context.user_data.setdefault("_state_stack", [])
    stack.append(state)


def pop_state(context: ContextTypes.DEFAULT_TYPE):
    stack = context.user_data.get("_state_stack", [])
    if stack:
        stack.pop()
    if stack:
        return stack.pop()
    return None


# --- Удаление сообщений ---
async def delete_last_bot_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    mid = context.user_data.pop("last_bot_mid", None)
    if not mid:
        return
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id, message_id=mid
        )
    except Exception:
        pass  # Сообщение уже удалено или недоступно


async def try_delete_user_message(update: Update):
    try:
        if update and update.message:
            await update.message.delete()
    except Exception:
        pass  # В личных чатах бот не может удалять сообщения пользователей


def remember_bot_message(context: ContextTypes.DEFAULT_TYPE, msg):
    if msg:
        context.user_data["last_bot_mid"] = msg.message_id


# --- Handlers ---


async def start_fuel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    if not user:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["_state_stack"] = []
    push_state(context, "ENTRY")

    msg = await update.message.reply_text(
        "🚗 Отлично! Введите госномер автомобиля (например: A123BC77):",
        reply_markup=cancel_kb.get(),
    )
    remember_bot_message(context, msg)
    return WAITING_CAR


async def quick_start_from_plate(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Быстрый старт диалога по госномеру из главного меню."""
    user = getattr(context, "user", None)
    if not user:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return ConversationHandler.END

    if not update.effective_message or not update.effective_message.text:
        return ConversationHandler.END

    raw_text = update.effective_message.text or ""
    plate = normalize_plate_input(raw_text)

    if not is_valid_plate(plate):
        msg = await update.message.reply_text(
            "Похоже на госномер, но формат неверный.\n"
            "Нажмите «⛽ Добавить» или введите номер в формате А123ВС77.",
            reply_markup=await main_kb.get_for_user(user),
        )
        remember_bot_message(context, msg)
        return ConversationHandler.END

    car = await find_car_by_state_number(plate)
    if not car:
        msg = await update.message.reply_text(
            "Автомобиль не найден. Нажмите «⛽ Добавить» и попробуйте снова.",
            reply_markup=await main_kb.get_for_user(user),
        )
        remember_bot_message(context, msg)
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["_state_stack"] = []
    push_state(context, "ENTRY")
    context.user_data["car_id"] = car.id
    context.user_data["car_display"] = (
        f"{car.model or '—'} ({car.state_number})"
    )
    push_state(context, WAITING_CAR)

    msg = await update.message.reply_text(
        (
            f"Автомобиль найден: {context.user_data['car_display']}\n\n"
            "Введите количество литров (например: 45.5):"
        ),
        reply_markup=cancel_kb.get(),
    )
    remember_bot_message(context, msg)
    return WAITING_LITERS


async def process_car_number(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not update.effective_message or not update.effective_message.text:
        return ConversationHandler.END
    raw_text = update.effective_message.text or ""
    plate = normalize_plate_input(raw_text)

    if not is_valid_plate(plate):
        msg = await update.message.reply_text(
            "Неверный формат госномера.\n"
            "Допустимые примеры: АА12345, А123ВС45, А123ВС456.\n"
            "Используйте только кирилицу и цифры.",
            reply_markup=cancel_kb.get(),
        )
        remember_bot_message(context, msg)
        return WAITING_CAR

    car = await find_car_by_state_number(plate)
    if not car:
        msg = await update.message.reply_text(
            "Автомобиль с таким госномером не найден или не активен. Попробуйте ещё раз:",
            reply_markup=cancel_kb.get(),
        )
        remember_bot_message(context, msg)
        return WAITING_CAR

    context.user_data["car_id"] = car.id
    context.user_data["car_display"] = (
        f"{car.model or '—'} ({car.state_number})"
    )
    push_state(context, WAITING_CAR)

    msg = await update.message.reply_text(
        f"Автомобиль найден: {context.user_data['car_display']}\n\nВведите количество литров (например: 45.5):",
        reply_markup=cancel_kb.get(),
    )
    remember_bot_message(context, msg)
    return WAITING_LITERS


async def process_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message or not update.effective_message.text:
        return ConversationHandler.END
    text = update.effective_message.text.replace(",", ".").strip()
    try:
        liters = Decimal(text)
        if liters <= 0 or liters > 330:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        msg = await update.message.reply_text(
            "Неверное количество. Введите число (0.1 — 330):",
            reply_markup=cancel_kb.get(),
        )
        remember_bot_message(context, msg)
        return WAITING_LITERS

    context.user_data["liters"] = liters
    push_state(context, WAITING_LITERS)

    msg = await update.message.reply_text(
        f"Вы указали {liters.quantize(Decimal('0.01'))} л. Выберите способ заправки:",
        reply_markup=refuel_kb.get(),
    )
    remember_bot_message(context, msg)
    return WAITING_REFUEL_METHOD


async def process_refuel_method(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    user = getattr(context, "user", None)
    if not user:
        await update.message.reply_text("⛔ Сессия истекла.")
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()
        data = query.data or ""
        is_cb = True
        logger.info(
            "Callback refuel_method received: user_id=%s data=%s",
            context.user_data.get("user_id"),
            data,
        )
    else:
        if not update.effective_message or not update.effective_message.text:
            return WAITING_REFUEL_METHOD
        data = update.effective_message.text.strip().lower()
        is_cb = False

    # ----- Отмена -----
    if (is_cb and data.endswith(":cancel")) or (
        not is_cb and data == "❌ отмена"
    ):
        if is_cb:
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await try_delete_user_message(update)
            await delete_last_bot_message(update, context)

        context.user_data.clear()
        await update.effective_chat.send_message(
            "Ввод отменён.", reply_markup=(await main_kb.get_for_user(user))
        )
        return ConversationHandler.END

    # ----- Назад -----
    if (is_cb and data.endswith(":back")) or (
        not is_cb and data == "🔙 назад"
    ):
        if is_cb:
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await try_delete_user_message(update)
            await delete_last_bot_message(update, context)

        prev = pop_state(context)
        if prev == WAITING_CAR:
            msg = await update.effective_chat.send_message(
                "Возврат к вводу госномера. Введите госномер:",
                reply_markup=cancel_kb.get(),
            )
            remember_bot_message(context, msg)
            return WAITING_CAR
        if prev == WAITING_LITERS:
            msg = await update.effective_chat.send_message(
                "Возврат к вводу литров. Введите количество литров:",
                reply_markup=cancel_kb.get(),
            )
            remember_bot_message(context, msg)
            return WAITING_LITERS

        await update.effective_chat.send_message(
            "Возвращаю в меню.",
            reply_markup=(await main_kb.get_for_user(user)),
        )
        return ConversationHandler.END

    # ----- Определение способа -----
    method_map = {
        "refuel_method:tg_bot": ("TGBOT", "Телеграм-бот"),
        "refuel_method:fuel_card": ("CARD", "Топливная карта"),
        "refuel_method:truck": ("TRUCK", "Топливозаправщик"),
    }

    if is_cb and data in method_map:
        method_key, method_name = method_map[data]
    elif not is_cb:
        if data in {"тг-бот", "через бота", "бот"}:
            method_key, method_name = "TGBOT", "Телеграм-бот"
        elif data in {"топливная карта", "карта"}:
            method_key, method_name = "CARD", "Топливная карта"
        elif data in {"топливозаправщик", "заправщик"}:
            method_key, method_name = "TRUCK", "Топливозаправщик"
        else:
            msg = await update.message.reply_text(
                "Выберите корректный способ.",
                reply_markup=refuel_kb.get(),
            )
            remember_bot_message(context, msg)
            return WAITING_REFUEL_METHOD
    else:
        msg = await update.message.reply_text(
            "Выберите способ заправки.", reply_markup=refuel_kb.get()
        )
        remember_bot_message(context, msg)
        return WAITING_REFUEL_METHOD

    # Сохраняем выбранный метод
    context.user_data["source"] = method_key
    context.user_data["source_name"] = method_name
    push_state(context, WAITING_REFUEL_METHOD)
    logger.info(
        "Refuel method selected: user_id=%s method=%s",
        context.user_data.get("user_id"),
        method_key,
    )

    # ----- УДАЛЯЕМ сообщение с выбором способа -----
    if is_cb:
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(
                "Не удалось удалить сообщение с выбором способа: %s", e
            )

    # Переход к выбору типа топлива
    msg = await update.effective_chat.send_message(
        "Выберите тип топлива:", reply_markup=fuel_type_kb.get()
    )
    remember_bot_message(context, msg)
    return WAITING_FUEL_TYPE


async def process_fuel_type(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not update.effective_message or not update.effective_message.text:
        return ConversationHandler.END
    user = getattr(context, "user", None)
    if not user:
        await update.message.reply_text("⛔ Сессия истекла.")
        return ConversationHandler.END

    query = update.callback_query
    if query:
        await query.answer()
        data = query.data or ""
        is_cb = True
        logger.info(
            "Callback fuel_type received: user_id=%s data=%s",
            context.user_data.get("user_id"),
            data,
        )
    else:
        data = (update.effective_message.text or "").strip().lower()
        is_cb = False

    # ----- Отмена -----
    if (is_cb and data.endswith(":cancel")) or (
        not is_cb and data == "❌ отмена"
    ):
        if is_cb:
            try:
                if query and query.message:
                    await query.message.delete()
            except Exception:
                pass
        else:
            await try_delete_user_message(update)
            await delete_last_bot_message(update, context)

        context.user_data.clear()
        await update.effective_chat.send_message(
            "Ввод отменён.", reply_markup=(await main_kb.get_for_user(user))
        )
        return ConversationHandler.END

    # ----- Назад -----
    if (is_cb and data.endswith(":back")) or (
        not is_cb and data == "🔙 назад"
    ):
        if is_cb:
            try:
                await query.message.delete()
            except Exception:
                pass
        else:
            await try_delete_user_message(update)
            await delete_last_bot_message(update, context)

        prev = pop_state(context)
        if prev == WAITING_CAR:
            msg = await update.effective_chat.send_message(
                "Возврат к вводу госномера. Введите госномер:",
                reply_markup=cancel_kb.get(),
            )
            remember_bot_message(context, msg)
            return WAITING_CAR
        if prev == WAITING_LITERS:
            msg = await update.effective_chat.send_message(
                "Возврат к вводу литров. Введите количество литров:",
                reply_markup=cancel_kb.get(),
            )
            remember_bot_message(context, msg)
            return WAITING_LITERS
        if prev == WAITING_REFUEL_METHOD:
            msg = await update.effective_chat.send_message(
                "Возврат к выбору способа заправки:",
                reply_markup=refuel_kb.get(),
            )
            remember_bot_message(context, msg)
            return WAITING_REFUEL_METHOD

        await update.effective_chat.send_message(
            "Возвращаю в меню.",
            reply_markup=(await main_kb.get_for_user(user)),
        )
        return ConversationHandler.END

    # ----- Выбор топлива -----
    FUEL_MAP = {
        "fuel_type:GASOLINE": ("GASOLINE", "Бензин"),
        "fuel_type:DIESEL": ("DIESEL", "Дизель"),
        "бензин": ("GASOLINE", "Бензин"),
        "дизель": ("DIESEL", "Дизель"),
    }

    if data not in FUEL_MAP:
        if is_cb:
            await query.edit_message_reply_markup(
                reply_markup=fuel_type_kb.get_inline()
            )
        else:
            msg = await update.message.reply_text(
                "Выберите тип топлива.", reply_markup=fuel_type_kb.get()
            )
            remember_bot_message(context, msg)
        return WAITING_FUEL_TYPE

    fuel_key, fuel_name = FUEL_MAP[data]
    context.user_data["fuel_type"] = fuel_key
    context.user_data["fuel_type_name"] = fuel_name
    logger.info(
        "Fuel type selected: user_id=%s fuel_type=%s",
        context.user_data.get("user_id"),
        fuel_key,
    )

    # ----- Проверка данных -----
    user_id = context.user_data.get("user_id")
    car_id = context.user_data.get("car_id")
    liters = context.user_data.get("liters")
    source = context.user_data.get("source")

    if not all([user_id, car_id, liters, source]):
        if is_cb:
            await query.edit_message_text("Ошибка данных — начните заново.")
        else:
            msg = await update.message.reply_text(
                "Ошибка данных — начните заново."
            )
            remember_bot_message(context, msg)
        context.user_data.clear()
        return ConversationHandler.END

    # ----- Создание записи -----
    try:
        await create_fuel_record(
            car_id=car_id,
            user_id=user_id,
            liters=liters,
            fuel_type=fuel_key,
            source=source,
            filled_at=dj_tz.now(),
            notes="",
        )
        logger.info(
            "Fuel record created from bot: user_id=%s car_id=%s liters=%s source=%s fuel_type=%s",
            user_id,
            car_id,
            liters,
            source,
            fuel_key,
        )
    except Exception:
        logger.exception("Ошибка при создании записи о заправке")
        if is_cb:
            await query.edit_message_text(
                "❌ Ошибка сохранения. Попробуйте позже."
            )
        else:
            await update.message.reply_text(
                "❌ Ошибка сохранения. Попробуйте позже."
            )
        return ConversationHandler.END

    local_dt = dj_tz.localtime(dj_tz.now())

    # ----- Ответ пользователю -----
    success_text = (
        f"✅ Заправка сохранена:\n"
        f"🚗 {context.user_data['car_display']}\n"
        f"⛽ {liters.quantize(Decimal('0.01'))} л, {fuel_name}\n"
        f"🔧 Способ: {context.user_data['source_name']}\n"
        f"📅 {local_dt.strftime('%d.%m.%Y %H:%M')}"
    )

    if is_cb:
        await query.edit_message_text(success_text)
    else:
        await update.message.reply_text(success_text)

    await update.effective_chat.send_message(
        "Возвращаю в меню.", reply_markup=(await main_kb.get_for_user(user))
    )

    context.user_data.clear()
    return ConversationHandler.END


# --- Обработчики "Отмена" и "Назад" ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    await try_delete_user_message(update)
    await delete_last_bot_message(update, context)
    context.user_data.clear()
    await update.effective_chat.send_message(
        "Операция отменена.", reply_markup=(await main_kb.get_for_user(user))
    )
    return ConversationHandler.END


async def back_from_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    await try_delete_user_message(update)
    await delete_last_bot_message(update, context)
    context.user_data.clear()
    await update.effective_chat.send_message(
        "Возвращаю в меню.", reply_markup=(await main_kb.get_for_user(user))
    )
    return ConversationHandler.END


async def back_from_liters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await try_delete_user_message(update)
    await delete_last_bot_message(update, context)
    msg = await update.effective_chat.send_message(
        "Возврат к вводу госномера. Введите госномер:",
        reply_markup=cancel_kb.get(),
    )
    remember_bot_message(context, msg)
    return WAITING_CAR


async def back_from_refuel_method(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Обработка кнопки 'Назад' при выборе типа топлива"""
    await try_delete_user_message(update)
    await delete_last_bot_message(update, context)

    msg = await update.effective_chat.send_message(
        "Возврат к выбору способа заправки:",
        reply_markup=refuel_kb.get(),
    )
    remember_bot_message(context, msg)
    return WAITING_REFUEL_METHOD


# --- Conversation Handler ---
fuel_conv_handler = ConversationHandler(
    entry_points=[
        MessageHandler(filters.Regex("^⛽ Добавить$"), start_fuel_input),
        MessageHandler(filters.TEXT & ~filters.COMMAND, quick_start_from_plate),
    ],
    states={
        WAITING_CAR: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.Regex("^🔙 Назад$"), back_from_car),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, process_car_number
            ),
        ],
        WAITING_LITERS: [
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
            MessageHandler(filters.Regex("^🔙 Назад$"), back_from_liters),
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_liters),
        ],
        WAITING_REFUEL_METHOD: [
            CallbackQueryHandler(
                process_refuel_method, pattern="^refuel_method:"
            ),
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, process_refuel_method
            ),
        ],
        WAITING_FUEL_TYPE: [
            CallbackQueryHandler(process_fuel_type, pattern="^fuel_type:"),
            MessageHandler(
                filters.Regex("^🔙 Назад$"), back_from_refuel_method
            ),
            MessageHandler(filters.TEXT & ~filters.COMMAND, process_fuel_type),
        ],
    },
    fallbacks=[
        MessageHandler(filters.Regex("^❌ Отмена$"), cancel),
        CallbackQueryHandler(cancel, pattern="^fuel_type:cancel"),
    ],
    per_user=True,
    per_chat=True,
    per_message=False,
    name="fuel_conversation",
)


# --- Команда /fuel ---
async def fuel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = getattr(context, "user", None)
    if not user:
        await update.effective_chat.send_message("⛔ Сессия истекла.")
        return ConversationHandler.END
    if not user_has_input_access(user):
        await update.message.reply_text("⛔ Доступ запрещён.")
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Использование: /fuel <госномер> <литры> <способ> [тип_топлива]\n"
            "Способы: tg-bot, card, truck\n"
            "Типы топлива: GASOLINE, DIESEL (по умолчанию: GASOLINE)"
        )
        return

    # Парсим аргументы
    state_plate = args[0]
    liters_text = args[1]
    method_raw = args[2].lower() if len(args) > 2 else "tg-bot"
    fuel_type_raw = args[3].upper() if len(args) > 3 else None

    # Валидация литров
    try:
        liters = FuelService.normalize_liters(liters_text)
    except ValueError:
        await update.message.reply_text("❌ Неверный формат литров.")
        return

    # Поиск автомобиля
    car = await find_car_by_state_number(state_plate)
    if not car:
        await update.message.reply_text("🚗 Автомобиль не найден.")
        return

    # Определение способа
    SOURCE_MAP = {
        "tg-bot": "TGBOT",
        "card": "CARD",
        "truck": "TRUCK",
    }
    source_key = SOURCE_MAP.get(method_raw)
    if not source_key:
        available = ", ".join(SOURCE_MAP.keys())
        await update.message.reply_text(
            f"❌ Неизвестный способ. Доступные: {available}"
        )
        return

    # Определение типа топлива
    valid_fuel_types = dict(FuelRecord.FuelType.choices)
    fuel_type = fuel_type_raw or "GASOLINE"
    if fuel_type not in valid_fuel_types:
        available = ", ".join(valid_fuel_types.keys())
        await update.message.reply_text(
            f"❌ Неверный тип топлива. Доступные: {available}"
        )
        return

    # Создание записи
    try:
        await create_fuel_record(
            car_id=car.id,
            user_id=user.id,
            liters=liters,
            fuel_type=fuel_type,
            source=source_key,
            filled_at=dj_tz.now(),
            notes="",
        )
    except Exception:
        logger.exception("Ошибка при создании записи через /fuel")
        await update.message.reply_text("❌ Ошибка сохранения.")
        return

    fuel_display = valid_fuel_types[fuel_type]
    await update.message.reply_text(
        f"✅ Заправка: {car.state_number} — {liters:.1f} л, {fuel_display}"
    )


fuel_command_handler = CommandHandler("fuel", fuel_command)
