import pandas as pd
import telebot
from telebot import types
import yaml

with open("answers.yaml", "r") as stream:
  try:
    answers = yaml.safe_load(stream)
  except yaml.YAMLError as exc:
    print(exc)

#### Get and process data ####
def read_google_sheet(sheet_id, gid):
  sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}'
  return pd.read_csv(sheet_url)

def get_disease_data(main_df, message_text):
  disease_df = read_google_sheet(main_df.loc[main_df['Заболевание'] == message_text, 'Таблица'].values[0], main_df.loc[main_df['Заболевание'] == message_text, 'Диагностика'].values[0])
  questions = {}
  tresholds = {}
  i = 0
  for _,row in disease_df.iterrows():
    if row['question'] == 'Диагноз':
      tresholds[row['points']] = row['variants']
    elif not pd.isna(row['question']):
      i += 1
      questions[i] = {'question':row['question'], 'multiple':row['multiple'], 'variants':{row['variants']:row['points']}}
    else:
      questions[i]['variants'][row['variants']] = row['points']
  return [questions, tresholds]

def make_question_table(disease_data):
  question_table = {0:[1]}
  for i, data in disease_data.items():
    question_table[i] = [0]*len(data['variants'])
  return question_table

#### Get results ####
def get_diagnosis(score, data):
  for key, val in data.items():
    if key > score:
      return val
  return val

def calculate_score(questions_table, diseases_data):
  score = 0
  for i, val in enumerate(list(questions_table.values())[1:]):
    for j, x in enumerate(list(diseases_data[i+1]['variants'].values())):
      if val[j]:
        score += x
  return score

#### Handle messages ####
def get_markup(variants: dict, user_inputs: list, current_question: int, last: int):
  markup = types.InlineKeyboardMarkup(row_width=2)
  for i, key in enumerate(variants):
    if user_inputs[i]:
      markup.add(types.InlineKeyboardButton(key + ' ☑️', callback_data=str(i)))
    else:
      markup.add(types.InlineKeyboardButton(key, callback_data=str(i)))
  if current_question != 1:
    markup.add(types.InlineKeyboardButton("⬅️ Предыдущий", callback_data='previous'))
  if current_question == last:
    markup.add(types.InlineKeyboardButton("Завершить 🏁", callback_data='results'))
  else:
    markup.add(types.InlineKeyboardButton("Следующий ➡️", callback_data='next'))
  return markup

def edit_message(bot, chat_id, message_id, current_question, tests_data, question_data):
  try:
    bot.edit_message_text(chat_id=chat_id,
                      message_id=message_id,
                      text=f"<i>Вопрос {current_question} из {len(tests_data[chat_id]['questions_table'])-1}</i>\n{question_data['question']}",
                      reply_markup=get_markup(question_data['variants'],
                                              tests_data[chat_id]['questions_table'][current_question],
                                              current_question,
                                              len(tests_data[chat_id]['questions_table'])-1),
                      parse_mode="HTML")
  except:
    pass
    
def start_block_test(bot, message_id, chat_id, diseases_data, tests_data, disease, main_df):
  start_markup = types.InlineKeyboardMarkup()
  start_markup.add(types.InlineKeyboardButton('Начать 🚀', callback_data='next'))
  diseases_data[disease] = diseases_data.get(disease, get_disease_data(main_df, disease)) # for cache
  tests_data[chat_id] = {'current_message':message_id + 1,
                          'current_test':disease,
                          'questions_table':make_question_table(diseases_data[disease][0]),
                          'current_question':0} # заводим таблицу для юзера по начатаму тесту
  bot.send_message(chat_id=chat_id,
                  text=f'Заболевание: {disease}. В тесте {len(tests_data[chat_id]["questions_table"])-1} вопросов. Ответьте на вопросы, как часто пациента беспокоили следующие сипмптомы в течение последних <b>двух недель</b>?',
                  parse_mode="HTML",
                  reply_markup=start_markup)

#### Handle warnings ####
def warning(bot, warnings, err, chat_id):
  text = answers[err]
  message = bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
  warnings[chat_id] = warnings.get(chat_id, []) + [message.message_id]

def answer_not_chosen_warning(bot, warnings, err, chat_id, tests_data, current_question, diseases_data):
  text = answers[err][int(diseases_data[tests_data[chat_id]['current_test']][0][current_question]['multiple'])]
  message = bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
  warnings[chat_id] = warnings.get(chat_id, []) + [message.message_id]

def change_test_warning(bot, warnings, err, chat_id, disease):
  text = answers[err]
  change_test_markup = types.InlineKeyboardMarkup()
  change_test_markup.add(types.InlineKeyboardButton('Да, прервать 💀', callback_data='change_test$'+disease))
  change_test_markup.add(types.InlineKeyboardButton('Нет, продолжить 🥺', callback_data='dont_change_test'))
  message = bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=change_test_markup)
  warnings[chat_id] = warnings.get(chat_id, []) + [message.message_id]
