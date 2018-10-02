import sys
sys.path.append('C:\\Users\\User\\1_MY_WORK\\1_Data_Scientist_and_ML_Project\\PredictionDota2\\HelpModules')
import collections
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from Prediction import Prediction, Features

class TelegramBot:
    def __init__(self, TOKEN, REQUEST_KWARGS):
        self.__updater = Updater(token=TOKEN, request_kwargs=REQUEST_KWARGS) # Токен API к Telegram
        self.__dispatcher = self.__updater.dispatcher
         
    def addAllHandlerInDispatcher(self):
        try:
            self.__dispatcher.add_handler(self.__start_command_handler)
            # dispatcher.add_handler(text_message_handler)
            self.__dispatcher.add_handler(self.__rules_command_handler)
            self.__dispatcher.add_handler(self.__predict_command_handler)
        except Exception as e:
            print('Ошибка при добавлении Хендлеров')
            print(e)
            
    def runBot(self):
        self.__updater.start_polling(clean=True) # Начинаем поиск обновлений
        self.__updater.idle() # Останавливаем бота, если были нажаты Ctrl + C

    def createAllHandler(self):
        try:
            command = Command()
            self.__start_command_handler = CommandHandler('start', command.startCommand)
            # text_message_handler = MessageHandler(Filters.text, textMessage)
            self.__rules_command_handler = CommandHandler('rules', command.ruleCommand)
            self.__predict_command_handler = CommandHandler('predict', command.predictCommand)
        except Exception as e:
            print('Ошибка при создании Хендлеров')
            print(e)
    
class Command:
    def __getIdMathcFromMessageUser(self, update):
        match_id = update.message.text[9:]
        print(match_id)
        return match_id
    
    def startCommand(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text='Привет, напиши id матча в доте')
    def ruleCommand(self, bot, update):
        rules = """
        1) Ставить только на команду с кф выше 2, но лучше ждать кф 2.5
        2) Не ставить на матчи с явными аутсайдерами и фаворитами. 
           Если кф на одну из команд меньше чем 1.3, то такие матчи необходимо пропустить
        3) Лучше не ставить на команду по прогнозу, если до 35 минуты на нее не было кф 2+.
           Так как часто если появляется кф 2+ на команду после 35-40 минуты, это значит,
           что противник сделал камбек.
        """
        bot.send_message(chat_id=update.message.chat_id, text=rules)
    def predictCommand(self, bot, update):
        # Создать текст для юзера, если отсуствует много данных и лучше пропустить матч
        def create_text_atention_for_users(all_data_for_telegram_bot):
            text_Head_to_head = ''
            text_meta = ''
            text_signatures = ''
            collect_Head_to_head = collections.Counter(all_data_for_telegram_bot[0].values[0])
            if collect_Head_to_head[0.0] > 1:
                text_Head_to_head = 'Head_to_head - Лучше пропустить матч, так как отсутствуют данные более чем по 2ум героям!!'

            collect_meta = collections.Counter(all_data_for_telegram_bot[1].values[0])
            if collect_meta[0.0] > 1:
                text_meta = 'Meta - Лучше пропустить матч, так как отсутствуют данные более чем по 2ум героям!!'

            collect_signatures = collections.Counter(all_data_for_telegram_bot[2].values[0])
            if collect_signatures[0.0] > 3:
                text_signatures = 'Signatures - Лучше пропустить матч, так как более 4 игроков не наиграли на своих героях!!'
            attention_text = text_Head_to_head + '\n' + text_meta + '\n' + text_signatures + '\n' 
            return attention_text
        # Создать текст для юзера с предсказаниями
        def create_text_predict_for_user(predict_gb1, predict_gb2, predict_gb3):
            text_predict_for_user = 'Лучше пропустить матч'
            if predict_gb1[0][0] > 0.60 and predict_gb2[0][0] > 0.60 and predict_gb3[0][0] > 0.60:
                text_predict_for_user = 'Победа команды Dire'
            if predict_gb1[0][1] > 0.60 and predict_gb1[0][1] > 0.60 and predict_gb1[0][1] > 0.60:
                text_predict_for_user = 'Победа команды Radiant'
            return text_predict_for_user

        match_id = self.__getIdMathcFromMessageUser(update)

        try:
            cur_match = Features(match_id)
        except Exception as e:
            print("Проблемы с созданием класса Фич")
            print(e)

        try:
            cur_match.get_data_players_for_signatures_at_allTime_and_7dayAgo()
        except Exception as e:
            print("Не получилось собрать данные по команде, возмодно команда мало сыграла вмсете")
            print(e)

        try:
            cur_match.get_teams_heroes_players_id()
        except Exception as e:
            print("Не получилось собрать ID игроков или героев")
            print(e)

        try:
            all_features = cur_match.get_and_connect_all_data_for_match()
            all_data_for_telegram_bot = cur_match.getHeadToHeadMetaSignaturesForTelegram()
        except Exception as e:
            print('Не получилось собрать все фичи в один ДФ')
            print(e)

        try:
            def createOutpuDataOfAlgortim(filename, name_columns_of_valid_features):
                predict_algor = Prediction(filename, name_columns_of_valid_features, all_features)
                text_algor = predict_algor.getTextPredict()
                predict_proba_algor = predict_algor.getPredictProba()
                return predict_algor, text_algor, predict_proba_algor

            filename1 = '../Work/xgb_v.1.2.b.66.sav'
            name_columns_of_valid_features1 = ['radiant_mu_glicko', 'radiant_rating_glicko',
               'radiant_ratingSevenDaysAgo_glicko', 'radiant_mu_glicko2',
               'dire_mu_glicko', 'radiant_H1_elo_vs_enemies',
               'radiant_H2_elo_vs_enemies', 'radiant_H3_elo_vs_enemies',
               'radiant_H4_elo_vs_enemies', 'radiant_H5_elo_vs_enemies',
               'dire_H1_elo_vs_enemies', 'dire_H2_elo_vs_enemies',
               'dire_H3_elo_vs_enemies', 'dire_H4_elo_vs_enemies',
               'dire_H5_elo_vs_enemies', 'radiant_H1_AvgElo', 'radiant_H2_AvgElo',
               'radiant_H3_AvgElo', 'radiant_H4_AvgElo', 'radiant_H5_AvgElo',
               'dire_H1_AvgElo', 'dire_H2_AvgElo', 'dire_H3_AvgElo', 'dire_H4_AvgElo',
               'dire_H5_AvgElo', 'radiant_P1_eloShift', 'radiant_P2_eloShift',
               'radiant_P3_eloShift', 'radiant_P4_eloShift', 'radiant_P5_eloShift',
               'dire_P1_eloShift', 'dire_P2_eloShift', 'dire_P3_eloShift',
               'dire_P4_eloShift', 'Clockwerk', 'Gyrocopter', 'Io', 'Predict',
               'radiant_elo_vs_enemies', 'radiant_P_eloShift', 'dire_P_eloShift',
               'P_eloShift', 'radiant_H_AvgElo', 'dire_H_AvgElo', 'H_AvgElo']
            predict_1st_algor, text_1st_algor, predict_proba_1st_algor =  createOutpuDataOfAlgortim(filename1, 
                                                                                    name_columns_of_valid_features1)

            filename2 = '../Work/xgb_v.1.3.b.75.sav'
            name_columns_of_valid_features2 = ['radiant_mu_glicko', 'radiant_rating_glicko',
               'radiant_ratingSevenDaysAgo_glicko', 'radiant_mu_glicko2',
               'dire_mu_glicko', 'radiant_H1_elo_vs_enemies',
               'radiant_H2_elo_vs_enemies', 'radiant_H3_elo_vs_enemies',
               'radiant_H4_elo_vs_enemies', 'radiant_H5_elo_vs_enemies',
               'dire_H1_elo_vs_enemies', 'dire_H2_elo_vs_enemies',
               'dire_H3_elo_vs_enemies', 'dire_H4_elo_vs_enemies',
               'dire_H5_elo_vs_enemies', 'radiant_H1_AvgElo', 'radiant_H2_AvgElo',
               'radiant_H3_AvgElo', 'radiant_H4_AvgElo', 'radiant_H5_AvgElo',
               'dire_H1_AvgElo', 'dire_H2_AvgElo', 'dire_H3_AvgElo', 'dire_H4_AvgElo',
               'dire_H5_AvgElo', 'radiant_P1_eloShift', 'radiant_P2_eloShift',
               'radiant_P3_eloShift', 'radiant_P4_eloShift', 'radiant_P5_eloShift',
               'dire_P1_eloShift', 'dire_P2_eloShift', 'dire_P3_eloShift',
               'dire_P4_eloShift', 'dire_P5_eloShift', 'Predict',
               'radiant_elo_vs_enemies', 'radiant_P_eloShift', 'dire_P_eloShift',
               'P_eloShift', 'radiant_H_AvgElo', 'dire_H_AvgElo', 'H_AvgElo']
            predict_2nd_algor, text_2nd_algor, predict_proba_2nd_algor = createOutpuDataOfAlgortim(filename2, 
                                                                                    name_columns_of_valid_features2)

            filename3 = '../Work/xgb_v.1.4.d.69.sav'
            name_columns_of_valid_features3 = ['radiant_mu_glicko', 'radiant_rating_glicko', 'radiant_mu_glicko2',
               'dire_mu_glicko', 'radiant_H1_elo_vs_enemies',
               'radiant_H2_elo_vs_enemies', 'radiant_H3_elo_vs_enemies',
               'radiant_H4_elo_vs_enemies', 'radiant_H5_elo_vs_enemies',
               'dire_H1_elo_vs_enemies', 'dire_H2_elo_vs_enemies',
               'dire_H4_elo_vs_enemies', 'dire_H5_elo_vs_enemies', 'radiant_H1_AvgElo',
               'radiant_H2_AvgElo', 'radiant_H3_AvgElo', 'radiant_H4_AvgElo',
               'radiant_H5_AvgElo', 'dire_H1_AvgElo', 'dire_H2_AvgElo',
               'dire_H3_AvgElo', 'dire_H4_AvgElo', 'dire_H5_AvgElo',
               'radiant_P1_eloShift', 'radiant_P2_eloShift', 'radiant_P3_eloShift',
               'radiant_P4_eloShift', 'radiant_P5_eloShift', 'dire_P1_eloShift',
               'dire_P3_eloShift', 'dire_P4_eloShift', 'radiant_H1_AvgElo_7day_ago',
               'radiant_H2_AvgElo_7day_ago', 'radiant_H3_AvgElo_7day_ago',
               'radiant_H4_AvgElo_7day_ago', 'radiant_H5_AvgElo_7day_ago',
               'dire_H1_AvgElo_7day_ago', 'dire_H2_AvgElo_7day_ago',
               'dire_H3_AvgElo_7day_ago', 'dire_H4_AvgElo_7day_ago',
               'radiant_P1_eloShift_7day_ago', 'radiant_P2_eloShift_7day_ago',
               'radiant_P3_eloShift_7day_ago', 'radiant_P4_eloShift_7day_ago',
               'radiant_P5_eloShift_7day_ago', 'dire_P1_eloShift_7day_ago',
               'dire_P2_eloShift_7day_ago', 'dire_P3_eloShift_7day_ago',
               'dire_P4_eloShift_7day_ago', 'dire_P5_eloShift_7day_ago',
               'radiant_elo_vs_enemies', 'radiant_P_eloShift', 'dire_P_eloShift',
               'P_eloShift', 'dire_H_AvgElo', 'H_AvgElo', 'radiant_H_AvgElo_7day_ago',
               'dire_H_AvgElo_7day_ago', 'H_AvgElo_7day_ago',
               'radiant_P_eloShift_7day_ago', 'P_eloShift_7day_ago']
            predict_3rd_algor, text_3rd_algor, predict_proba_3rd_algor = createOutpuDataOfAlgortim(filename3, 
                                                                                        name_columns_of_valid_features3)
        except Exception as e:
            print("Ошибка в сборках предсказательных моделей")
            print(e)
        try:
            atention_text = create_text_atention_for_users(all_data_for_telegram_bot)
            prediction_text = create_text_predict_for_user(predict_proba_1st_algor, predict_proba_2nd_algor, 
                                                           predict_proba_3rd_algor)
            # -------------------------------------------------------------------------------
            response = (text_1st_algor + '\n' + text_2nd_algor + '\n' + text_3rd_algor + '\n' +
                       'Head-to-Head \n' + str(all_data_for_telegram_bot[0].values) + '\n' + 
                       'Meta \n' + str(all_data_for_telegram_bot[1].values) + '\n' + 
                       'Signatures \n' + str(all_data_for_telegram_bot[2].values) + '\n' + 
                       atention_text + prediction_text)
            bot.send_message(chat_id=update.message.chat_id, text=response)
        except Exception as e:
            print("Проблемы с выводом текста")
            print(e)