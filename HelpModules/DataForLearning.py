import sys
sys.path.append('C:\\Users\\User\\1_MY_WORK\\1_Data_Scientist_and_ML_Project\\PredictionDota2\\HelpModules')
import pandas as pd
import numpy as np
import urllib, json
from datetime import date, timedelta, datetime
import re, requests, pickle
from sklearn.metrics import classification_report
from sklearn import metrics
from connection_to_internet import Connection_to_internet
from patch import Patch
class DataForLearning:
    def __init__(self, date_first, date_end):
        self.date_first = date_first
        self.date_end = date_end
        self.day_first_for_saving_in_file = date_first.date()
        self.day_end_for_saving_in_file = date_end.date()
        
        self.PATCH = Patch.getCurrentPatch(Patch)
        
        connect = Connection_to_internet()
        self.__get_url_from_proxy = connect.get_url_from_proxy
        self.__get_json_from_url = connect.get_json_from_url
    
    # ------- For SQL request to  Opendota  ----------------------------------------------------------------
    def __query_data_matches(self):
        sql = '''SELECT
        
        matches.match_id ,
        matches.start_time,
        matches.radiant_team_id,
        matches.radiant_score,
        matches.dire_team_id,
        matches.dire_score,
        matches.radiant_win
        FROM matches
        JOIN match_patch using(match_id)
        JOIN leagues using(leagueid)
        JOIN player_matches using(match_id)
        JOIN heroes on heroes.id = player_matches.hero_id
        LEFT JOIN notable_players ON notable_players.account_id = player_matches.account_id AND notable_players.locked_until = (SELECT MAX(locked_until) FROM notable_players)
        LEFT JOIN teams using(team_id)
        WHERE TRUE
        AND matches.start_time >= extract(epoch from timestamp '{}')
        AND matches.start_time <= extract(epoch from timestamp '{}')
        AND leagues.tier = 'professional'
        AND match_patch.patch >= '7.01'
        GROUP BY matches.match_id
        HAVING count(distinct matches.match_id) >= 1
        LIMIT 2000000'''.format(self.date_first.isoformat() , self.date_end.isoformat()) 
        return  self.__query_opendota(sql)

    def __query_teams_heroes_mathes(self):
        sql = '''SELECT
        
        matches.match_id,
        matches.start_time,
        ((player_matches.player_slot < 128) = matches.radiant_win) win,
        player_matches.hero_id,
        player_matches.account_id,
        leagues.name leaguename
        FROM matches
        JOIN match_patch using(match_id)
        JOIN leagues using(leagueid)
        JOIN player_matches using(match_id)
        JOIN heroes on heroes.id = player_matches.hero_id
        LEFT JOIN notable_players ON notable_players.account_id = player_matches.account_id AND notable_players.locked_until = (SELECT MAX(locked_until) FROM notable_players)
        LEFT JOIN teams using(team_id)
        WHERE TRUE
        AND matches.start_time >= extract(epoch from timestamp '{}')
        AND matches.start_time <= extract(epoch from timestamp '{}')
        AND leagues.tier = 'professional'
        AND match_patch.patch >= '7.01'
        ORDER BY matches.match_id DESC NULLS LAST
        LIMIT 2000000'''.format(self.date_first.isoformat() , self.date_end.isoformat()) 
        return self.__query_opendota(sql)
    
    def __query_opendota(self, sql):
        resp = self.__get_url_from_proxy('https://api.opendota.com/api/explorer',({'sql': sql}))
        data = resp.json()
        return pd.DataFrame.from_records(data['rows'])
    # -------------------------------------------------------------------------------------------------------------
    
    def createAndSaveMainDf(self):
        # создать главный ДФ, в который и будет все добавляться
        main = pd.DataFrame(self.__query_data_matches())
        # присвоить ДФ для обработки из нужного файла с героями и игроками
        df_her_play = pd.DataFrame(self.__query_teams_heroes_mathes())
        # собрать все матчи из ДФ с героями и игроками
        matches = np.unique(df_her_play['match_id'])
        for id_match in matches:
            # номер индекса в галвном ДФ
            main_index = main[main['match_id'] == id_match].index[0]
            # создать два датафрейма по героям и игрокам (разделенных на выйгрывших и проигравших)
            her_false = pd.DataFrame(df_her_play['hero_id'][df_her_play['match_id'] == id_match][
                                                                                        df_her_play['win'] == False])
            her_true = pd.DataFrame(df_her_play['hero_id'][df_her_play['match_id'] == id_match][
                                                                                        df_her_play['win'] == True])
            heroes = pd.concat([her_false, her_true]).reset_index().T.drop('index')
            play_false = pd.DataFrame(df_her_play['account_id'][df_her_play['match_id'] == id_match][
                                                                                        df_her_play['win'] == False])
            play_true = pd.DataFrame(df_her_play['account_id'][df_her_play['match_id'] == id_match][
                                                                                        df_her_play['win'] == True])
            players = pd.concat([play_false, play_true]).reset_index().T.drop('index')

            # соединение и присваивание нормальных имен столбцам в дф с героями и игроками
            col_her = {0: 'lose_H1', 1: 'lose_H2', 2: 'lose_H3', 3: 'lose_H4', 4: 'lose_H5', 
                         5: 'win_H1', 6: 'win_H2', 7: 'win_H3', 8: 'win_H4', 9: 'win_H5'}
            col_play = {0: 'lose_P1', 1: 'lose_P2', 2: 'lose_P3', 3: 'lose_P4', 4: 'lose_P5', 
                         5: 'win_P1', 6: 'win_P2', 7: 'win_P3', 8: 'win_P4', 9: 'win_P5'}
            heroes = heroes.rename(columns=col_her,).rename( {'hero_id': 0})
            players = players.rename(columns=col_play).rename( {'account_id': 0})

            match = pd.merge(heroes, players,  left_index=True, right_index=True)
            match['match_id'] = id_match

            #ЗАменить название столбцов win or lose на радиант и даер
            if main[main['match_id'] == id_match]['radiant_win'].bool() == False:
                for i in range(1,6):
                    main.loc[main_index, 'radiant_H' + str(i)] = match['lose_H' + str(i)][0]
                for i in range(1,6):
                    main.loc[main_index, 'dire_H' + str(i)] = match['win_H' + str(i)][0]
                for i in range(1,6):
                    main.loc[main_index, 'radiant_P' + str(i)] = match['lose_P' + str(i)][0]
                for i in range(1,6):
                    main.loc[main_index, 'dire_P' + str(i)] = match['win_P' + str(i)][0]

            elif main[main['match_id'] == id_match]['radiant_win'].bool() == True:
                for i in range(1,6):
                    main.loc[main_index, 'radiant_H' + str(i)] = match['win_H' + str(i)][0]
                for i in range(1,6):
                    main.loc[main_index, 'dire_H' + str(i)] = match['lose_H' + str(i)][0]
                for i in range(1,6):
                    main.loc[main_index, 'radiant_P' + str(i)] = match['win_P' + str(i)][0]
                for i in range(1,6):
                    main.loc[main_index, 'dire_P' + str(i)] = match['lose_P' + str(i)][0]
        # добавить лигу
        for id_match in matches:
            # номер индекса в галвном ДФ
            main_index = main[main['match_id'] == id_match].index[0]
            df_her_play_index = df_her_play[df_her_play['match_id'] == id_match].index[0]

            main.loc[main_index, 'league_name'] = df_her_play.loc[df_her_play_index,'leaguename']
        main.to_csv('../tabel/MAIN TABEL PREMIUM on {} to {}.csv'.format(self.day_first_for_saving_in_file, 
                                                                         self.day_end_for_saving_in_file))
        print('MAIN - ', len(main))
        return main
    
    def createColumnWithTeamName(self, main):
        # создать дф из json по всем командам с OPENDOTA https://api.opendota.com/api/teams
        url_teams_name = "https://api.opendota.com/api/teams"
        dat = self.__get_json_from_url(url_teams_name)
        # дф с именем команды и ее id
        df_team_id = pd.DataFrame(dat).loc[:,['name', 'team_id']]

        # создать столбцы с именами команд с opendota
        for index in main.index:
            try:
                main.loc[index, 'radiant_name'] = (
                    df_team_id.loc[df_team_id['team_id'] == main.loc[index, 'radiant_team_id'], 'name'].get_values()[0])
            except:
                continue
            try:
                main.loc[index, 'dire_name'] = (
                    df_team_id.loc[df_team_id['team_id'] == main.loc[index, 'dire_team_id'], 'name'].get_values()[0])
            except:
                continue
#         print(main.columns)
        main = main.dropna()
        main['radiant_name'] = main['radiant_name'].apply(self.__reg)
        main['dire_name'] = main['dire_name'].apply(self.__reg)
        main = main.reset_index().drop('index', axis=1)
        return main
    # для преобразования имен команд (убрать лишние символы)
    def __reg(self, x): 
        reg = re.compile('[^-a-zA-Z0-9_. 、]')
        return reg.sub('', x)
    
    def delRepeatedTeamsInMain(self, main):
        # на Opendota в рейтинге команд есть повторяющиеся команды но с разными ID_team
        main = main[main['dire_team_id'] != 5065748]
        main = main[main['radiant_team_id'] != 5065748]
        main = main[main['dire_team_id'] != 2672298]
        main = main[main['radiant_team_id'] != 2672298]
        main = main[main['dire_team_id'] != 5196328]
        main = main[main['radiant_team_id'] != 5196328]
        main = main[main['dire_team_id'] != 2512249]
        main = main[main['radiant_team_id'] != 2512249]
        main = main[main['dire_team_id'] != 2790766]
        main = main[main['radiant_team_id'] != 2790766]
        main = main[main['dire_team_id'] != 5197722]
        main = main[main['radiant_team_id'] != 5197722]
        return main
   # ------- Рейтинг команд по таблице рейтинга -------------------------------------------------------------- 
    def createAndSaveRatingTeamsOnTabelRating(self, main):
        print('Рейтинг команд по таблице рейтинга')
        # вытащить таблицу рейтинга на предыдущий день матча
        def get_rating_table(time_match):
            # работа с датами
            date = time_match - timedelta(1)
            # Открыть json с сайта и выгрузить данные
            url = "https://www.datdota.com/api/ratings?date={}-{}-{}".format(date.day, date.month, date.year)
            dat = self.__get_json_from_url(url)
            data = dat.get('data')
            # создать DF для сохранения
            rating_team_date = pd.DataFrame() 
            # вытащить все команды и сохранить их данные в all_teams
            for i in data:   
                team = get_data_team(i) 
                rating_team_date = pd.concat([rating_team_date, team], ignore_index=True)    
            # очистить имена команд
            rating_team_date['team_Name'] = rating_team_date['team_Name'].apply(self.__reg)
            return rating_team_date
        # создать данные рейтинга команды по мнимальному рейтингу на день соревнований
        def get_min_team_rating(team_name, dire_or_radiant, rating_team_date):
            #взять минимальную команду в рейтинге
            test_min_team_rating = rating_team_date[rating_team_date['current_elo32'] == min(rating_team_date['current_elo32'])]
            test_min_team_rating = test_min_team_rating.drop(['phi_glicko', 'sigma_glicko2'],  axis=1)
            # сменить имя в минимальном рейтиенге
            test_min_team_rating['team_Name'] = team_name
            test_min_team_rating.columns = [dire_or_radiant + '_' + str(col) for col in test_min_team_rating.columns]
            return test_min_team_rating
        # создать мапу с старыми и новыми именами колонок для рейтинга команд
        def name_columns(z1, elo):
            mapa = {}
            for index, key in enumerate(z1.keys()):
                mapa[key] = key + elo
            return mapa
        # вытащить все данные по рейтингу (elo32, elo64, glicko, glicko2) одной команды
        def get_data_team(data):
            ratings = ['elo32', 'elo64', 'glicko', 'glicko2']
            #Создать колонку с именем команды
            team = pd.DataFrame(columns=['team_Name'])
            team['team_Name'] = [data.get('teamName')]

            for rat in ratings:
                current_rating = data.get(rat)
                columns = name_columns(current_rating, '_' + rat)
                df = pd.DataFrame(data.get(rat), index=range(0,1))     
                df.rename(columns=columns, inplace=True)
                team = pd.DataFrame.merge(team, df, left_index=True, right_index=True)
            return team

        df_rating_teams_on_tabel_rating = pd.DataFrame()
        for index in  main.index:
            if index%100 == 0:
                print (index) 
            # вытащить одну строчку (для того чтобы потом добавить в основную таблицу. Пока оставить так, но в принципе можно 
            # уброть переменную one_match)
            one_match = main.loc[[index]]
            # достать дату матча
            date_match =  date.fromtimestamp(one_match['start_time'][index])
            # вытащить таблицу с рейтингами на предыдущий день матча
            rating_team_date = get_rating_table(date_match)

            # имена команд в матче
            radiant_name = one_match['radiant_name'][index]
            dire_name = one_match['dire_name'][index]

            # вытащить команду radiant из рейтинга команд на предыдущий день соревнований
            rating_radiant = rating_team_date[rating_team_date['team_Name'] == radiant_name]
            if rating_radiant.empty == True:
                # если команды нету в списке рейтинга взять данные по команде с минимальным рейтинго elo32
                rating_radiant = get_min_team_rating(radiant_name, 'radiant', rating_team_date)
            else:
                rating_radiant = rating_radiant.drop(['phi_glicko', 'sigma_glicko2'],  axis=1)
                # добавить к названиям столбцов 'radiant'
                rating_radiant.columns = ['radiant_' + str(col) for col in rating_radiant.columns]

            # вытащить команду dire из рейтинга команд на предыдущий денб соревнований
            rating_dire = rating_team_date[rating_team_date['team_Name'] == dire_name]
            if rating_dire.empty == True:
                # если команды нету в списке рейтинга взять данные по команде с минимальным рейтинго elo32
                rating_dire = get_min_team_rating(dire_name, 'dire', rating_team_date)
            else:
                rating_dire = rating_dire.drop(['phi_glicko', 'sigma_glicko2'],  axis=1)
                # добавить к названиям столбцов 'dire'
                rating_dire.columns = ['dire_' + str(col) for col in rating_dire.columns]

            #соединить в одну строчку данные матча и данные с рейтинга каждой команды если присутсвуют данные по команде
            rating_teams = pd.merge(one_match, rating_radiant,  left_on='radiant_name', right_on='radiant_team_Name')
            rating_teams = pd.merge(rating_teams, rating_dire, left_on='dire_name', right_on='dire_team_Name')
            rating_teams = rating_teams.drop(['dire_team_Name', 'radiant_team_Name'], axis=1)
            # Если повторяющиеся команды  то длина будет два. НЕ ДОБАВЛЯТЬ ПОВТОРЯЮЩИЕСЯ КОМАНДЫ
            if len(rating_teams) == 1:
                df_rating_teams_on_tabel_rating = pd.concat([df_rating_teams_on_tabel_rating, rating_teams])
        # match_rating_teams = match_rating_teams.reset_index().drop('index', axis=1)
        df_rating_teams_on_tabel_rating.to_csv('../tabel/table from Datdota/Rating teams/' +
                                    'PREMIUM on {} to {} (PreDay).csv'.format(self.day_first_for_saving_in_file, 
                                                                              self.day_end_for_saving_in_file))
    # ------- Рейтинг команд по ссылке на данные команды ----------------------------------------------------------
    def createAndSaveGlickoRatingTeamsOnLinkTeam(self, main):
        print('Рейтинг команд по ссылке на данные команды')
        def get_current_rating_teams(date_match, team_id, radiant_or_dire):
            date_rating = date_match
            date_rating_7day_ago = date_rating - timedelta(7)
            # Достать данные по рейтингу для редиант на текущий день и семь дней назад
            url = 'http://www.datdota.com/api/teams/{}/ratings?date={}-{}-{}'.format(
                                        team_id, date_rating.year, date_rating.month, date_rating.day )
            # выгрзить json с предыдущей ссылки и создать ДФ
            dat = self.__get_json_from_url(url)
            data = pd.DataFrame(dat.get('data'))

            url_7day_ago = 'http://www.datdota.com/api/teams/{}/ratings?date={}-{}-{}'.format(
                    team_id, date_rating_7day_ago.year, date_rating_7day_ago.month, date_rating_7day_ago.day )
            # выгрзить json с предыдущей ссылки и создать ДФ
            dat_7day_ago = self.__get_json_from_url(url_7day_ago)
            data_7day_ago = pd.DataFrame(dat_7day_ago.get('data'))
            # если нету данных 7 дней назад
            try:
                # бывает что не посчитан рейтинг для текущей недели и тогда взять 14 дней назад
                if data_7day_ago.loc['startPeriod', 'GLICKO_1'] == data.loc['startPeriod', 'GLICKO_1']:
                    date_rating_7day_ago = date_rating - timedelta(14)
                    url_7day_ago = 'http://www.datdota.com/api/teams/{}/ratings?date={}-{}-{}'.format(
                            team_id, date_rating_7day_ago.year, date_rating_7day_ago.month, date_rating_7day_ago.day )
                    # выгрзить json с предыдущей ссылки и создать ДФ
                    dat_7day_ago = self.__get_json_from_url(url_7day_ago)
                    data_7day_ago = pd.DataFrame(dat_7day_ago.get('data'))
            except:
                data_7day_ago = pd.DataFrame([[0,0]], columns=['GLICKO_1', 'GLICKO_2'], index=['rating'])
            try:
                team_ratin_df_allData = pd.DataFrame()
                team_ratin_df_allData.loc[0, radiant_or_dire + '_mu_glicko'] = data.loc['mu', 'GLICKO_1']
                team_ratin_df_allData.loc[0, radiant_or_dire + '_rating_glicko'] = data.loc['rating', 'GLICKO_1']
                team_ratin_df_allData.loc[0, radiant_or_dire + '_ratingSevenDaysAgo_glicko'] = data_7day_ago.loc['rating', 'GLICKO_1']
                team_ratin_df_allData.loc[0, radiant_or_dire + '_sigma_glicko'] = data.loc['sigma', 'GLICKO_1']

                team_ratin_df_allData.loc[0, radiant_or_dire + '_mu_glicko2'] = data.loc['mu', 'GLICKO_2']
                team_ratin_df_allData.loc[0, radiant_or_dire + '_phi_glicko2'] = data.loc['phi', 'GLICKO_2']
                team_ratin_df_allData.loc[0, radiant_or_dire + '_rating_glicko2'] = data.loc['rating', 'GLICKO_2']
                team_ratin_df_allData.loc[0, radiant_or_dire + '_ratingSevenDaysAgo_glicko2'] = data_7day_ago.loc['rating', 'GLICKO_2']    
            except:
                team_ratin_df_allData = pd.DataFrame([[0,0,0,0,0,0,0,0]], 
                        columns=[radiant_or_dire + x for x in ['_mu_glicko', '_rating_glicko', 
                                                '_ratingSevenDaysAgo_glicko', '_sigma_glicko', 
                                    '_mu_glicko2', '_phi_glicko2', '_rating_glicko2', '_ratingSevenDaysAgo_glicko2', ]])
            return(team_ratin_df_allData)

        df_glicko_rating_teams_on_links = pd.DataFrame()
        for index in  main.index:
            if index%100 == 0:
                print (index) 
            # вытащить одну строчку (для того чтобы потом добавить в основную таблицу. Пока оставить так, но в принципе можно 
            # уброть переменную one_match)
            one_match = main.loc[[index]]
            # достать дату матча
            date_match =  date.fromtimestamp(one_match['start_time'][index]) - timedelta(1)

            # id команд в матче, иногда бывает что нет id 
            try:
                radiant_id = int(one_match['radiant_team_id'][index])
            except:
                radiant_id = 0
            try:
                dire_id = int(one_match['dire_team_id'][index])
            except:
                dire_id = 0

            rating_radiant = get_current_rating_teams(date_match, radiant_id, 'radiant')
            rating_dire = get_current_rating_teams(date_match, dire_id, 'dire')
            #соединить в одну строчку данные матча и данные с рейтинга каждой команды если присутсвуют данные по команде
            rating_teams = pd.merge(rating_radiant, rating_dire, left_index=True, right_index=True)
            rating_teams['match_id'] = one_match['match_id'].values[0]
            # Если повторяющиеся команды  то длина будет два. НЕ ДОБАВЛЯТЬ ПОВТОРЯЮЩИЕСЯ КОМАНДЫ
            if len(rating_teams) == 1:
                df_glicko_rating_teams_on_links = pd.concat([df_glicko_rating_teams_on_links, rating_teams])
            df_glicko_rating_teams_on_links = df_glicko_rating_teams_on_links.reset_index().drop('index', axis=1)
            df_glicko_rating_teams_on_links.to_csv('../tabel/table from Datdota/Rating teams/' + 
                        'Rating Glicko on {} to {} (PreDay).csv'.format(self.day_first_for_saving_in_file, 
                                                                        self.day_end_for_saving_in_file))
    # ------- KDA для героев в матче ----------------------------------------------------------
    def createAndSaveKdaHeroes(self, main, days_ago=0, pro_or_all_teams='All', threshold='20'):
        print('KDA и все другие данные для героев в матче')
        columns = ['hero', 'kills', 'deaths', 'assists', 'kda', 'avgKal', 'gpm', 'xpm', 'lastHits', 'denies', 'level',
                   'heroDamage', 'towerDamage', 'heroHealing', 'goldSpent']
        # создать основной массив, где будут записаны все матчи (id матча и rda героя)
        df_basick_peromances_heroes = pd.DataFrame()

        # создать список названий колонок всех героев
        all_her = main.loc[:,'radiant_H1':'dire_H5'].columns
        
        tier = self.__checkTierTeams(pro_or_all_teams)
        
        for index in main.index:
            if index%100 == 0:
                print (index)
            # ДФ для соединения всех герове матча в один ДФ 
            df_heroe_match = pd.DataFrame()
            # дата матча
            date_match = date.fromtimestamp(main['start_time'][index])
            # предыдущий день
            date_match =  date_match - timedelta(1)
            if days_ago == 0:
                url_heroes =('http://www.datdota.com/api/heroes/performances?' + self.PATCH +
                    '&winner=either&after=01%2F01%2F2011' + 
                    '&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year) + 
                    '&duration=0%3B200&duration-value-from=0&duration-value-to=200&{}'.format(tier) + 
                    '&valve-event=does-not-matter&threshold={}'.format(threshold))
            else:
                several_day_ago = date_match - timedelta(days_ago)
                url_heroes =('http://www.datdota.com/api/heroes/performances?' + self.PATCH +
                    '&winner=either&after={}%2F{}%2F{}'.format(several_day_ago.day, several_day_ago.month, several_day_ago.year) + 
                    '&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year) + 
                    '&duration=0%3B200&duration-value-from=0&duration-value-to=200&{}'.format(tier) + 
                    '&valve-event=does-not-matter&threshold={}'.format(threshold))
            # выгрзить json с предыдущей ссылки
            dat = self.__get_json_from_url(url_heroes).get('data')
            df_data_tabel_for_heroes = pd.DataFrame(dat)#, columns=columns)
            for her in all_her:
                # вытащить id героя
                id_heroe = main[her][index]

                # создать массив с данными 
                array = df_data_tabel_for_heroes[df_data_tabel_for_heroes['hero'] == id_heroe].values
                # создать название колонок для определнного героя
                col = [her + '_' + c for c  in df_data_tabel_for_heroes.columns]
                # ДФ для героя по матчу
                df_heroe = pd.DataFrame(array, columns=col)
                df_heroe_match = pd.merge(df_heroe_match, df_heroe, 
                                                       left_index=True, right_index=True, how='outer')
                df_heroe_match['match_id'] = main.loc[index, 'match_id']
            df_basick_peromances_heroes = pd.concat([df_basick_peromances_heroes, df_heroe_match])
        df_basick_peromances_heroes = df_basick_peromances_heroes.reset_index().drop('index', axis=1)
        df_basick_peromances_heroes = df_basick_peromances_heroes.fillna(0)
        if days_ago == 0:
            df_basick_peromances_heroes.to_csv('../tabel/table from Datdota/KDA/Heroes/'+
                        'KDA heroes on {} to {} (6.88+, {}, more {}).csv'.format(self.day_first_for_saving_in_file, 
                                                                            self.day_end_for_saving_in_file,
                                                                                pro_or_all_teams, threshold))
        else:
            df_basick_peromances_heroes.to_csv('../tabel/table from Datdota/KDA/Heroes/{}day_ago/'.format(days_ago)+
                        'KDA heroes on {} to {} ({}day_ago, {}, more {}).csv'.format(self.day_first_for_saving_in_file, 
                                                                                self.day_end_for_saving_in_file, 
                                                                                str(days_ago), 
                                                                                pro_or_all_teams, threshold))
            
    # ------- Head-to-Head ----------------------------------------------------------
    def createAndSaveHeadToHead(self, main, pro_or_all_teams='All', threshold='20'):
        """Contrpick Heroes"""
        print('Head-to-Head')
        def elo_heroes_vs_enemies(main, index, columns_heroes, columns_enemies, df_elo_herVsEne, df_head_to_head_elo_heroes):
            """Добавить в df_head_to_head_elo_heroes суммарный показатель elo для героя vs всх врагов"""
            # две переменные для записи суммарного elo каждой команды
            for her in columns_heroes:
                hero_elo = 0
                # вытащить id героя
                id_heroe = main[her][index]
                # суммировать elo героя против героев противника
                for her_enemy in columns_enemies:
                    id_heroe_enemy = main[her_enemy][index]
                    try:
                        elo =  df_elo_herVsEne['shift'][df_elo_herVsEne['hero'] == 
                                                      id_heroe][df_elo_herVsEne['againstHero'] == id_heroe_enemy].item()
                    except:
                        elo=0
                    hero_elo += elo
                # записать в основной ДФ elo по каждому герою
                df_head_to_head_elo_heroes.loc[index, her + '_elo_vs_enemies'] =  hero_elo 

        # создать основной массив, где будут записаны суммарное elo каждого егроя относительно всех героев противника
        df_head_to_head_elo_heroes = pd.DataFrame()#main['match_id']
        # создать список названий колонок  героев radiant
        all_her_rad = main.loc[:,'radiant_H1':'radiant_H5'].columns
        # создать список названий колонок  героев radiant
        all_her_dir = main.loc[:,'dire_H1':'dire_H5'].columns
        
        tier = self.__checkTierTeams(pro_or_all_teams)
        
        for index in main.index:
            if index % 100 == 0:
                print (index)
            # достать дату матча и отнять один день
            date_match = date.fromtimestamp(main['start_time'][index])
            date_match = date_match - timedelta(1)    
            # создать cылку для предыдущего дня по контрпикам  за все время существования DatDota
            url_heroes_team = ('http://www.datdota.com/api/heroes/head-to-head-elo?{}'.format(tier) +
                               '&valve-event=does-not-matter&threshold={}'.format(threshold) + self.PATCH +
                               '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81' +
                               '&patch=6.80&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74'+
                               '&winner=either&after=01%2F01%2F2011' +
                        '&before={}%2F{}%2F{}&duration=0%3B200&'.format(date_match.day, date_match.month, date_match.year) +
                        'duration-value-from=0&duration-value-to=200') 
            # выгрзить json с предыдущей ссылки и создать ДФ
            dat = self.__get_json_from_url(url_heroes_team)
            df_elo_herVsEne = pd.DataFrame(dat.get('data'))

            # добавить в мейн таблицу данные сначала по ело героям рединт против дире, а затем наоборот
            elo_heroes_vs_enemies(main, index, all_her_rad, all_her_dir, df_elo_herVsEne, df_head_to_head_elo_heroes)
            elo_heroes_vs_enemies(main, index, all_her_dir, all_her_rad, df_elo_herVsEne, df_head_to_head_elo_heroes)
        df_head_to_head_elo_heroes['match_id'] = main['match_id']  
        
        self.df_head_to_head_elo_heroes = df_head_to_head_elo_heroes
        df_head_to_head_elo_heroes.to_csv('../tabel/table from Datdota/Heah-to-head Contrpicks/'+
                               'data from 6.74-last. on {} to {} (All time, {}, more {}).csv'.format(
                                   self.day_first_for_saving_in_file, self.day_end_for_saving_in_file,
                                   pro_or_all_teams, threshold))
        
    def __checkTierTeams(self, pro_or_all_teams):
        if pro_or_all_teams == 'All':
            tier = 'tier=1&tier=2&tier=3'            
        elif pro_or_all_teams == 'Pro':
            tier = 'tier=1'
        return tier
    # ------- Метовые герои AvgELo для одного и для пары героев ---------------------------------------------
    def createAndSaveAvgeloForOneHero(self, main, days_ago=60, pro_or_all_teams='All', threshold='20'):
        """Meta за последние время, какие показатели у одного героя. По умолчанию за 2 месяца (60 дней)"""
        print('AvgElo (Meta) for one heroes')
        # создать основной ДФ, где будут записаны все матчи (id матча и rda героя)
        df_AvgElo_heroes = pd.DataFrame()
        df_AvgElo_for_two_heroes_in_two_teams = pd.DataFrame()

        # создать список названий колонок всех героев
        all_her = main.loc[:,'radiant_H1':'dire_H5'].columns
       
        tier = self.__checkTierTeams(pro_or_all_teams)
        
        for index in main.index:
            if index % 100 == 0:
                print (index)
            # ДФ для соединения всех герове матча в один ДФ 
            df_heroe_match = pd.DataFrame()
            date_match = date.fromtimestamp(main['start_time'][index])
            date_match =  date_match - timedelta(1)
            # создать дату столько то дней назад назад от даты матча
            several_day_ago = date_match - timedelta(days_ago)
            # создать ссылку с данными по Avg.Elo для двух предыдущих месяцев игры
            url = ('http://www.datdota.com/api/heroes/elo?{}'.format(tier) +
                '&valve-event=does-not-matter&threshold={}'.format(threshold) + self.PATCH + 
                '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81&patch=6.80' + 
                '&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74'+
                '&winner=either'+
                '&after={}%2F{}%2F{}'.format(several_day_ago.day, several_day_ago.month, several_day_ago.year) + 
                '&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year) + 
                '&duration=0%3B200&duration-value-from=0&duration-value-to=200')
            # выгрузить все с сайта и создать ДФ
            dat = self.__get_json_from_url(url)
            df_url = pd.DataFrame(dat.get('data'))
            # создать ДФ для одного и пары героев за 2 предыдущих месяца
            df_data_tabel_for_heroes, df_data_tabel_for_two_heroes = self.__get_df_avgElo_heroes(date_match, df_url)

            for her in all_her:
                # вытащить id героя
                id_hero = main[her][index]

                # вытащить avg elo для данного героя
                avgElo_hero = df_data_tabel_for_heroes.loc[(index for index, x in enumerate(
                                                    df_data_tabel_for_heroes['heroes']) if x == [id_hero]),'eloShift']

                # проверить есть ли герой
                try:
                    avgElo_hero = float(avgElo_hero)
                except:
                    avgElo_hero = 0
                # ДФ для avgELo героя по матчу
                df_heroe = pd.DataFrame([avgElo_hero], columns=[her + '_AvgElo'])
                df_heroe_match = pd.merge(df_heroe_match, df_heroe, left_index=True, right_index=True, how='outer')
                df_heroe_match['match_id'] = main.loc[index, 'match_id']
            df_AvgElo_heroes = pd.concat([df_AvgElo_heroes, df_heroe_match])

        # df_AvgElo_heroes['mathc_id'] = main['match_id']
        df_AvgElo_heroes = df_AvgElo_heroes.reset_index().drop('index', axis=1)
        df_AvgElo_heroes.to_csv('../tabel/table from Datdota/AvgElo Meta and Signatures Heroes/'+
                            'Meta on {} to {} ({}day_ago, {}, more {}).csv'.format(self.day_first_for_saving_in_file, 
                                                                                    self.day_end_for_saving_in_file, 
                                                                                    str(days_ago), 
                                                                                    pro_or_all_teams, threshold))
    # вытащить ДФы для одного, пары, тройки героев из сайта по дате
    def __get_df_avgElo_heroes(self, day_match, df):
        # создать ДФ для одного героя, пары и тройки
        df_one = df.loc[(index for index, x in enumerate(df['heroes']) if len(x) == 1), :]  
        df_one = df_one.reset_index().drop('index', axis=1)
        df_double = df.loc[(index for index, x in enumerate(df['heroes']) if len(x) == 2), :]  
        df_double = df_double.reset_index().drop('index', axis=1)
    #     df_triple = df.loc[(index for index, x in enumerate(df['heroes']) if len(x) == 3), :]  
        return df_one, df_double#, df_triple

    def createAndSaveAvgeloForTwoHeroes(self, main, days_ago=60, pro_or_all_teams='Pro', threshold='8'):
        """Meta за последние время, какие показатели у ПАРЫ героев. По умолчанию за 2 месяца (60 дней)"""
        print('AvgElo (Meta) for two heroes')
        # вытащить avgElo для двух героев, по их номеру
        def AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, first_H, second_H):
            a = what_team + first_H
            b = what_team + second_H
            # Если нету связки то поставить 0
            try:
                avgElo = df_data_tabel_for_two_heroes.loc[(ind for ind, x in enumerate(df_data_tabel_for_two_heroes['heroes'])
                        if (arr_heroes[a] in x and arr_heroes[b] in x)),'eloShift'].values[0]
            except:
                avgElo = 0
            return (avgElo)

        # создать ДФ с avgElo по парам героев
        def get_df_AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, dire_or_radiant):
            if dire_or_radiant == 'dire':
                what_team = 5
            else:
                what_team = 0
             # вытащить avgElo для связки героя с другими по команде
            avgElo_hero1_2 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 0, 1)
            avgElo_hero1_3 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 0, 2)
            avgElo_hero1_4 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 0, 3)
            avgElo_hero1_5 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 0, 4)
            avgElo_hero2_3 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 1, 2)
            avgElo_hero2_4 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 1, 3)
            avgElo_hero2_5 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 1, 4)
            avgElo_hero3_4 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 2, 3)
            avgElo_hero3_5 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 2, 4)
            avgElo_hero4_5 = AvgElo_for_two_heroes_in_teams(arr_heroes, df_data_tabel_for_two_heroes, what_team, 3, 4)
            arr = []
            arr.append(avgElo_hero1_2); arr.append(avgElo_hero1_3); arr.append(avgElo_hero1_4); arr.append(avgElo_hero1_5);
            arr.append(avgElo_hero2_3); arr.append(avgElo_hero2_4); arr.append(avgElo_hero2_5);
            arr.append(avgElo_hero3_4); arr.append(avgElo_hero3_5);
            arr.append(avgElo_hero4_5);
            # Создать ДФ с данными для пар героев в команде
            df_avgElo_for_two_heroes = pd.DataFrame([arr], columns=[dire_or_radiant + '_' + c for c in [
                                                                                            '1_2','1_3','1_4','1_5',
                                                                                            '2_3','2_4','2_5',
                                                                                            '3_4','3_5',
                                                                                            '4_5']])
            return df_avgElo_for_two_heroes

        # создать основной ДФ, где будут записаны все матчи (id матча и rda героя)
        df_AvgElo_heroes = pd.DataFrame()
        df_AvgElo_for_two_heroes_in_two_teams = pd.DataFrame()
        # создать список названий колонок всех героев
        all_her = main.loc[:,'radiant_H1':'dire_H5'].columns
        
        tier = self.__checkTierTeams(pro_or_all_teams)
        
        for index in main.index:
            if index % 100 == 0:
                print (index)
            # ДФ для соединения всех герове матча в один ДФ 
            df_heroe_match = pd.DataFrame()
            # дата матча
            date_match = date.fromtimestamp(main['start_time'][index])
            # предыдущий день
            date_match =  date_match - timedelta(1)
            # создать дату два месяца назад от даты матча
            several_day_ago = date_match - timedelta(days_ago)
            # создать ссылку с данными по Avg.Elo для двух предыдущих месяцев игры
            url = ('http://www.datdota.com/api/heroes/elo?{}'.format(tier) +
                '&valve-event=does-not-matter&threshold={}'.format(threshold) + self.PATCH + 
                '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81&patch=6.80' + 
                '&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74'+
                '&winner=either'+
                '&after={}%2F{}%2F{}'.format(several_day_ago.day, several_day_ago.month, several_day_ago.year) + 
                '&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year) + 
                '&duration=0%3B200&duration-value-from=0&duration-value-to=200')
            # выгрузить все с сайта и создать ДФ
            dat = self.__get_json_from_url(url)
            df_url = pd.DataFrame(dat.get('data'))
            # создать ДФ для одного и пары героев за 2 предыдущих месяца
            df_data_tabel_for_heroes, df_data_tabel_for_two_heroes = self.__get_df_avgElo_heroes(date_match, df_url)
            # Массив героев в матче 
            arr_heroes_in_match = main.loc[index,'radiant_H1':'dire_H5'].values
            # Создать два ДФ для редиант и даер по парным связкам AvgElo
            rad = get_df_AvgElo_for_two_heroes_in_teams(arr_heroes_in_match, df_data_tabel_for_two_heroes, 'radiant')
            di =  get_df_AvgElo_for_two_heroes_in_teams(arr_heroes_in_match, df_data_tabel_for_two_heroes, 'dire')
            df_AvgElo_for_two_heroes_in_match = pd.merge(rad, di, 
                                                           left_index=True, right_index=True, how='outer')
            df_AvgElo_for_two_heroes_in_match['match_id'] = main.loc[index, 'match_id'] 
            df_AvgElo_for_two_heroes_in_two_teams = pd.concat([
                                        df_AvgElo_for_two_heroes_in_two_teams, df_AvgElo_for_two_heroes_in_match ])

        df_AvgElo_for_two_heroes_in_two_teams = df_AvgElo_for_two_heroes_in_two_teams.reset_index().drop('index', axis=1)
        df_AvgElo_for_two_heroes_in_two_teams.to_csv('../tabel/table from Datdota/'+
            'AvgElo Meta and Signatures Heroes/Meta AvgElo Couples/'+
            'Meta couples heroes on {} to {} ({}day_ago, {}, more {}).csv'.format(self.day_first_for_saving_in_file, 
                                                                    self.day_end_for_saving_in_file, 
                                                                    str(days_ago), 
                                                                    pro_or_all_teams, threshold))
    # ------- Signatures & KDA для игрока ---------------------------------------------
    def createAndSaveSignatureAndKdaForPlayers(self, main, pro_or_all_teams='All', threshold='5'):
        print('Signatures and KDA for players')
        def get_players_heroes(df_heroe_match, radiant_or_dire, index, pro_or_all_teams, threshold):
            """Вытащить данные по героям для игроков (elo, gpm, xpm, kda). 
               Передается DF в который добаляются все данные по одному матчу"""
            def get_df_AvgElo_heroes_player(player, index, tier, threshold):
                # дата матча
                date_match = date.fromtimestamp(main['start_time'][index])
                date_match = date_match - timedelta(1)
                # создать ДФ для соло героев за все время игр игрока (сигнатурки)
                url = ('http://www.datdota.com/api/players/hero-combos?players={}'.format(player) +
                self.PATCH +
                '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81'+
                '&patch=6.80&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74&winner=either'+
                '&after=01%2F01%2F2011&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year)+
                '&duration=0%3B200&duration-value-from=0&duration-value-to=200&{}'.format(tier) +
                '&valve-event=does-not-matter&threshold={}'.format(threshold))
                # выгрузить все с сайта и создать ДФ
                try:
                    dat = self.__get_json_from_url(url)
                except:
                    dat = {'data':[]}
                df_url = pd.DataFrame(dat.get('data'))
                return df_url
            
            tier = self.__checkTierTeams(pro_or_all_teams)
            
            for i in range(1, 6):
                # вытащить id героя
                id_hero = main[radiant_or_dire + '_H' + str(i)][index]
                # вытащить id игрока
                id_player = main[radiant_or_dire + '_P' + str(i)][index]
                # создать ДФ c avgElo для игрока по ДАТЕ ИГРЫ
                df_player = get_df_AvgElo_heroes_player(int(id_player), index, pro_or_all_teams, threshold)
                try:
                    total = df_player['total'][df_player['hero'] == id_hero].values[0]
                    winrate = df_player['winrate'][df_player['hero'] == id_hero].values[0]
                    kills = df_player['kills'][df_player['hero'] == id_hero].values[0]
                    deaths = df_player['deaths'][df_player['hero'] == id_hero].values[0]
                    assists = df_player['assists'][df_player['hero'] == id_hero].values[0]
                    elo = df_player['eloShift'][df_player['hero'] == id_hero].values[0]
                    gpm = df_player['gpm'][df_player['hero'] == id_hero].values[0]
                    xpm = df_player['xpm'][df_player['hero'] == id_hero].values[0]
                    kda = df_player['kda'][df_player['hero'] == id_hero].values[0] 
                    lastHits = df_player['lastHits'][df_player['hero'] == id_hero].values[0] 
                    denies = df_player['denies'][df_player['hero'] == id_hero].values[0] 
                except:
                    total=0; winrate=0; kills=0; deaths=0; assists=0; elo=0; gpm=0;  xpm=0; kda=0; lastHits=0; denies=0;
                # ДФ для героя игрока по матчу
                df_heroe = pd.DataFrame([[total, winrate, kills, deaths, assists, elo, gpm, xpm, kda, lastHits, denies]], 
                                    columns=[radiant_or_dire + '_P' + str(i) + '_totalGames',
                                            radiant_or_dire + '_P' + str(i) + '_winrate',
                                            radiant_or_dire + '_P' + str(i) + '_kills',
                                            radiant_or_dire + '_P' + str(i) + '_deaths',
                                            radiant_or_dire + '_P' + str(i) + '_assists',
                                            radiant_or_dire + '_P' + str(i) + '_eloShift',
                                            radiant_or_dire + '_P' + str(i) + '_gpm',
                                            radiant_or_dire + '_P' + str(i) + '_xpm',
                                            radiant_or_dire + '_P' + str(i) + '_kda',
                                            radiant_or_dire + '_P' + str(i) + '_lastHits',
                                            radiant_or_dire + '_P' + str(i) + '_denies'])
                df_heroe_match = pd.merge(df_heroe_match, df_heroe, left_index=True, right_index=True, how='outer')
            return df_heroe_match

        # создать основной ДФ, где будут записаны все матчи (id матча и rda героя)
        df_heroes_players_elo_gpm_xpm_kda = pd.DataFrame()
        # создать список названий колонок  героев radiant
        all_her_rad = main.loc[:,'radiant_H1':'radiant_H5'].columns
        # создать список названий колонок  героев radiant
        all_her_dir = main.loc[:,'dire_H1':'dire_H5'].columns
        # создать список названий колонок  игроков radiant
        all_play_rad = main.loc[:,'radiant_P1':'radiant_P5'].columns
        # создать список названий колонок  игроков radiant
        all_play_dir = main.loc[:,'dire_P1':'dire_P5'].columns
        for index in main.index:
            if index % 100 == 0:
                print (index)
            # ДФ для соединения всех герове radiant & dire матча в один ДФ 
            df_heroe_match = pd.DataFrame()
            df_heroe_match = get_players_heroes(df_heroe_match, 'radiant', index, pro_or_all_teams, threshold)
            df_heroe_match = get_players_heroes(df_heroe_match, 'dire', index, pro_or_all_teams, threshold)
            df_heroe_match['match_id'] = main.loc[index, 'match_id']
            df_heroes_players_elo_gpm_xpm_kda = pd.concat([df_heroes_players_elo_gpm_xpm_kda, df_heroe_match])   
        df_heroes_players_elo_gpm_xpm_kda = df_heroes_players_elo_gpm_xpm_kda.reset_index().drop('index', axis=1)
        df_heroes_players_elo_gpm_xpm_kda.to_csv('../tabel/table from Datdota/KDA/Players/'+
                    'KDA Players on hero {} to {} (All time, {}, more {}).csv'.format(self.day_first_for_saving_in_file, 
                                                                                        self.day_end_for_saving_in_file,
                                                                                        pro_or_all_teams, threshold))   
    # ------- Predict on rating Teams ---------------------------------------------
    def createAndSavePredictionForRatingTeams(self, main):
        print("DF for Prediction on Rating Teams")
        # Общая функция для удобного обучения и предсказания на контрольных данных
        def get_main_df_for_predict(df_rating_teams_Premium):
            # Создание основного ДФ 
            # Соединение всех данных в один ДФ
            main = df_rating_teams_Premium

            # удаление не нужных колонок для обучения
            main = main.drop(['match_id', 'start_time', 'radiant_team_id', 'radiant_score', 'dire_team_id',
                       'dire_score', 'radiant_name', 'dire_name','league_name'], axis=1)
            main = main.drop(main.loc[:, 'radiant_H1' : 'dire_P5'], axis=1)

            # # Оставляю только важные фичи, убираю из рейтинга команд ело32 и ело64
            main = main.drop(main.loc[:, 'radiant_current_elo32':'radiant_thirtyDayAvg_elo64'], axis=1)
            main = main.drop(main.loc[:, 'dire_current_elo32':'dire_thirtyDayAvg_elo64'], axis=1)
            print (len(main))
            #  Заполнить или удалить NaN и добаить коллонку с предсказаниями, обучеными ранее        
            # убрать пустые ячейки
            print(main)
            main = main.dropna()
            print(len(main), "After dropna")
            # Для рейтинга команд 
            print(main)
            main['mu_glicko'] = main['radiant_mu_glicko'] -  main['dire_mu_glicko']
            main['rating_glicko'] = main['radiant_rating_glicko'] -  main['dire_rating_glicko']
            main['ratingSevenDaysAgo_glicko'] = main['radiant_ratingSevenDaysAgo_glicko'] -  main['dire_ratingSevenDaysAgo_glicko']
            main['mu_glicko2'] = main['radiant_mu_glicko2'] -  main['dire_mu_glicko2']
            main['phi_glicko2'] = main['radiant_phi_glicko2'] -  main['dire_phi_glicko2'] 
            # Почему-то иногда менятеся порядок колоно из исходных данных и поэтому нужно создать правильный порядок
            main = main[['radiant_win', 'radiant_mu_glicko', 'radiant_rating_glicko', 'radiant_ratingSevenDaysAgo_glicko', 
                         'radiant_mu_glicko2', 'dire_mu_glicko', 'dire_rating_glicko', 'dire_ratingSevenDaysAgo_glicko', 
                         'dire_sigma_glicko', 'dire_mu_glicko2', 'dire_ratingSevenDaysAgo_glicko2', 'mu_glicko', 
                         'rating_glicko', 'ratingSevenDaysAgo_glicko', 'mu_glicko2', 'phi_glicko2']]
            return main

        XGB = pickle.load(open('../Work/Xgboost_model_predict_rating_teams_without_elo.sav', 'rb'))

        # дф с матчами и рейтингом каждой команды с 
        df_rating_teams_Premium_contr = pd.read_csv('../tabel/table from Datdota/Rating teams/'+
                                              'PREMIUM on {} to {} (PreDay).csv'.format(
                                                                      self.day_first_for_saving_in_file, 
                                                                      self.day_end_for_saving_in_file,), index_col=0)

        contr = get_main_df_for_predict(df_rating_teams_Premium_contr)
        # Создание контрольной выборки
        # Cделать обучающие данные и ответы
        X_contr = contr.drop(['radiant_win'], axis=1)
        y_contr = contr['radiant_win']

        # СДЕЛАТЬ 1 или 0 вместо true false
        y_contr = y_contr.astype(int)
        print(classification_report(y_contr, XGB.predict(X_contr), target_names=['dire_win', 'radiant_win']))
        gb_auc = metrics.roc_auc_score(y_contr, XGB.predict_proba(X_contr)[:,1])
        print('AUC для градиентного бустинга - {:.3f}'.format(gb_auc))
        # Создать и сохранить фичу с предсказаниями по алгоритму, обученому на рейтинге команд
        df_pedict_for_rating_teams = pd.DataFrame(XGB.predict_proba(X_contr)[:,1:], columns=['Predict'])
        df_pedict_for_rating_teams['match_id'] = df_rating_teams_Premium_contr['match_id'].reset_index().drop(
                                                                                                        'index', axis=1)
        df_pedict_for_rating_teams.to_csv('../tabel/table from Datdota/Rating teams/'+
                                   'Predict for rating teams on {} to {}.csv'.format(self.day_first_for_saving_in_file, 
                                                                            self.day_end_for_saving_in_file,))
    # ------- Тип Атаки и тиа героев в матче ---------------------------------------------
    def createAndSaveTypeAtackOfHeroesAndTypeHeroes(self, main):
        """Пока не используется в предсказательных моделях, но необходимо собирать данные тоже, 
            так как может пригодиться в будущем."""
        print("Тип Атаки и тип героев")
        # Прочитать файл с героями
        heroes = pd.read_csv('../All_heroes.csv').drop(['id.1'], axis=1)
        # Создвание списка имен героев и списка имен команд и объединение его
        name_heroes = heroes['localized_name'].values
        columns = ['attac_type1','Disabler1','Nuker1','Carry1','Initiator1','Escape1','Durable1','Support1','Pusher1','Jungler1',
                   'attac_type2','Disabler2','Nuker2','Carry2','Initiator2','Escape2','Durable2','Support2','Pusher2','Jungler2',
                   'attac_type3','Disabler3','Nuker3','Carry3','Initiator3','Escape3','Durable3','Support3','Pusher3','Jungler3',
                   'attac_type4','Disabler4','Nuker4','Carry4','Initiator4','Escape4','Durable4','Support4','Pusher4','Jungler4',
                   'attac_type5','Disabler5','Nuker5','Carry5','Initiator5','Escape5','Durable5','Support5','Pusher5','Jungler5',
                   'attac_type6','Disabler6','Nuker6','Carry6','Initiator6','Escape6','Durable6','Support6','Pusher6','Jungler6',
                   'attac_type7','Disabler7','Nuker7','Carry7','Initiator7','Escape7','Durable7','Support7','Pusher7','Jungler7',
                   'attac_type8','Disabler8','Nuker8','Carry8','Initiator8','Escape8','Durable8','Support8','Pusher8','Jungler8',
                   'attac_type9','Disabler9','Nuker9','Carry9','Initiator9','Escape9','Durable9','Support9','Pusher9','Jungler9',
             'attac_type10','Disabler10','Nuker10','Carry10','Initiator10','Escape10','Durable10','Support10','Pusher10','Jungler10']

        list_scripts = ['Disabler', 'Nuker', 'Carry', 'Initiator', 'Escape', 'Durable',
                        'Support', 'Pusher', 'Jungler']

        # функция для перевода в бинарное состояние типа атаки
        def atac(type_at):
            if type_at == 'Melee':
                return 0
            else:
                return 1
        # df в который записыватеся пик команда с росписью кажого героя    
        df_script_her = pd.DataFrame(columns=columns)

        for index in main.index:
            if index % 100 == 0:
                print (index)
            # для radiant
            for i in range(1,6):
                id_her = main['radiant_H' + str(i)].loc[index]
                df_script_her.loc[index, ('attac_type' + str(i))] = atac(heroes['attack_type'][heroes['id'] == id_her].item())
                for col in list_scripts:
                    sc = heroes[col][(heroes['id'] == id_her)].item()
                    df_script_her.loc[index, (col + str(i))] = sc
            # для dire
            for i in range(1,6):
                id_her = main['dire_H' + str(i)].loc[index]
                df_script_her.loc[index, ('attac_type' + str(i+5))] = atac(heroes['attack_type'][heroes['id'] == id_her].item())
                for col in list_scripts:
                    sc = heroes[col][(heroes['id'] == id_her)].item()
                    df_script_her.loc[index, (col + str(i+5))] = sc      
        df_script_her['match_id'] = main['match_id']
        df_script_her.to_csv('../tabel/table from Datdota/Features carry, support, necker/'+
                         'PREMIUM on {} to {}.csv'.format(self.day_first_for_saving_in_file, 
                                                                    self.day_end_for_saving_in_file))
   # ------- KDA и Elo у игрока за послдние несколько дней (Его форма и подготовка) ------------------------------
    def createAndSaveKdaAndEloshiftPlayersForLastDays(self, main, days_ago=7, pro_or_all_teams='All', threshold='1'):
        """Как игрок играет в псоледнее время (Его нынешняя форма)"""
        # вытащить таблицу с elo героев  по каждому игроку
        def getDfPlayerDaysAgo(player, index, days_ago, threshold):
            date_match = date.fromtimestamp(main['start_time'][index])
            date_match = date_match - timedelta(1)
            several_days_ago = date_match - timedelta(days_ago)
            url = ('http://www.datdota.com/api/players/hero-combos?players={}'.format(player) +
            self.PATCH +
            '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81'+
            '&patch=6.80&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74&winner=either'+
            '&after={}%2F{}%2F{}'.format(several_days_ago.day, several_days_ago.month, several_days_ago.year)+
            '&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year)+
            '&duration=0%3B200&duration-value-from=0&duration-value-to=200&tier=1&tier=2&tier=3'+
            '&valve-event=does-not-matter&threshold={}'.format(threshold))
            # выгрузить все с сайта и создать ДФ
            try:
                dat = self.__get_json_from_url(url)
            except:
                dat = {'data':[]}
            df_url = pd.DataFrame(dat.get('data'))
            return df_url

        def getKdaAndEloshiftPlayersFromTeam(df_heroe_match, radiant_or_dire, index, days_ago, threshold):
            def createColumnName(radiant_or_dire, i, different_part, days_ago):
                column_name = '{}_P{}_{}_{}days_ago'.format(radiant_or_dire, str(i), different_part, days_ago)
                return column_name

            for i in range(1, 6):
                # вытащить id игрока
                id_player = main[radiant_or_dire + '_P' + str(i)][index]
                # создать ДФ c avgElo для игрока по ДАТЕ ИГРЫ
                df_player = getDfPlayerDaysAgo(int(id_player), index, days_ago, threshold)
                df_player = df_player.dropna()
                try:
                    # diffferent_H - на скольких разных героях отыграл этот игрок за 7 дней
                    different_H = len(df_player)
                    winrate = df_player['winrate'].mean()
                    kills = df_player['kills'].mean()
                    deaths = df_player['deaths'].mean()
                    assists = df_player['assists'].mean()
                    elo = df_player['eloShift'].mean()
                    gpm = df_player['gpm'].mean()
                    xpm = df_player['xpm'].mean()
                    kda = df_player['kda'].mean()
                    lastHits = df_player['lastHits'].mean()
                    denies = df_player['denies'].mean()
                except:
                    different_H=0; winrate=0; kills=0; deaths=0; assists=0; elo=0; gpm=0;  xpm=0; kda=0; lastHits=0; denies=0;            
                # ДФ для героя игрока по матчу
                df_heroe = pd.DataFrame([[different_H, winrate, kills, deaths, assists, elo, gpm, 
                                              xpm, kda, lastHits, denies]], columns=[
                                                        createColumnName(radiant_or_dire, i, 'different_H', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'winrate', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'kills', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'deaths', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'assists', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'eloShift', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'gpm', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'xpm', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'kda', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'lastHits', days_ago),
                                                        createColumnName(radiant_or_dire, i, 'denies', days_ago)])
                df_heroe_match = pd.merge(df_heroe_match, df_heroe, left_index=True, right_index=True, how='outer')
            return df_heroe_match

        # создать основной ДФ, где будут записаны все матчи (id матча и rda героя)
        df_heroes_players_KDA_elo_days_ago = pd.DataFrame()

        for index in main.index:
            if index % 100 == 0:
                print (index)
            # ДФ для соединения всех герове radiant & dire матча в один ДФ 
            df_heroe_match = pd.DataFrame()
            df_heroe_match = getKdaAndEloshiftPlayersFromTeam(df_heroe_match, 'radiant', index, days_ago, threshold)
            df_heroe_match = getKdaAndEloshiftPlayersFromTeam(df_heroe_match, 'dire', index, days_ago, threshold)
            df_heroe_match['match_id'] = main.loc[index, 'match_id']
            df_heroes_players_KDA_elo_days_ago = pd.concat([df_heroes_players_KDA_elo_days_ago, df_heroe_match])   

        df_heroes_players_KDA_elo_days_ago = df_heroes_players_KDA_elo_days_ago.reset_index().drop('index', axis=1)       
        df_heroes_players_KDA_elo_days_ago = df_heroes_players_KDA_elo_days_ago.fillna(0)
        df_heroes_players_KDA_elo_days_ago.to_csv('../tabel/table from Datdota/KDA/Players/{}day_ago/'.format(days_ago) +
                                  'KDA, EloShift Players on {} to {} ({}day_ago, {}, more {}).csv'.format(
                                                                                    self.day_first_for_saving_in_file, 
                                                                                    self.day_end_for_saving_in_file, 
                                                                                    str(days_ago), 
                                                                                    pro_or_all_teams, threshold))
    # ------- HD, TD, LVL, HH, GS у Игрока на героях за все время ------------------------------
    def createAndSaveHdTdLvlHhGsForPlayersOnHeroes(self, main, threshold=5):
        print("HD, TD, LVL ... у игроков на героях за все время")
        # Вытащить данные по героям для игроков (elo, gpm, xpm, kda). Передается DF в который добаляются все данные по одному матчу
        def get_players_heroes_HD_TD(df_heroe_match, radiant_or_dire, index):
            for i in range(1, 6):
                # вытащить id героя
                id_hero = main[radiant_or_dire + '_H' + str(i)][index]
                # вытащить id игрока
                id_player = main[radiant_or_dire + '_P' + str(i)][index]

                date_match = date.fromtimestamp(main['start_time'][index])
                date_match = date_match - timedelta(1)

                url = ('http://www.datdota.com/api/heroes/performances?players={}'.format(int(id_player)) +
                self.PATCH +
                '&patch=7.11&patch=7.10&patch=7.09&patch=7.08&patch=7.07&patch=7.06&patch=7.05&patch=7.04&patch=7.03&patch=7.02'+
                '&patch=7.01&patch=7.00&patch=6.88&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81'+
                '&patch=6.80&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74&winner=either'+
                '&after=01%2F01%2F2011&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year)+
                '&duration=0%3B200&duration-value-from=0&duration-value-to=200&tier=1&tier=2&tier=3'+
                '&valve-event=does-not-matter&threshold={}'.format(threshold))

                # выгрузить все с сайта и создать ДФ
                try:
                    dat = self.__get_json_from_url(url)
                except:
                    dat = {'data':[]}
                df_player = pd.DataFrame(dat.get('data'))

                try: 
                    HD = df_player['heroDamage'][df_player['hero'] == id_hero].values[0]
                    TD = df_player['towerDamage'][df_player['hero'] == id_hero].values[0]
                    LVL = df_player['level'][df_player['hero'] == id_hero].values[0]
                    HH = df_player['heroHealing'][df_player['hero'] == id_hero].values[0]
                    GS = df_player['goldSpent'][df_player['hero'] == id_hero].values[0]
                except:
                    HD=0; TD=0; LVL=0; HH=0; GS=0;         

                # ДФ для героя игрока по матчу
                df_heroe = pd.DataFrame([[HD, TD, LVL, HH, GS]], columns=[
                                                                    radiant_or_dire + '_P' + str(i) + '_heroDamage',
                                                                    radiant_or_dire + '_P' + str(i) + '_towerDamage',
                                                                    radiant_or_dire + '_P' + str(i) + '_level',
                                                                    radiant_or_dire + '_P' + str(i) + '_heroHealing',
                                                                    radiant_or_dire + '_P' + str(i) + '_goldSpent'])
                df_heroe_match = pd.merge(df_heroe_match, df_heroe, left_index=True, right_index=True, how='outer')
            return df_heroe_match

        # создать основной ДФ, где будут записаны все матчи (id матча и rda героя)
        df_heroes_players_HD_TD_LVL_HH_GS = pd.DataFrame()

        # создать список названий колонок  героев radiant
        all_her_rad = main.loc[:,'radiant_H1':'radiant_H5'].columns
        # создать список названий колонок  героев radiant
        all_her_dir = main.loc[:,'dire_H1':'dire_H5'].columns
        # создать список названий колонок  игроков radiant
        all_play_rad = main.loc[:,'radiant_P1':'radiant_P5'].columns
        # создать список названий колонок  игроков radiant
        all_play_dir = main.loc[:,'dire_P1':'dire_P5'].columns

        for index in main.index:
            if index % 100 == 0:
                print (index)

            # ДФ для соединения всех герове radiant & dire матча в один ДФ 
            df_heroe_match = pd.DataFrame()

            df_heroe_match = get_players_heroes_HD_TD(df_heroe_match, 'radiant', index)
            df_heroe_match = get_players_heroes_HD_TD(df_heroe_match, 'dire', index)
            df_heroe_match['match_id'] = main.loc[index, 'match_id']

            df_heroes_players_HD_TD_LVL_HH_GS = pd.concat([df_heroes_players_HD_TD_LVL_HH_GS, df_heroe_match])   
        df_heroes_players_HD_TD_LVL_HH_GS = df_heroes_players_HD_TD_LVL_HH_GS.reset_index().drop('index', axis=1)

        df_heroes_players_HD_TD_LVL_HH_GS.to_csv('../tabel/table from Datdota/KDA/Players/'+
                              'HD,TD,LVL,HH,GS Players on hero {} to {} (All time, All, more {}).csv'.format(
                                                                                        self.day_first_for_saving_in_file, 
                                                                                        self.day_end_for_saving_in_file, 
                                                                                        threshold))
    # ------- HD, TD, LVL, HH, GS для героев за последние несколько дней или год если отсутсвуют данные -------------
    def createSaveReturnDataForFillEmptyData(self, main, days_ago=365, pro_or_all_teams='Pro', threshold='10'):
        max_day = (self.day_end_for_saving_in_file - self.day_first_for_saving_in_file).days
        all_data = {}
        match_date = self.day_first_for_saving_in_file - timedelta(1)
        tier = self.__checkTierTeams(pro_or_all_teams)
                    
        for day in range(max_day + 1):
            date_ago = match_date - timedelta(days_ago)
            url_heroes =('http://www.datdota.com/api/heroes/performances?' + self.PATCH +
                '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81&patch=6.80'+ 
                '&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74' +
                '&winner=either&after={}%2F{}%2F{}'.format(date_ago.day, date_ago.month, date_ago.year) + 
                '&before={}%2F{}%2F{}'.format(match_date.day, match_date.month, match_date.year) + 
                '&duration=0%3B200&duration-value-from=0&duration-value-to=200&{}'.format(tier) + 
                '&valve-event=does-not-matter&threshold={}'.format(threshold)) 

            dat = self.__get_json_from_url(url_heroes).get('data')
            all_data[str(match_date)] = dat
            match_date = match_date + timedelta(1)

        name_file = 'DataForFillEmptyData/data_KDA_HD_TD_for_all_Heroes_on({})_to({}) ({}day_ago, {}, more {}).txt'.format(
                                                    self.day_first_for_saving_in_file, self.day_end_for_saving_in_file, 
                                                    str(days_ago), pro_or_all_teams, threshold)
        with open(name_file, 'w') as outfile:
            json.dump(all_data, outfile)
        return all_data
    def createAndSaveHdTdLvlHhGsForHeroesLastDaysWithFillEmptyData(self, main, file_with_data_for_empty_data, 
                                                                   days_ago=30, pro_or_all_teams='Pro', threshold='5'):
        """В отличие от функции createAndSaveKdaHeroes эта отсуствующих данных вставляет данные из
        подгруженного файла. Чтобы создать этот файл, используйте фун-ию createSaveReturnDataForFillEmptyData."""
        print('HD, TD, LVL, HH, GS для героев за последние несколько дней с заполненеим отсуствующих данных')

        # создать основной массив, где будут записаны все матчи (id матча и rda героя)
        df_HD_TD_LVL_HH_GS_heroes_last_days = pd.DataFrame()
        # создать список названий колонок всех героев
        all_her = main.loc[:,'radiant_H1':'dire_H5'].columns
        tier = self.__checkTierTeams(pro_or_all_teams)
        for index in main.index:
            if index%100 == 0:
                print (index)
            # ДФ для соединения всех герове матча в один ДФ 
            df_heroe_match = pd.DataFrame()
            # дата матча
            date_match = date.fromtimestamp(main['start_time'][index])
            # предыдущий день
            date_match =  date_match - timedelta(1)
            several_days_ago = date_match - timedelta(days_ago)
            url_heroes =('http://www.datdota.com/api/heroes/performances?' + self.PATCH +
                '&winner=either&after={}%2F{}%2F{}'.format(several_days_ago.day, several_days_ago.month, 
                                                           several_days_ago.year) + 
                '&before={}%2F{}%2F{}'.format(date_match.day, date_match.month, date_match.year) + 
                '&duration=0%3B200&duration-value-from=0&duration-value-to=200&{}'.format(tier) + 
                '&valve-event=does-not-matter&threshold={}'.format(threshold)) 

            # выгрзить json с предыдущей ссылки
            dat = self.__get_json_from_url(url_heroes).get('data')
            df_data_tabel_for_heroes = pd.DataFrame(dat)
            # создание ДФ с данными за последний год до дня матча, из файла
            df_data_tabel_for_heroes_1Year_ago = pd.DataFrame(file_with_data_for_empty_data.get(str(date_match)))
            for her in all_her:
                # вытащить id героя
                id_heroe = main[her][index]
                try:
                    # создать массив с данными 
                    array = df_data_tabel_for_heroes[df_data_tabel_for_heroes['hero'] == id_heroe].values
                    # Если нет данных по герою то взять данные по герою за последний год из файла
                    if len(array) == 0:
                        array = df_data_tabel_for_heroes_1Year_ago[df_data_tabel_for_heroes_1Year_ago['hero'] == 
                                                                   id_heroe].values
                except: # Если абсолютно новый герой то тогда поставить все 0
                    array = [[z*0 for z in range(21)]]
                # создать название колонок для определнного героя
                col = [her + '_' + c for c  in df_data_tabel_for_heroes_1Year_ago.columns + '_{}day_ago'.format(
                                                                                                            days_ago)]
                # ДФ для героя по матчу
                df_heroe = pd.DataFrame(array, columns=col)
                df_heroe_match = pd.merge(df_heroe_match, df_heroe, 
                                                       left_index=True, right_index=True, how='outer')
                df_heroe_match['match_id'] = main.loc[index, 'match_id']
            df_HD_TD_LVL_HH_GS_heroes_last_days = pd.concat([df_HD_TD_LVL_HH_GS_heroes_last_days, df_heroe_match])
        df_HD_TD_LVL_HH_GS_heroes_last_days = df_HD_TD_LVL_HH_GS_heroes_last_days.reset_index().drop('index', axis=1)
        df_HD_TD_LVL_HH_GS_heroes_last_days.to_csv('../tabel/table from Datdota/KDA/Heroes/DaysAgoWithFillEmptyData/' +
                              'KDA, HD, TD... heroes on {} to {} ({}day_ago, {}, more {}).csv'.format(
                                                                                    self.day_first_for_saving_in_file, 
                                                                                    self.day_end_for_saving_in_file, 
                                                                                    str(days_ago), 
                                                                                    pro_or_all_teams, threshold))