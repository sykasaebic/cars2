import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv('BOT_TOKEN')  # СЮДА ТВОЙ ТОКЕН

# --- ДАННЫЕ (ВОПРОСЫ) ---
QUESTIONS = {
    1: {
        "question": "Было?",
        "options": ["Да", "Нет", "Возможно", "Не знаю"],
        "correct": 0,
        "points": 10,
        "image_url": "https://i.redd.it/3um53493yy6d1.jpeg"
    },
    2: {
        "question": "Точно было?",
        "options": ["Да", "Нет", "Сомневаюсь", "100%"],
        "correct": 1,
        "points": 15,
        "image_url": "https://i.redd.it/3um53493yy6d1.jpeg"
    },
    3: {
        "question": "Абсолютно точно было?",
        "options": ["Да", "Нет, я врун", "Возможно ты был прав", "Нет"],
        "correct": 1,
        "points": 20,
        "image_url": "https://i.redd.it/3um53493yy6d1.jpeg"
    },
    4: {
        "question": "А он выжил вообще?",
        "options": ["Да", "Нет", "Неизвестно", "Возможно"],
        "correct": 0,
        "points": 25,
        "image_url": "https://i.redd.it/3um53493yy6d1.jpeg"
    }
}

# --- КЛАВИАТУРЫ ---
main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📜 Начать викторину")]],
    resize_keyboard=True
)

# --- СОСТОЯНИЯ FSM ---
class QuizState(StatesGroup):
    answering = State()

# --- ХРАНИЛИЩЕ ДАННЫХ ПОЛЬЗОВАТЕЛЕЙ ---
user_scores = {}
# Словарь для отслеживания, отвечал ли пользователь на вопрос (защита от двойного нажатия)
user_answered = {}

# --- ИНИЦИАЛИЗАЦИЯ БОТА ---
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def get_grade(percent: int) -> str:
    """Определяет оценку по проценту"""
    if percent >= 80:
        return "🌟 БОГ ИСТОРИИ!"
    elif percent >= 60:
        return "👍 НЕПЛОХО!"
    elif percent >= 40:
        return "📚 НОРМ"
    else:
        return "😂 АХАХАХА, УЧИ ИСТОРИЮ!"

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    # Полностью очищаем состояние
    await state.clear()
    user_id = message.from_user.id
    
    # Полностью удаляем все данные пользователя
    user_scores.pop(user_id, None)
    user_answered.pop(user_id, None)
    
    max_possible = sum(q['points'] for q in QUESTIONS.values())
    
    welcome_text = f"""
🎯 *ИСТОРИЧЕСКАЯ ВИКТОРИНА* 🎯

Привет, *{message.from_user.first_name}*! 👋

Проверь свои знания!

📊 *Всего вопросов:* {len(QUESTIONS)}
🏆 *Максимум баллов:* {max_possible}

👇 *Нажми кнопку ниже, чтобы начать*
"""
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_kb)

@dp.message(F.text == "📜 Начать викторину")
async def start_quiz(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, не идёт ли уже викторина
    current_state = await state.get_state()
    if current_state == QuizState.answering:
        await message.answer("⚠️ Викторина уже идёт! Отвечай на текущий вопрос.")
        return
    
    # Сбрасываем данные перед началом
    user_scores[user_id] = {'score': 0, 'answers': {}}
    user_answered[user_id] = set()  # Для отслеживания отвеченных вопросов
    
    # Устанавливаем состояние
    await state.set_state(QuizState.answering)
    
    # Начинаем с первого вопроса
    await ask_question(message, user_id, 1)

async def ask_question(message: types.Message, user_id: int, q_id: int):
    """Отправляет вопрос пользователю"""
    # Проверяем, не завершена ли викторина
    if user_id not in user_scores:
        await message.answer("Начни викторину заново с помощью /start")
        return
    
    if q_id not in QUESTIONS:
        await finish_quiz(message, user_id)
        return
    
    question_data = QUESTIONS[q_id]
    
    text = f"""
📖 *Вопрос {q_id}/{len(QUESTIONS)}*

*{question_data['question']}*

💰 *Баллов:* {question_data['points']}

🔽 *Выбери ответ:*
"""
    
    # Создаём кнопки
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for idx, option in enumerate(question_data['options']):
        # Пропускаем пустые варианты ответов
        if option and option.strip():
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(text=f"{idx+1}. {option}", callback_data=f"ans_{q_id}_{idx}")
            ])
    
    # Отправляем вопрос
    image_url = question_data.get('image_url', '')
    if image_url and image_url.strip():
        try:
            await message.answer_photo(
                photo=image_url,
                caption=text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        except Exception:
            # Если фото не загрузилось, отправляем без фото
            await message.answer(
                text + "\n_⚠️ Картинка не загрузилась_",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    else:
        await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ans_"), QuizState.answering)
async def handle_answer(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    # Проверяем, есть ли данные пользователя
    if user_id not in user_scores:
        await callback.answer("Начни викторину заново с помощью /start", show_alert=True)
        await callback.message.answer("Нажми /start, чтобы начать новую викторину")
        return
    
    _, q_id_str, answer_idx_str = callback.data.split("_")
    q_id = int(q_id_str)
    answer_idx = int(answer_idx_str)
    
    # Защита от повторного ответа на один вопрос
    if q_id in user_answered.get(user_id, set()):
        await callback.answer("⚠️ Ты уже ответил на этот вопрос!", show_alert=True)
        return
    
    question_data = QUESTIONS[q_id]
    
    # Проверяем, что индекс ответа существует
    if answer_idx >= len(question_data['options']):
        await callback.answer("❌ Ошибка: неверный вариант ответа", show_alert=True)
        return
    
    is_correct = (answer_idx == question_data["correct"])
    
    # Обновляем счёт
    if is_correct:
        points = question_data["points"]
        user_scores[user_id]['score'] += points
        await callback.answer(f"✅ Верно! +{points} баллов", show_alert=False)
    else:
        correct_text = question_data["options"][question_data["correct"]]
        await callback.answer(f"❌ Неверно! Правильно: {correct_text}", show_alert=False)
    
    # Запоминаем ответ
    user_scores[user_id]['answers'][q_id] = {
        'user_choice': answer_idx,
        'is_correct': is_correct
    }
    
    # Отмечаем, что на вопрос ответили
    if user_id not in user_answered:
        user_answered[user_id] = set()
    user_answered[user_id].add(q_id)
    
    # Удаляем кнопки
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass  # Игнорируем ошибки редактирования
    
    # Переходим к следующему вопросу
    next_q = q_id + 1
    
    if next_q in QUESTIONS:
        await ask_question(callback.message, user_id, next_q)
    else:
        # Очищаем состояние
        await state.clear()
        await finish_quiz(callback.message, user_id)

async def finish_quiz(message: types.Message, user_id: int):
    """Выводит итоговый результат"""
    
    # Проверяем, есть ли данные пользователя
    if user_id not in user_scores:
        await message.answer("Начни викторину заново с помощью /start")
        return
    
    total_score = user_scores[user_id]['score']
    max_possible = sum(q['points'] for q in QUESTIONS.values())
    correct_count = sum(1 for a in user_scores[user_id]['answers'].values() if a['is_correct'])
    total_questions = len(QUESTIONS)
    
    # Защита от деления на ноль
    percent = int(total_score / max_possible * 100) if max_possible > 0 else 0
    
    # Получаем оценку
    grade = get_grade(percent)
    
    # Результат
    result_text = f"""
🎯 *РЕЗУЛЬТАТ ВИКТОРИНЫ* 🎯

✅ *Правильно:* {correct_count} / {total_questions}
💰 *Баллы:* {total_score} / {max_possible}
📊 *Успех:* {percent}%

🏆 *Оценка:* {grade}

💫 *Чтобы начать заново, нажми /start*
"""
    
    await message.answer(result_text, parse_mode="Markdown", reply_markup=main_kb)
    
    # Очищаем данные пользователя через 5 секунд (чтобы он успел увидеть результат)
    await asyncio.sleep(5)
    user_scores.pop(user_id, None)
    user_answered.pop(user_id, None)

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = """
📚 *Помощь*

Используй команды:
/start - начать или перезапустить викторину
/help - показать эту справку

📜 *Как играть:*
1. Нажми /start
2. Нажми кнопку "📜 Начать викторину"
3. Отвечай на вопросы, нажимая на кнопки
4. Получи результат!

⚠️ *Важно:* Не нажимай на кнопки ответа дважды!
"""
    await message.answer(help_text, parse_mode="Markdown")

# --- ЗАПУСК БОТА ---
async def main():
    logging.basicConfig(level=logging.INFO)
    print("🎯 Бот запущен!")
    print("✅ Готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())