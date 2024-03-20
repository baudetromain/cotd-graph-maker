import requests
import argparse
import time
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime as dt


class NoExactMatchingPlayerException(Exception):
    def __init__(self, player_name, close_matches):
        super().__init__(f'No player called {player_name}, suggestions are: {", ".join(close_matches)}')


class NoPlayerFoundException(Exception):
    def __init__(self, player_name):
        super().__init__(f'No player called {player_name}, and no players with a name close to it were found.')


class Non200StatusCodeReturnedException(Exception):
    def __init__(self, url):
        super().__init__(f'Error: a request to {url} has returned a non-200 status code.')


class RatelimitAwareRequestsWrapper():
    
    def __init__(self):
        self.session = requests.session()

    def __check_rate_limit(self, response):
        if 'X-Ratelimit-Remaining' in response.headers.keys():
            if int(response.headers['X-Ratelimit-Remaining']) <= 2:
                timeout = int(response.headers['X-Ratelimit-Reset']) + 2
                print(f'Ratelimit almost hit, sleeping for {timeout} seconds')
                time.sleep(timeout)

    def get(self, *args, **kwargs):
        response = self.session.get(*args, **kwargs)
        self.__check_rate_limit(response)
        return response

    def post(self, *args, **kwargs):
        response = self.session.post(*args, **kwargs)
        self.__check_rate_limit(response)
        return response


headers = {
    'User-Agent': 'github.com/baudetromain/cotd-graph-maker'
}

requestWrapper = RatelimitAwareRequestsWrapper()


def get_player_uuid(player):
    url = f'https://trackmania.io/api/players/find?search={player}'
    response = requestWrapper.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        if len(data) == 0:
            raise NoPlayerFoundException(player)
        if len(data) > 1:
            raise NoExactMatchingPlayerException(player, [item['player']['name'] for item in data])
        return data[0]['player']['id']
    raise Non200StatusCodeReturnedException(url)


def main():
    parser = argparse.ArgumentParser(prog='COTD graph maker',
                        description='A program to generate a graph of the COTD placements of some players over time')

    parser.add_argument('-p', '--players', nargs='+', required=True,
                        help='The list of the players for which the graph must be generated. At least one must be provided.')

    args = parser.parse_args()

    results = dict()

    for player in args.players:
        try:
            req_count = 0
            players_results = {'dates': [], 'scores': []}
            uuid = get_player_uuid(player)
            data = {'cotds': [0]*25}
            while len(data['cotds']) == 25:
                response = requestWrapper.get(f'https://trackmania.io/api/player/{uuid}/cotd/{req_count}?includeReruns=false',
                                    headers=headers)
                data = response.json()
                req_count += 1
                for cotd in data['cotds']:
                    players_results['dates'].append(dt.datetime.strptime(cotd['timestamp'][:10], '%Y-%m-%d').date())
                    players_results['scores'].append(cotd['rank'])

            results[player] = players_results

        except Exception as e:
            print(e)

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y/%m/%d'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator())

    for player in results:
        plt.plot(results[player]['dates'], results[player]['scores'], label=player)

    plt.savefig('output.png')


if __name__ == '__main__':
    main()
