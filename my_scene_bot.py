import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command
from aiogram.fsm.scene import SceneRegistry, ScenesManager
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.types import Message


from myscene import CommonInfoScene, get_list_data_ikb, Preloads

TOKEN = os.environ.get('BOT_TOKEN')

quiz_router = Router(name=__name__)
# Add handler that initializes the scene


@quiz_router.message(Command("start"))
async def command_start(message: Message, scenes: ScenesManager):
    await scenes.close()
    items = [Preloads(pk=1, data='Выбор 1'), Preloads(pk=2, data='Выбор 2')]
    await message.answer(
        "Hi! This is a quiz demo bot.",
        reply_markup=get_list_data_ikb(items, 'menu'),
    )


@quiz_router.callback_query(F.data == 'cancel_soft')
async def cancel_soft(cbk: types.CallbackQuery):
    await cbk.message.edit_text('Действие отменено.', reply_markup=None)
    await cbk.answer('Действие отменено!')


def create_dispatcher():
    # Event isolation is needed to correctly handle fast user responses
    dispatcher = Dispatcher(
        events_isolation=SimpleEventIsolation(),
    )
    dispatcher.include_router(quiz_router)

    # To use scenes, you should create a SceneRegistry and register your scenes there
    scene_registry = SceneRegistry(dispatcher)
    # ... and then register a scene in the registry
    # by default, Scene will be mounted to the router that passed to the SceneRegistry,
    # but you can specify the router explicitly using the `router` argument
    scene_registry.add(CommonInfoScene)

    return dispatcher


quiz_router.callback_query.register(CommonInfoScene.as_handler(somevar='Hi there!'), F.data.startswith('menu_select_'))


async def main():
    dispatcher = create_dispatcher()
    bot = Bot(TOKEN)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
