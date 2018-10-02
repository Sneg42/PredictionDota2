import json, requests, dota2api
class Connection_to_internet:
    
    # ДЛЯ ДОСТУПА через прокси и без или дома
    def get_url_from_proxy(self, url, *args):
        # *args need to connect with data base opendota
        if len(args) == 1:
            params = args[0]
        else:
            params = ''
        """Для доступа через прокси и без, разкоментить и заменить данные прокси если нужно.
           Если делать через исключение, то может долго грузить данные с сайтов.
        """
    #     http_proxy  = "http://pavlov.ds:qwerty@172.16.0.10:3128"
    #     https_proxy = "https://pavlov.ds:qwerty@172.16.0.10:3128"
    #     ftp_proxy   = "ftp://pavlov.ds:qwerty@172.16.0.10:3128"

    #     proxyDict = { 
    #                   "http"  : http_proxy, 
    #                   "https" : https_proxy, 
    #                   "ftp"   : ftp_proxy   
    #                 }
    #     return requests.get(url, params = params, headers={'User-agent': 'Mozilla/5.0'}, proxies=proxyDict)
    #   # Без прокси
        return requests.get(url, params = params, headers={'User-agent': 'Mozilla/5.0'})

    def get_json_from_url(self, url):
        """Создать json из текста url"""
        r = self.get_url_from_proxy(url)
        return json.loads(r.text)
    
    # Вытащить данные с лайв API по ID матча или с прошедшего матча
    def get_live_data_for_match(self, match_id):   
        # Api для доты2 чтобы доставать данные из лайва
        api = dota2api.Initialise("F976A5435E1C8C0B8F3992D8CCA9B619", executor=self.get_url_from_proxy)
        """Cоздает переменную data_match, либо из лайва, либо из прошедшего матча"""
        for game in api.get_live_league_games().get('games'):
            """Если матч в лайве то беруться данные из лайва"""
            if game.get('match_id') == match_id:
                return(game)
        return(api.get_match_details(match_id))