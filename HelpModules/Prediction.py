import sys
sys.path.append('C:\\Users\\User\\1_MY_WORK\\1_Data_Scientist_and_ML_Project\\PredictionDota2\\Help_modules')
import pandas as pd
import numpy as np
import math, json, urllib, pickle
from datetime import date, timedelta
import xgboost as xgb
from connection_to_internet import Connection_to_internet
from patch import Patch

class Features:
    def __init__(self, match_id):
        connect = Connection_to_internet()
        self.match_id = match_id
        self.PATCH = Patch.getCurrentPatch(Patch)
        self.players_signatures = {}
        self.players_7day_ago = {}
        self.__get_json_from_url = connect.get_json_from_url
        # Нельзя вызвать данные в лайве в одном месте, так иногда бывает что не прогрузились данные
        # Поэтому необходимо вызывать каждый раз с self.match_id
        self.get_live_data_for_match = connect.get_live_data_for_match
 
    def get_picks_teams(self, data_match, radiant_or_dire):
        team = []
        try:
            for pick in data_match.get('scoreboard').get(radiant_or_dire).get('picks'):
                team.append(pick.get('hero_id'))
        except:
            df_picks = pd.DataFrame(data_match.get('picks_bans'))
            if radiant_or_dire == 'radiant':
                for pick in df_picks['hero_id'][df_picks['is_pick'] == True][df_picks['team'] == 0]:
                    team.append(pick)
            else:
                for pick in df_picks['hero_id'][df_picks['is_pick'] == True][df_picks['team'] == 1]:
                    team.append(pick)
        return team
      
    def get_team_name_and_id(self, data_match, radiant_or_dire):
        try:
            name = data_match.get(radiant_or_dire + '_team').get('team_name')
            team_id = data_match.get(radiant_or_dire + '_team').get('team_id')
        except:
            name = data_match.get(radiant_or_dire + '_name')
            team_id = data_match.get(radiant_or_dire + '_team_id')
        return name, team_id
    
    def get_players_from_heroes(self, data_match, radiant_or_dire):
        """Создать массив с игроками, которые играют на героях из массива. Массив с героями в порядке пиков"""
        df = pd.DataFrame(data_match.get('players'))
        players = []
        for her in radiant_or_dire:
            # на дат дота ошибка и при id игрока Ame выдает другого игрока
            if df['account_id'][df['hero_id'] == her].values[0] == 125581247:
                players.append(177416702)
            else:
                players.append(df['account_id'][df['hero_id'] == her].values[0])
        return players
# ----------------------------------------------------------------------------------------------------------------
    # Head_to_head (How heroes play in meta)
    def __elo_heroes_vs_enemies(self, array_heroes, array_enemies, df_elo_herVsEne):
        """Создать массив с суммарными показателями elo для героя vs всх врагов"""
        df_elo = []
        # две переменные для записи суммарного elo каждой команды
        for her in array_heroes:
            hero_elo = 0
            # суммировать elo героя против героев противника
            for her_enemy in array_enemies:
                try:
                    elo =  df_elo_herVsEne['shift'][df_elo_herVsEne['hero'] == 
                                                  her][df_elo_herVsEne['againstHero'] == her_enemy].item()
                    if math.isnan(elo):
                        elo=0
                except:
                    elo=0
                hero_elo += elo
            # записать в основной массив elo по каждому герою
            df_elo = np.append(df_elo, hero_elo)
        return df_elo
    
    def __get_elo_head_to_head(self, url, radiant_H, dire_H):
        """Создать ДФ elo по героям имея только ссылку на сайт"""
        dat = self.__get_json_from_url(url)
        df_elo_herVsEne = pd.DataFrame(dat.get('data'))

        radiant_eloVsEnemy = self.__elo_heroes_vs_enemies(radiant_H, dire_H, df_elo_herVsEne)
        dire_eloVsEnemy = self.__elo_heroes_vs_enemies(dire_H, radiant_H, df_elo_herVsEne)
        # Соединить все в один ДФ
        df_elo_vs_enemies = pd.DataFrame([np.append(radiant_eloVsEnemy, dire_eloVsEnemy)], columns= [
            'radiant_H1_elo_vs_enemies', 'radiant_H2_elo_vs_enemies', 'radiant_H3_elo_vs_enemies',  
            'radiant_H4_elo_vs_enemies', 'radiant_H5_elo_vs_enemies','dire_H1_elo_vs_enemies', 
            'dire_H2_elo_vs_enemies', 'dire_H3_elo_vs_enemies','dire_H4_elo_vs_enemies', 'dire_H5_elo_vs_enemies'])

        return df_elo_vs_enemies
    
    def create_df_Head_to_Head_contrpick(self):
        # Elo героя относительно его врагов (Head-to_head)
        url_Head_to_head_allPatch = ('http://www.datdota.com/api/heroes/head-to-head-elo?tier=1&tier=2&tier=3'+
            '&valve-event=does-not-matter&threshold=20'+ self.PATCH + 
            '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83' +
            '&patch=6.82&patch=6.81&patch=6.80&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74' +
            '&winner=either&after=01%2F01%2F2011'+
            '&before={}%2F{}%2F{}'.format(date.today().day, date.today().month, date.today().year)+
            '&duration=0%3B200&duration-value-from=0&duration-value-to=200')
        head_to_head_allPatch = self.__get_elo_head_to_head(url_Head_to_head_allPatch, self.radiant_H, self.dire_H)
        print('Head-to-Head')
        print(head_to_head_allPatch.values)
        
        return head_to_head_allPatch
# ----------------------------------------------------------------------------------------------------------------
    #AvgElo / Meta
    def __get_df_avgElo_heroes(self, df):
        """Cоздать ДФ c elo (какой импакт вносит или вносят герои) для одного героя, пары и тройки"""
        df_one = df.loc[(index for index, x in enumerate(df['heroes']) if len(x) == 1), :]  
        df_one = df_one.reset_index().drop('index', axis=1)
    #     df_double = df.loc[(index for index, x in enumerate(df['heroes']) if len(x) == 2), :]  
    #     df_triple = df.loc[(index for index, x in enumerate(df['heroes']) if len(x) == 3), :]  
        return df_one#, df_double, df_triple
    
    def create_df_heroes_match_AvgElo_meta(self):
        # ДФ для соединения всех герове матча в один ДФ 
        df_heroes_match_AvgElo_meta = []
        # создать дату два месяца назад от даты матча
        two_month_ago = date.today() - timedelta(60)
        # создать ссылку с данными по Avg.Elo для двух предыдущих месяцев игры
        url_meta_two_month = ('http://www.datdota.com/api/heroes/elo?tier=1&tier=2&tier=3&valve-event=does-not-matter&threshold=20' +
               self.PATCH +
            '&winner=either'+
            '&after={}%2F{}%2F{}'.format(two_month_ago.day, two_month_ago.month, two_month_ago.year) + 
            '&before={}%2F{}%2F{}'.format(date.today().day, date.today().month, date.today().year) + 
            '&duration=0%3B200&duration-value-from=0&duration-value-to=200')
        # выгрузить все с сайта и создать ДФ
        dat = self.__get_json_from_url(url_meta_two_month)
        df_url = pd.DataFrame(dat.get('data'))
        # создать ДФ для одного героя за 2 предыдущих месяца
        df_data_tabel_for_heroes = self.__get_df_avgElo_heroes(df_url)
        for her in (self.radiant_H + self.dire_H):
            # вытащить avg elo для данного героя
            avgElo_hero = df_data_tabel_for_heroes.loc[(index for index, x in enumerate(
                                                df_data_tabel_for_heroes['heroes']) if x == [her]),'eloShift']

            # проверить есть ли герой
            try:
                avgElo_hero = float(avgElo_hero)
            except:
                avgElo_hero = 0
            df_heroes_match_AvgElo_meta.append(avgElo_hero)
        df_heroes_match_AvgElo_meta = pd.DataFrame([df_heroes_match_AvgElo_meta], columns=['radiant_H1_AvgElo',
               'radiant_H2_AvgElo', 'radiant_H3_AvgElo', 'radiant_H4_AvgElo', 'radiant_H5_AvgElo', 
                'dire_H1_AvgElo', 'dire_H2_AvgElo','dire_H3_AvgElo', 'dire_H4_AvgElo', 'dire_H5_AvgElo'])
        print('Meta')
        print(df_heroes_match_AvgElo_meta.values)
        return df_heroes_match_AvgElo_meta
    
# ----------------------------------------------------------------------------------------------------------------
    # Average eloShift for heroes over the last 7 day
    def create_df_heroes_match_AvgEloShift_7day_ago(self):
        # ДФ для соединения всех герове матча в один ДФ 
        df_heroes_match_AvgEloShift_7day_ago = []
        # создать дату 7 дней назад от даты матча
        seven_day_ago = date.today() - timedelta(7)
        # создать ссылку с данными по Avg.Elo для двух предыдущих месяцев игры
        url_heroes_AvgElo_7day_ago = ('http://www.datdota.com/api/heroes/elo?tier=1&tier=2&tier=3&valve-event=does-not-matter&threshold=10' +
               self.PATCH +
            '&winner=either&after={}%2F{}%2F{}'.format(seven_day_ago.day, seven_day_ago.month, seven_day_ago.year) + 
            '&before={}%2F{}%2F{}'.format(date.today().day, date.today().month, date.today().year) + 
            '&duration=0%3B200&duration-value-from=0&duration-value-to=200')
        # выгрузить все с сайта и создать ДФ
        dat = self.__get_json_from_url(url_heroes_AvgElo_7day_ago)
        df_url_heroes_AvgElo_7day_ago = pd.DataFrame(dat.get('data'))
        try:
            # создать ДФ для одного героя за последние 7 дней
            df_data_tabel_for_heroes_7day_ago = self.__get_df_avgElo_heroes(df_url_heroes_AvgElo_7day_ago)
        except:
            df_data_tabel_for_heroes_7day_ago = pd.DataFrame()

        for her in (self.radiant_H + self.dire_H):
            try:
                # вытащить avg elo для данного героя
                avgElo_hero = df_data_tabel_for_heroes_7day_ago.loc[(index for index, x in enumerate(
                                                df_data_tabel_for_heroes_7day_ago['heroes']) if x == [her]),'eloShift']
                # проверить есть ли герой
                avgElo_hero = float(avgElo_hero)
            except:
                avgElo_hero = 0
            df_heroes_match_AvgEloShift_7day_ago.append(avgElo_hero)
        df_heroes_match_AvgEloShift_7day_ago = pd.DataFrame([df_heroes_match_AvgEloShift_7day_ago], columns=[
                'radiant_H1_AvgElo_7day_ago', 'radiant_H2_AvgElo_7day_ago', 'radiant_H3_AvgElo_7day_ago', 
                'radiant_H4_AvgElo_7day_ago', 'radiant_H5_AvgElo_7day_ago', 'dire_H1_AvgElo_7day_ago', 
                'dire_H2_AvgElo_7day_ago', 'dire_H3_AvgElo_7day_ago', 'dire_H4_AvgElo_7day_ago', 
                'dire_H5_AvgElo_7day_ago'])
        print('Meta_7day_ago')
        print(df_heroes_match_AvgEloShift_7day_ago.values)

        return df_heroes_match_AvgEloShift_7day_ago
# ----------------------------------------------------------------------------------------------------------------
    #Signatures   
    def get_data_players_for_signatures_at_allTime_and_7dayAgo(self):
        """Создать словарь по сигнатуркам игроков для данного матча за все время и за 7 дней. 
        Записать их в переменную класса"""
        try:
            df = pd.DataFrame(self.get_live_data_for_match(self.match_id).get('players'))
            account_players =[]
            account_players = df[df['team'] ==1]['account_id']
            account_players = account_players.append(df[df['team'] ==0 ]['account_id'])
        except:
            map_with_players = self.get_live_data_for_match(self.match_id).get('players')
            account_players =[]
            for p in map_with_players:
                account_players.append(p.get('account_id'))


        for p in account_players:
            # на дат дота ошибка и при id игрока Ame выдает другого игрока
            if p == 125581247:
                p = 177416702
            df_p = self.__get_df_AvgElo_heroes_player(p)
            df_p_7day_ago = self.__get_df_player_7day_ago(p)
            
            self.players_signatures.update({p : df_p})
            self.players_7day_ago.update({p : df_p_7day_ago})
        
    
    def create_df_players_heroe_match_signatures(self):
        if self.players_signatures == {}:
            return '1st call function get_data_players_for_signatures_at_allTime_and_7dayAgo'                              
        # ДФ для соединения всех героев radiant & dire матча в один ДФ 
        df_players_heroe_match_signatures = []
        self.get_players_heroes_signatures_in_match(df_players_heroe_match_signatures, 
                                                        self.radiant_H, self.radiant_P, self.players_signatures)
        self.get_players_heroes_signatures_in_match(df_players_heroe_match_signatures, 
                                                        self.dire_H, self.dire_P, self.players_signatures)
        df_players_heroe_match_signatures = pd.DataFrame([df_players_heroe_match_signatures], columns=['radiant_P1_eloShift', 'radiant_P2_eloShift', 
               'radiant_P3_eloShift', 'radiant_P4_eloShift', 'radiant_P5_eloShift', 
               'dire_P1_eloShift', 'dire_P2_eloShift', 'dire_P3_eloShift', 'dire_P4_eloShift', 'dire_P5_eloShift'])
        print('Signatures')
        print(df_players_heroe_match_signatures.values)
        return df_players_heroe_match_signatures
        
    def get_players_heroes_signatures_in_match(self, df_heroe_match, heroes, players, players_signatures):
        """Содать ДФ, как игрок отыгрывает на герое. Для каждой команды ф-ция отдельная."""
        for i in range(5):
            # вытащить id героя
            id_hero = heroes[i]
            # вытащить id игрока
            id_player = players[i]
            # players_signatures - список сформированный из функции get_df_AvgElo_heroes_player
            df_player = players_signatures.get(id_player)
            try:
                elo = df_player['eloShift'][df_player['hero'] == id_hero].values[0]
            except:
                elo = 0          
            df_heroe_match.append(elo)
        return df_heroe_match
    
    def __get_df_AvgElo_heroes_player(self, player):
        url = ('http://www.datdota.com/api/players/hero-combos?players={}'.format(player) +
        self.PATCH +
        '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81'+
        '&patch=6.80&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74&winner=either'+
        '&after=01%2F01%2F2011&before={}%2F{}%2F{}'.format(date.today().day, date.today().month, date.today().year)+
        '&duration=0%3B200&duration-value-from=0&duration-value-to=200&tier=1&tier=2&tier=3'+
        '&valve-event=does-not-matter&threshold=5')
        # выгрузить все с сайта и создать ДФ
        dat = self.__get_json_from_url(url)
        df_url = pd.DataFrame(dat.get('data'))
        return df_url

    # Average eloShift for players over the last 7 day        
    def get_players_heroes_7day_ago_signatures_in_match(self, df_heroe_match, players, players_7day_ago):
        """Cформировать список с данными по каждому игроку за послеждние 7 дней. Для каждой команды отдельно"""
        for i in range(5):
            # вытащить id игрока
            id_player = players[i]
            df_player = players_7day_ago.get(id_player)
            try:
                elo = df_player.dropna()['eloShift'].mean()
            except:
                elo = 0          
            df_heroe_match.append(elo)
        return df_heroe_match
        
    def __get_df_player_7day_ago(self, player):
        """Cоздать ДФ для соло героев за 7 предыдущих дней (какая форма игрока)"""
        # создать дату 7 дней назад от даты матча
        seven_day_ago = date.today() - timedelta(7)
        # создать ДФ для соло героев за все время игр игрока (сигнатурки)
        url = ('http://www.datdota.com/api/players/hero-combos?players={}'.format(player) +
        self.PATCH +
        '&patch=6.87&patch=6.86&patch=6.85&patch=6.84&patch=6.83&patch=6.82&patch=6.81'+
        '&patch=6.80&patch=6.79&patch=6.78&patch=6.77&patch=6.76&patch=6.75&patch=6.74&winner=either'+
        '&after={}%2F{}%2F{}'.format(seven_day_ago.day, seven_day_ago.month, seven_day_ago.year)+
        '&before={}%2F{}%2F{}'.format(date.today().day, date.today().month, date.today().year)+
        '&duration=0%3B200&duration-value-from=0&duration-value-to=200&tier=1&tier=2&tier=3'+
        '&valve-event=does-not-matter&threshold=1')
        dat = self.__get_json_from_url(url)
    #     try:
    #         dat = get_json_from_url(url)
    #     except:
    #         dat = {'data':[]}
        df_url = pd.DataFrame(dat.get('data'))
        return df_url
    
    def create_df_players_heroe_match_7day_ago(self):
        """Как игрок отыгрывает послежние 7 дней """                          
        # ДФ для соединения всех герове radiant & dire матча в один ДФ 
        df_players_heroe_match_7day_ago = []
        df_players_heroe_match_7day_ago = self.get_players_heroes_7day_ago_signatures_in_match(
                                    df_players_heroe_match_7day_ago, self.radiant_P, self.players_7day_ago)
        df_players_heroe_match_7day_ago = self.get_players_heroes_7day_ago_signatures_in_match(
                                    df_players_heroe_match_7day_ago, self.dire_P, self.players_7day_ago)
        df_players_heroe_match_7day_ago = pd.DataFrame([df_players_heroe_match_7day_ago], columns=['radiant_P1_eloShift_7day_ago',
                'radiant_P2_eloShift_7day_ago', 'radiant_P3_eloShift_7day_ago', 'radiant_P4_eloShift_7day_ago',
                'radiant_P5_eloShift_7day_ago', 'dire_P1_eloShift_7day_ago', 'dire_P2_eloShift_7day_ago', 
                'dire_P3_eloShift_7day_ago', 'dire_P4_eloShift_7day_ago', 'dire_P5_eloShift_7day_ago'])
        print('Signatures_7day_ago')
        print(df_players_heroe_match_7day_ago.values)
        return df_players_heroe_match_7day_ago
# ----------------------------------------------------------------------------------------------------------------    
    def get_current_rating_teams(self, team_id, radiant_or_dire):
        """Создать ДФ с рейтингом Glicko команд . Также используетяс изменение рейтинга за последние 7 лней."""
        date_rating = date.today()
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

        # бывает что не посчитан рейтинг для текущей недели и тогда взять 14 дней назад
        if data_7day_ago.loc['startPeriod', 'GLICKO_1'] == data.loc['startPeriod', 'GLICKO_1']:
            date_rating_7day_ago = date_rating - timedelta(14)
            url_7day_ago = 'http://www.datdota.com/api/teams/{}/ratings?date={}-{}-{}'.format(
                    team_id, date_rating_7day_ago.year, date_rating_7day_ago.month, date_rating_7day_ago.day )
            # выгрзить json с предыдущей ссылки и создать ДФ
            dat_7day_ago = self.__get_json_from_url(url_7day_ago)
            data_7day_ago = pd.DataFrame(dat_7day_ago.get('data'))

        team_rating_df_allData = pd.DataFrame()
        team_rating_df_allData.loc[0, radiant_or_dire + '_mu_glicko'] = data.loc['mu', 'GLICKO_1']
        team_rating_df_allData.loc[0, radiant_or_dire + '_rating_glicko'] = data.loc['rating', 'GLICKO_1']
        team_rating_df_allData.loc[0, radiant_or_dire + '_ratingSevenDaysAgo_glicko'] = data_7day_ago.loc['rating', 'GLICKO_1']
        team_rating_df_allData.loc[0, radiant_or_dire + '_sigma_glicko'] = data.loc['sigma', 'GLICKO_1']

        team_rating_df_allData.loc[0, radiant_or_dire + '_mu_glicko2'] = data.loc['mu', 'GLICKO_2']
        team_rating_df_allData.loc[0, radiant_or_dire + '_phi_glicko2'] = data.loc['phi', 'GLICKO_2']
        team_rating_df_allData.loc[0, radiant_or_dire + '_rating_glicko2'] = data.loc['rating', 'GLICKO_2']
        team_rating_df_allData.loc[0, radiant_or_dire + '_ratingSevenDaysAgo_glicko2'] = data_7day_ago.loc['rating', 'GLICKO_2']    

        return(team_rating_df_allData)
# ----------------------------------------------------------------------------------------------------------------     
    def create_array_heroes(self):
        """Создать список есть ли в како-нибудь команде Клок, Гиро, Висп.
        Используется только в алгоритме 66"""
        arr_her = []
        hero = [51,72, 91]
        for her in hero:
            if her in self.radiant_H :
                arr_her.append(1)
            elif her in self.dire_H:
                arr_her.append(-1)
            else:
                arr_her.append(0)
        arr_her = pd.DataFrame([arr_her], columns=['Clockwerk', 'Gyrocopter', 'Io'])
        return arr_her
# ----------------------------------------------------------------------------------------------------------------     
    def create_feature_on_predict_rating(self, radiant_rating_df_allData, dire_rating_df_allData):
        # Выгрузить алгоритм для создания переменной предсказаной по рейтингу команд
        predict_for_rating = pickle.load(open('../Work/Xgboost_model_predict_rating_teams_without_elo.sav', 'rb'))
        # Создание DF для предсказания по алгоритму обученому на рейтинге
        df_predict_rating = pd.DataFrame()
        df_predict_rating.loc[0, 'radiant_mu_glicko'] = radiant_rating_df_allData.loc[0, 'radiant_mu_glicko'].item()
        df_predict_rating.loc[0, 'radiant_rating_glicko'] = radiant_rating_df_allData.loc[0, 'radiant_rating_glicko'].item()
        df_predict_rating.loc[0, 'radiant_ratingSevenDaysAgo_glicko'] = radiant_rating_df_allData.loc[0, 'radiant_ratingSevenDaysAgo_glicko'].item()
        df_predict_rating.loc[0, 'radiant_mu_glicko2'] = radiant_rating_df_allData.loc[0, 'radiant_mu_glicko2'].item()

        df_predict_rating.loc[0, 'dire_mu_glicko'] = dire_rating_df_allData.loc[0, 'dire_mu_glicko'].item()
        df_predict_rating.loc[0, 'dire_rating_glicko'] = dire_rating_df_allData.loc[0, 'dire_rating_glicko'].item()
        df_predict_rating.loc[0, 'dire_ratingSevenDaysAgo_glicko'] = dire_rating_df_allData.loc[0, 'dire_ratingSevenDaysAgo_glicko'].item()
        df_predict_rating.loc[0, 'dire_sigma_glicko'] = dire_rating_df_allData.loc[0, 'dire_sigma_glicko'].item()
        df_predict_rating.loc[0, 'dire_mu_glicko2'] = dire_rating_df_allData.loc[0, 'dire_mu_glicko2'].item()
        df_predict_rating.loc[0, 'dire_ratingSevenDaysAgo_glicko2'] = dire_rating_df_allData.loc[0, 'dire_ratingSevenDaysAgo_glicko2'].item()

        df_predict_rating.loc[0, 'mu_glicko'] = (radiant_rating_df_allData.loc[0, 'radiant_mu_glicko'].item() - 
                                                    dire_rating_df_allData.loc[0, 'dire_mu_glicko'].item())
        df_predict_rating.loc[0, 'rating_glicko'] = (radiant_rating_df_allData.loc[0, 'radiant_rating_glicko'].item() - 
                                                    dire_rating_df_allData.loc[0, 'dire_rating_glicko'].item())
        df_predict_rating.loc[0, 'ratingSevenDaysAgo_glicko'] = (radiant_rating_df_allData['radiant_ratingSevenDaysAgo_glicko'].item() - 
                                                    dire_rating_df_allData.loc[0, 'dire_ratingSevenDaysAgo_glicko'].item())
        df_predict_rating.loc[0, 'mu_glicko2'] = (radiant_rating_df_allData.loc[0, 'radiant_mu_glicko2'].item() - 
                                                    dire_rating_df_allData.loc[0, 'dire_mu_glicko2'].item())
        df_predict_rating.loc[0, 'phi_glicko2'] = (radiant_rating_df_allData.loc[0, 'radiant_phi_glicko2'].item() - 
                                                    dire_rating_df_allData.loc[0, 'dire_phi_glicko2'].item())
        print('Predict')
        print(df_predict_rating.values)
        predict_rating = pd.DataFrame(predict_for_rating.predict_proba(df_predict_rating)[:,1:], columns=['Predict'])
        return predict_rating   
# ==================================================================================================================
# ==================================================================================================================
    def get_teams_heroes_players_id(self):
        """Записать в переменные класса название и ID команд, героев и игроков, когда будут доступны данные в лайве"""
        while True:
            try:
                data_match = self.get_live_data_for_match(self.match_id)

                self.radiant_team_name, self.radiant_team_id = self.get_team_name_and_id(data_match, 'radiant')
                self.dire_team_name, self.dire_team_id = self.get_team_name_and_id(data_match, 'dire')
                self.radiant_H = self.get_picks_teams(data_match, 'radiant')
                self.radiant_P = self.get_players_from_heroes(data_match, self.radiant_H)
                self.dire_H = self.get_picks_teams(data_match, 'dire')
                self.dire_P = self.get_players_from_heroes(data_match, self.dire_H)

                if len(self.radiant_H) == 5 and len(self.dire_H) == 5:
                    print (self.radiant_team_name, " - ", self.radiant_team_id)
                    print ('Picks - ', self.radiant_H)
                    print ('Players - ', self.radiant_P)
                    print (self.dire_team_name, " - ", self.dire_team_id)
                    print ('Picks - ', self.dire_H)
                    print ('Players - ', self.dire_P)
                    break
            except:
                pass
    
    def get_and_connect_all_data_for_match(self):
        def connect_allData_in_oneDF(radiant_rating_df_allData, dire_rating_df_allData, predict_rating, 
                        df_head_to_head_contrpick, df_heroes_match_AvgElo_meta, df_heroes_match_AvgEloShift_7day_ago, 
                        df_players_heroe_match_signatures, df_players_heroe_match_7day_ago, arr_heroe):
            
            main = pd.concat([radiant_rating_df_allData, dire_rating_df_allData, 
                        df_head_to_head_contrpick, df_heroes_match_AvgElo_meta, df_players_heroe_match_signatures,
                        arr_heroe, predict_rating, df_heroes_match_AvgEloShift_7day_ago, 
                        df_players_heroe_match_7day_ago], axis=1 )
            return main
        
        def create_addFeatures_from_existingData(main):
            #------------- Для контрпиков героев --------------------------------------------------------
            main['radiant_elo_vs_enemies'] = (main['radiant_H1_elo_vs_enemies'] + main['radiant_H2_elo_vs_enemies'] + 
                                              main['radiant_H3_elo_vs_enemies'] + main['radiant_H4_elo_vs_enemies'] + 
                                              main['radiant_H5_elo_vs_enemies'])

            main['dire_elo_vs_enemies'] = (main['dire_H1_elo_vs_enemies'] + main['dire_H2_elo_vs_enemies'] + 
                              main['dire_H3_elo_vs_enemies'] + main['dire_H4_elo_vs_enemies'] + main['dire_H5_elo_vs_enemies'])

            main['elo_vs_enemies'] = main['radiant_elo_vs_enemies'] - main['dire_elo_vs_enemies']

            #------------- Для сигнатурных героев по игрокам --------------------------------------------------------
            main['radiant_P_eloShift'] = (main['radiant_P1_eloShift'] + main['radiant_P2_eloShift'] + 
                                          main['radiant_P3_eloShift'] + main['radiant_P4_eloShift'] + 
                                          main['radiant_P5_eloShift'])

            main['dire_P_eloShift'] = (main['dire_P1_eloShift'] + main['dire_P2_eloShift'] + 
                                       main['dire_P3_eloShift'] + main['dire_P4_eloShift'] + main['dire_P5_eloShift'])

            main['P_eloShift'] = main['radiant_P_eloShift'] - main['dire_P_eloShift']

            #------------- Для метовых героев --------------------------------------------------------
            main['radiant_H_AvgElo'] = (main['radiant_H1_AvgElo'] + main['radiant_H2_AvgElo'] + 
                                      main['radiant_H3_AvgElo'] + main['radiant_H4_AvgElo'] + main['radiant_H5_AvgElo'])

            main['dire_H_AvgElo'] = (main['dire_H1_AvgElo'] + main['dire_H2_AvgElo'] + 
                                       main['dire_H3_AvgElo'] + main['dire_H4_AvgElo'] + main['dire_H5_AvgElo'])

            main['H_AvgElo'] = main['radiant_H_AvgElo'] - main['dire_H_AvgElo']

            #------------- Для метовых героев 7 дней назад --------------------------------------------------------
            main['radiant_H_AvgElo_7day_ago'] = (main['radiant_H1_AvgElo_7day_ago'] + main['radiant_H2_AvgElo_7day_ago'] + 
                                      main['radiant_H3_AvgElo_7day_ago'] + main['radiant_H4_AvgElo_7day_ago'] + 
                                                 main['radiant_H5_AvgElo_7day_ago'])

            main['dire_H_AvgElo_7day_ago'] = (main['dire_H1_AvgElo_7day_ago'] + main['dire_H2_AvgElo_7day_ago'] + 
                                       main['dire_H3_AvgElo_7day_ago'] + main['dire_H4_AvgElo_7day_ago'] + 
                                              main['dire_H5_AvgElo_7day_ago'])

            main['H_AvgElo_7day_ago'] = main['radiant_H_AvgElo_7day_ago'] - main['dire_H_AvgElo_7day_ago']

            #------------- Для того как игрок отыграл 7 дней назад --------------------------------------------------------
            main['radiant_P_eloShift_7day_ago'] = (main['radiant_P1_eloShift_7day_ago'] + main['radiant_P2_eloShift_7day_ago'] + 
                                          main['radiant_P3_eloShift_7day_ago'] + main['radiant_P4_eloShift_7day_ago'] + 
                                                   main['radiant_P5_eloShift_7day_ago'])

            main['dire_P_eloShift_7day_ago'] = (main['dire_P1_eloShift_7day_ago'] + main['dire_P2_eloShift_7day_ago'] + 
                                       main['dire_P3_eloShift_7day_ago'] + main['dire_P4_eloShift_7day_ago'] + 
                                                main['dire_P5_eloShift_7day_ago'])

            main['P_eloShift_7day_ago'] = main['radiant_P_eloShift_7day_ago'] - main['dire_P_eloShift_7day_ago']
            return main
        # ==============================================================
        radiant_rating_df_allData = self.get_current_rating_teams(self.radiant_team_id, 'radiant')
        dire_rating_df_allData = self.get_current_rating_teams(self.dire_team_id, 'dire')
        # ==============================================================
        predict_rating = self.create_feature_on_predict_rating(radiant_rating_df_allData, dire_rating_df_allData)
        
        df_head_to_head_contrpick = self.create_df_Head_to_Head_contrpick()
        
        df_heroes_match_AvgElo_meta = self.create_df_heroes_match_AvgElo_meta()
              
        df_players_heroe_match_signatures = self.create_df_players_heroe_match_signatures()

        df_heroes_match_AvgEloShift_7day_ago = self.create_df_heroes_match_AvgEloShift_7day_ago()
        
        df_players_heroe_match_7day_ago = self.create_df_players_heroe_match_7day_ago()
        
        arr_heroe = self.create_array_heroes()

        self.__array_HeadToHead_Meta_Signatures_for_telegrammBot = [df_head_to_head_contrpick,
                                                                             df_heroes_match_AvgElo_meta,
                                                                             df_players_heroe_match_signatures]

        main = connect_allData_in_oneDF(radiant_rating_df_allData, dire_rating_df_allData, 
                                    predict_rating, df_head_to_head_contrpick, df_heroes_match_AvgElo_meta, 
                                    df_heroes_match_AvgEloShift_7day_ago, df_players_heroe_match_signatures, 
                                    df_players_heroe_match_7day_ago, arr_heroe)
        
        main = create_addFeatures_from_existingData(main)
        return main   
        
    def getHeadToHeadMetaSignaturesForTelegram(self):
        return self.__array_HeadToHead_Meta_Signatures_for_telegrammBot
        
class Prediction:
    def __init__(self, fileName_algoritm_prediction, name_columns_of_valid_features, all_features):
        self.__algoritm_prediction = pickle.load(open(fileName_algoritm_prediction, 'rb'))
        self.__valid_features = all_features[name_columns_of_valid_features]
        self.__fileName_algoritm_prediction = fileName_algoritm_prediction
        self.__predict_proba = self.__algoritm_prediction.predict_proba(self.__valid_features)
    
    def getTextPredict(self):
        text_result_prediction = self.__fileName_algoritm_prediction + " - " + str(self.__predict_proba)
        return text_result_prediction 
    
    def getPredictProba(self):
        return self.__predict_proba

    
    