import logging
from dataclasses import dataclass
from typing import Any

from aiogram import types, html, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.scene import Scene, on
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup
from aiogram.utils.formatting import as_list, as_section, Bold, as_numbered_list
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

logger = logging.getLogger(__name__)


@dataclass
class ExModel:
    title: str
    var_name: str
    description: str
    store_history: bool = False
    presets: list = None


@dataclass
class Preloads:
    pk: int
    data: str


QUESTIONS = [
    [
        ExModel(title='var 1', var_name='var1', description='Вопрос №1'),
        ExModel(title='var 2', var_name='var2', description='Вопрос №2', presets=["good", "bad"]),
        ExModel(title='var 3', var_name='var3', description='Вопрос №3'),
     ],
    [
        ExModel(title='var 1', var_name='var1', description='Вопрос №1'),
        ExModel(title='var 2', var_name='var2', description='Вопрос №2'),
    ],

]


def get_list_data_ikb(items: list = None, pref: str = '') -> InlineKeyboardMarkup:
    ikb = InlineKeyboardBuilder()
    if items:
        for item in items:
            ikb.button(text=f'{item.data:.255}{"..." if len(item.data) > 255 else ""}',
                       callback_data=f"{pref}_select_{item.pk}")
        ikb.button(text="🚫 Отменить", callback_data="cancel_soft")
    else:
        ikb.button(text="🚫 Нет записей", callback_data="cancel_soft")
    ikb.adjust(1)
    return ikb.as_markup()


def reply_std_kbd(step: int) -> InlineKeyboardMarkup:
    markup = ReplyKeyboardBuilder()
    if step > 0:
        markup.button(text="🔙 Back")
    markup.button(text="🚫 Exit")
    markup.button(text="ℹ️ Info")
    markup.button(text="➡️ Skip")
    return markup.adjust(2).as_markup(resize_keyboard=True)


class CommonInfoScene(Scene, state='coms'):

    def __init__(self, *args, **kwargs):
        self.greetings = "Введите основные данные."
        if kwargs['wizard'].scene_config.state != kwargs['wizard'].data['raw_state']:
            # если реальный вход, то создаём свойство класса 'init_data' для последующего возможного использования
            # и сохраняем в нём CallbackQuery.data
            self.init_data: str = kwargs['wizard'].event.data
            doc_type = int(self.init_data.removeprefix('menu_select_'))
        else:
            try:
                doc_type = int(list(kwargs['wizard'].state.storage.storage.values())[0].data.get(
                    'init_data').removeprefix('menu_select_'))
            except Exception as e:
                # обычно происходит когда пользователь вызывает сцену, когда уже активна другая сцена.
                logger.error(f"Пользователь %r вызвал некорректный тип данных инициализации сцены %r! %r",
                             kwargs['wizard'].data.get('event_from_user').id, self.__class__.__name__, e)
                raise
        self.work_data = QUESTIONS[doc_type-1]
        Scene.__init__(self, *args, **kwargs)

    async def show_presets_msg(self, chat_id, presets_data, bot, state):
        presets = []
        for number, data in enumerate(presets_data):
            presets.append(Preloads(pk=number, data=data))
        msg = await bot.send_message(chat_id, 'Выберете значение:',
                                     reply_markup=get_list_data_ikb(presets, 'coms'))
        await state.update_data(automsg=msg.message_id)

    async def define_msg(self, data) -> types.Message | None:
        if isinstance(data, types.Message):
            return data
        elif isinstance(data, types.CallbackQuery):
            await data.answer()
            return data.message
        else:
            logger.error('Невозможное событие! Переданные в функцию данные не удалось определить!')
            return None

    async def del_auto_msg(self, message: str, data: dict, bot: Bot, chat_id, msg_sig: str = 'automsg') -> dict:
        if msg_id := data.get(msg_sig, None):
            await bot.edit_message_text(message, chat_id=chat_id, message_id=msg_id, reply_markup=None)
            del data[msg_sig]
        return data

    @on.callback_query.enter()
    @on.message.enter()
    async def on_msg_enter(self, data, bot: Bot, state: FSMContext, step: int | None = 0) -> Any:
        message = await self.define_msg(data)

        try:
            quiz = self.work_data[step]
        except IndexError:
            # This error means that the question's list is over
            return await self.wizard.exit()

        await state.update_data(step=step)
        try:  # по факту является проверкой на реальный вход в сцену, а не на первый шаг
            await state.update_data(init_data=self.init_data)  # проверка на существование переменной 'init_data'
            await message.answer(self.greetings)
            await message.edit_reply_markup(reply_markup=None)
        except:
            pass  # если повторный вход в сцену (например через wizard.retake), ничего не делаем

        await message.answer(text=f"[{step+1}/{len(self.work_data)}] {quiz.description}",
                             reply_markup=reply_std_kbd(step),
                             )
        if quiz.presets:
            await self.show_presets_msg(message.chat.id, quiz.presets, bot, state)

    async def save_user_data(self, user_id, data, init_data):
        if data:
            return True
        else:
            return False

    async def exit_msg(self, msg: types.Message, state: FSMContext):
        await msg.answer('Спасибо за уделённое время!')

    @on.callback_query.exit()
    @on.message.exit()
    async def on_exit(self, data, bot: Bot, state: FSMContext) -> None:
        if message := await self.define_msg(data):
            user_id = data.from_user.id
            chat_id = message.chat.id
        else:
            return

        if not self.work_data:
            await message.answer('Заполнять ещё нечего. Шаги не определены!')
            await state.set_data({})
            return

        data_st = await state.get_data()

        answers = data_st.get("answers", {})
        user_answers, final_data, user_data = [], {}, {}
        for step, quiz in enumerate(self.work_data):
            answer = answers.get(step)
            final_data[quiz.var_name] = answer  # Чтобы вместо не заполненных было None
            if answer is None:
                answer = "[Не заполнено]"
            user_answers.append(f"{quiz.title} ({html.quote(answer)})")
        content = as_list(
            as_section(
                Bold("Your answers:"),
                as_numbered_list(*user_answers),
            ),
        )
        await bot.send_message(chat_id, **content.as_kwargs(), reply_markup=ReplyKeyboardRemove())
        if await self.save_user_data(user_id, final_data, data_st):
            logger.info(f"Userdata from %r was handled by %r with %r query and successfully saved.",
                        user_id, self.__class__.__name__, data_st.get('init_data'))
        else:
            logger.warning(f"Userdata from %r was handled by %r with %r query, but not saved!",
                           user_id, self.__class__.__name__, data_st.get('init_data'))

        await self.del_auto_msg('Отменено.', data_st, bot, chat_id)
        await self.exit_msg(message, state)

        await state.set_data({})

    @on.message(F.text == "🔙 Back")
    async def back(self, message: types.Message, bot: Bot, state: FSMContext) -> None:
        data = await state.get_data()
        step = data["step"]
        data = await self.del_auto_msg('Отменено.', data, bot, message.chat.id)
        await state.set_data(data)
        previous_step = step - 1
        if previous_step < 0:
            return await self.wizard.exit()
        return await self.wizard.back(step=previous_step)

    @on.message(F.text == "ℹ️ Info")
    async def help(self, message: types.Message, state: FSMContext) -> None:
        data = await state.get_data()
        step = data["step"]
        await message.answer(
            text=self.work_data[step].description
        )

    @on.message(F.text == "➡️ Skip")
    async def skip(self, msg, bot: Bot, state: FSMContext) -> None:
        data = await state.get_data()
        step = data["step"]
        if self.work_data[step].presets:
            if automsg := data.get('automsg', None):
                try:
                    await bot.edit_message_reply_markup(chat_id=msg.chat.id, message_id=automsg, reply_markup=None)
                except Exception as e:
                    logger.warning(f"Can't edit msg! %r", e)
                await msg.answer('Данный шаг нельзя пропустить!')
                await self.show_presets_msg(msg.chat.id, self.work_data[step].presets, bot, state)
            return

        data = await self.del_auto_msg('Выбрано:', data, bot, msg.chat.id)
        await state.set_data(data)

        await self.wizard.retake(step=step + 1)

    @on.message(F.text == "🚫 Exit")
    async def exit(self, msg) -> None:
        await self.wizard.exit()

    @on.message(F.text)
    async def answer(self, message: types.Message, bot: Bot, state: FSMContext) -> None:
        data = await state.get_data()
        step = data["step"]
        if self.work_data[step].presets:
            if automsg := data.get('automsg', None):
                try:
                    await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=automsg, reply_markup=None)
                except Exception as e:
                    logger.warning(f"Can't edit msg! %r", e)
                await self.show_presets_msg(message.chat.id, self.work_data[step].presets, bot, state)
            return
        answers = data.get("answers", {})
        answers[step] = message.text
        data = await self.del_auto_msg('Выбрано:', data, bot, message.chat.id)
        await state.set_data(data)

        await state.update_data(answers=answers)
        await self.wizard.retake(step=step + 1)

    @on.callback_query(F.data.startswith(f'coms_select_'))
    async def autoselect(self, cbk: types.CallbackQuery, bot: Bot, state: FSMContext):
        data = await state.get_data()
        step = data["step"]
        value_id = int(cbk.data.removeprefix(f"coms_select_"))
        answers = data.get("answers", {})
        value = Preloads(pk=value_id, data=self.work_data[step].presets[value_id])
        answers[step] = value.data
        data = await self.del_auto_msg('Выбрано:', data, bot, cbk.message.chat.id)
        await state.set_data(data)

        await state.update_data(answers=answers)
        await cbk.message.answer(value.data)
        await cbk.answer()
        await self.wizard.retake(step=step + 1)

    @on.message()
    async def unknown_message(self, message: types.Message) -> None:
        await message.answer("Пожалуйста, отправьте корректный ответ!")
