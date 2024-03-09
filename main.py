import pandas as pd
import yaml 
import telebot
from telebot import types
from funcs import *

with open("credentials.yaml", "r") as stream:
  try:
    credentials = yaml.safe_load(stream)
  except yaml.YAMLError as exc:
    print(exc)
    
main_df = read_google_sheet(credentials['main_sheet_id'], 0)
diseases_data = {}
tests_data = {}
warnings = {}

bot = telebot.TeleBot(credentials['token'])

@bot.message_handler(commands = ['start'])
def start(message):
  bot.send_message(message.from_user.id, answers['disclaimer_message'])
  bot.send_message(message.from_user.id, answers['hello_message'])

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
  chat_id = message.chat.id
  message_id = message.message_id
  warnings[chat_id] = warnings.get(chat_id, []) + [message_id]
  disease = message.text
  if warnings.get(chat_id, []):
    for ind in warnings.pop(chat_id):
      bot.delete_message(chat_id=chat_id, message_id=ind)
  print(chat_id, disease) # for debugging
  # сделать неточный поиск по описанным заболеваниям
  if (main_df['Заболевание'] == disease).sum():     
    if tests_data.get(chat_id, None): # если есть начатый тест
      change_test_warning(bot, warnings, 'change_test_warning', chat_id, disease)
    else:
      start_block_test(bot, message_id, chat_id, diseases_data, tests_data, disease, main_df)
  else:
    warning(bot, warnings, 'dont_understand_warning', chat_id) 

@bot.callback_query_handler(func=lambda call: True)
def answer(call):
  chat_id = call.message.chat.id
  message_id = call.message.message_id
  if not tests_data.get(chat_id, None):
    return
  current_question = tests_data[chat_id]['current_question']
  if warnings.get(chat_id, None):
    for ind in warnings.pop(chat_id):
      bot.delete_message(chat_id=chat_id, message_id=ind)
  if call.data.startswith('change_test'):
    disease = call.data.split("$")[-1]
    bot.delete_message(chat_id=chat_id, message_id=tests_data[chat_id]['current_message'])
    start_block_test(bot, message_id, chat_id, diseases_data, tests_data, disease, main_df)
  elif call.data == 'dont_change_test':
    pass
  elif call.data == 'results':
    if sum(tests_data[chat_id]['questions_table'][current_question]) > 0:
      score = calculate_score(tests_data[chat_id]['questions_table'], diseases_data[tests_data[chat_id]['current_test']][0])
      bot.edit_message_text(chat_id=chat_id,
                            message_id=message_id,
                            text=f'Общее кол-во баллов: {score}\n{get_diagnosis(score, diseases_data[tests_data[chat_id]["current_test"]][1])}')
      del tests_data[chat_id] 
    else:
      answer_not_chosen_warning(bot, warnings, 'answer_not_chosen_warning', chat_id, tests_data, current_question, diseases_data)
  elif call.data == 'next':
    if sum(tests_data[chat_id]['questions_table'][current_question]) > 0:
      current_question += 1
      edit_message(bot, chat_id, message_id, current_question, tests_data, diseases_data[tests_data[chat_id]['current_test']][0][current_question])
      tests_data[chat_id]['current_question'] = current_question
    else:
      answer_not_chosen_warning(bot, warnings, 'answer_not_chosen_warning', chat_id, tests_data, current_question, diseases_data)
  elif call.data == 'previous':
    current_question -= 1
    edit_message(bot, chat_id, message_id, current_question, tests_data, diseases_data[tests_data[chat_id]['current_test']][0][current_question])
    tests_data[chat_id]['current_question'] = current_question
  else:
    if sum(tests_data[chat_id]['questions_table'][current_question]) > 0 and not diseases_data[tests_data[chat_id]['current_test']][0][current_question]['multiple']:
      tests_data[chat_id]['questions_table'][current_question] = [0]*len(tests_data[chat_id]['questions_table'][current_question])
    tests_data[chat_id]['questions_table'][current_question][int(call.data)] = 1 - tests_data[chat_id]['questions_table'][current_question][int(call.data)]
    edit_message(bot, chat_id, message_id, current_question, tests_data, diseases_data[tests_data[chat_id]['current_test']][0][current_question])
    
if __name__ == '__main__':  
    bot.polling(none_stop=True, interval=0)
