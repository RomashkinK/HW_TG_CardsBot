import random
import configparser
import sqlalchemy as sq
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from sqlalchemy.orm import sessionmaker
from models import User, UserDictionary, MainDictionary

print('Start telegram bot...')

state_storage = StateMemoryStorage()
config = configparser.ConfigParser()
config.read('settings.ini')

token_bot = config['telegram']['token']
bot = TeleBot(token_bot, state_storage=state_storage)

engine = sq.create_engine(config['postgres']['DSN'])


# Функция возвращает список пользователей из базы данных
def get_users(engine):
    session = (sessionmaker(bind=engine))()
    users = session.query(User).all()
    users = [user.cid for user in users]
    session.close()
    return users

# Функция добавляет нового пользователя в базу данных
def add_new_user(engine, user_id):
    session = (sessionmaker(bind=engine))()
    session.add(User(cid=user_id))
    session.commit()
    session.close()

# Функция возвращает слова и переводы из базы данных
def get_words(engine, user_id):
    session = (sessionmaker(bind=engine))()
    words = session.query(UserDictionary.word, UserDictionary.translate) \
        .join(User, User.id == UserDictionary.id_user) \
        .filter(User.cid == user_id).all()
    common_words = session.query(MainDictionary.word, MainDictionary.translate).all()
    result = common_words + words
    session.close()
    return result

# Функция добавляет пользовательское слово в базу данных
def add_user_word(engine, cid, word, translate):
    session = (sessionmaker(bind=engine))()
    id_user = session.query(User.id).filter(User.cid == cid).first()[0]
    session.add(UserDictionary(word=word, translate=translate, id_user=id_user))
    session.commit()
    session.close()

# Функция удаляет пользовательское слово из базы данных
def delete_user_word(engine, cid, word):
    session = (sessionmaker(bind=engine))()
    id_user = session.query(User.id).filter(User.cid == cid).first()[0]
    session.query(UserDictionary).filter(UserDictionary.id_user == id_user, UserDictionary.word == word).delete()
    session.commit()
    session.close()

# Функция подсказок при вводе ответа в боте
def show_hint(*lines):
    return '\n'.join(lines)

# Функция показывающая слово для перевода
def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"


# Название кнопок в Telegram-боте
class Command: 
    ADD_WORD = 'ДОБАВИТЬ СЛОВО ➕'
    DELETE_WORD = 'УДАЛИТЬ СЛОВО 🔙'
    NEXT = 'ДАЛЬШЕ⏭'


class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()

# Функция возвращает текущий шаг пользователя
def get_user_step(uid):
    if uid in userStep:
        return userStep[uid]
    else:
        known_users.append(uid)
        userStep[uid] = 0
        print("New user detected, who hasn't used \"/start\" yet")
        return 0
    

known_users = get_users(engine)
userStep = {}
buttons = []

# Обработка команды /start и /cards и функция создающая карточки
@bot.message_handler(commands=['start', 'cards'])
def create_cards(message):
    cid = message.chat.id
    userStep[cid] = 0
    if cid not in known_users:
        known_users.append(cid)
        add_new_user(engine, cid)
        userStep[cid] = 0
        bot.send_message(cid, '''Привет 👋 Давай попрактикуемся в английском языке. Тренировки можешь проходить в удобном для себя темпе.

У тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения. Для этого воспрользуйся инструментами:

Добавить слово ➕,
Удалить слово 🔙.
Ну что, начнём ⬇️?''')
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    words_random = random.sample(get_words(engine,cid), 4)
    word = words_random[0]
    print (f'Choosing word: {word}')
    target_word = word[0]
    translate = word[1]
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = [word for word, _ in words_random[1:]]
    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])
    markup.add(*buttons)

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others

# Обработчик кнопки "ДАЛЬШЕ⏭"
@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


# Обработчик кнопки "ДОБАВИТЬ СЛОВО ➕"
@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    cid = message.chat.id
    userStep[cid] = 1
    bot.send_message(cid, 'Введите слово на английском языке')
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)


#Обработчик кнопки "УДАЛИТЬ СЛОВО 🔙"
@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    cid = message.chat.id
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        word = data['target_word']
    delete_user_word(engine, cid, word)
    print(f'Delete word: {word}')
    bot.send_message(message.chat.id, f'Слово {word} успешно удалено')
    create_cards(message)

# Реакции бота на ввод пользователя
@bot.message_handler(func=lambda message: True, content_types=['text'])
def bot_reaction(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    cid = message.chat.id
    if userStep[cid] == 0:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            target_word = data['target_word']
            if  text == target_word:
                hint = show_target(data)
                hint_text = ["Отлично!❤", hint]
                hint = show_hint(*hint_text)
            else:
                for btn in buttons:
                    if btn.text == text:
                        btn.text = text +'❌'
                        break
                hint = show_hint("Допущена ошибка!",
                                f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}")
        markup.add(*buttons)
        bot.send_message(message.chat.id, hint, reply_markup=markup)
        if text == target_word:
            create_cards(message)

    elif userStep[cid] == 1:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word'] = text
            bot.send_message(cid, 'Введите перевод слова на русском языке')
            bot.set_state(message.from_user.id, MyStates.translate_word, message.chat.id)
            userStep[cid] = 2

    elif userStep[cid] == 2:
            with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
                data['translate_word'] = text
                add_user_word(engine,cid, data['target_word'], data['translate_word'])
                bot.send_message(cid, 'Слово добавлено')
                bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
                hint_text = ["Отлично!❤ Жми ДАЛЬШЕ⏭ или ДОБАВИТЬ СЛОВО ➕ если хочешь добавить ещё одно"]
                hint = show_hint(*hint_text)
                userStep[cid] = 0
                markup.add(*buttons)
                bot.send_message(message.chat.id, hint, reply_markup=markup)
    
bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.infinity_polling(skip_pending=True)
