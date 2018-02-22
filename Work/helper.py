import pandas as pd
import numpy as np
import urllib.request, json
from pandas.io.json import json_normalize

def load_table (file, y_answer, ratio_or_testRows):
        matches = pd.read_csv(file, index_col=0)
        if ratio_or_testRows < 1:
            ratio = len(matches) - int(len(matches)*ratio_or_testRows)
        else:
            ratio = len(matches) - 400
          
        X, y = np.split(matches, [ratio])
        
        X_train = X.drop([y_answer], axis=1)
        y_train = X[y_answer]
    
        X_test = y.drop([y_answer], axis=1)
        y_test = y[y_answer]
        
        return X_train, X_test, y_train, y_test;
    
# Составить список из predict proba больще чем perc
def predict_proba (pred_prob, perc):
        arr = []
        for x in pred_prob:
            if (x[0]>=perc):
                arr.append(0)
                continue
            if(x[1]>=perc):
                arr.append(1)
                continue
            else:
                arr.append('X')
                continue
        return np.array(arr);

# Создать и обучить модель с выводом процента предсказания
def learn_algoritm(algoritm, X_train, y_train, X_test, y_test):
    model = algoritm
    model.fit(X_train, y_train)
    print ('Обучающие данные - ', model.score(X_train, y_train))
    print ('Тестовые данные - ', model.score(X_test, y_test))      
    return model

# записать JSON объект с сайта по id матчу
def get_match_on_id(ID, site_name='https://api.opendota.com/api/matches/'):
    #название сайта для одного матча
    site = site_name + str(ID)
    #Прочитаь JSON с сайта для одного матча
    with urllib.request.urlopen(site) as url:
        return json.loads(url.read().decode())

# Вытащить данные из json объекта по ключу в виде датафрейма
def get_from_JSON_for_key(data, key):
    return pd.DataFrame(data.get(key))

# Вытащить имя команды из объекта json по их ID
def get_teamName(data, dire_or_radiant):
    team_id = data.get(dire_or_radiant + '_team').get('team_id')
    data_name_teams = get_match_on_id(team_id, 'https://api.opendota.com/api/teams/')
    return data_name_teams.get("name")

# Вытащить ID команды из моего файла 
def team_id(my_file, team_name):
    team_id = my_file.get(team_name)
    if team_id == None:
        team_id = np.nan
    return team_id

# Создать DF по пикам и банам из матча
def pick_ban(data, result):
    # Первый пик радиант
    first_ban_radiant = (int)(not bool(result['team'][0]))

    # Запись всех пиков и банов подряд из DF по пикам и банам в массив
    a =[first_ban_radiant]
    for id_hero in result['hero_id']:
        a.append(id_hero)

#     Название столбцов в DF пики и баны для патча 7,07+
#     name_columns_picks_bans =['first_ban_radiant', 'ban1', 'ban2','ban3', 'ban4', 'ban5', 'ban6', 'pick1', 'pick2', 'pick3', 'pick4', 
#                               'ban7', 'ban8','ban9', 'ban10', 'pick5', 'pick6', 'pick7', 'pick8', 
#                               'ban11', 'ban12', 'pick9', 'pick10']
    
    # Название столбцов в DF пики и баны для патча 7,06
    name_columns_picks_bans =['first_ban_radiant', 'ban1', 'ban2','ban3', 'ban4', 'pick1', 'pick2', 'pick3', 'pick4', 
                              'ban7', 'ban8','ban9', 'ban10', 'pick5', 'pick6', 'pick7', 'pick8', 
                              'ban11', 'ban12', 'pick9', 'pick10']
    # создание DF для пиков и банов с правильным названием столбцов
    picks_bans = pd.DataFrame([a], columns=name_columns_picks_bans)
    return picks_bans

# Вытащить все неободиимые данные для матча по его ID с OPENDOTA
def get_data_for_match(ID, matches_df, len_picks:"Длина пиков", file_name_and_ID_team:'список команд из мого файла'):
        try:
            data = get_match_on_id(ID)
            # Выбрать DF по Picks_bans (пики и баны для матча 3534749496)
            result_with_picks_bans = get_from_JSON_for_key(data, 'picks_bans')
            try:

                # Для патча до 7.07 длина дожна быть равна 20, после 22
                if len(result_with_picks_bans['hero_id']) == len_picks:    
                    # Название и id лиги
                    league = data.get('league')
                    league_name = league.get('name')
                    league_id = league.get('leagueid')

                    #Имена команд
                    try:
                        radiant_name = get_teamName(data, 'radiant')
                    except AttributeError:
                        radiant_name = np.nan
                    try:
                        dire_name = get_teamName(data, 'dire')                   
                    except AttributeError:
                        dire_name = np.nan

                    # Вытащить id команд из моего списка
                    dire_id = team_id(file_name_and_ID_team, dire_name)
                    radiant_id = team_id(file_name_and_ID_team, radiant_name)

                    # победили редиант
                    radiant_win = (int)(data.get('players').pop().get('radiant_win'))

                    #пики и баны команд, кто первый пикнул
                    picks_bans = pick_ban(data, result_with_picks_bans)

                    # Версия патча
                    version_id = data.get('version')

                    # Кол-во убийсвт в матче
                    dire_score = data.get('dire_score')
                    radiant_score = data.get('radiant_score')

                    # регион
                    region = data.get('region')
                    table_for_match = pd.DataFrame([[ID, version_id, region,  league_name, league_id, radiant_name, radiant_id, 
                                                     dire_name, dire_id, radiant_score, dire_score]], 
                                        columns=['id matches', 'patch', 'region', 'league_name', 'league_id', 'radiant_name', 
                                                 'radiant_id', 'dire_name', 'dire_id', 'radiant_score', 'dire_score'])
                    df = pd.merge(table_for_match, picks_bans, left_index=True, right_index=True)
                    df['radiant_win'] = radiant_win
                    return (df)
            except KeyError:
                print('Отсутсвуют id героев. ID матча - ', ID)
            except AttributeError:
                print ('Отсутсвуют id команды. ID матча - ', ID)
        except Exception as e :
            print ('ID матча - ', ID)
            print (e)