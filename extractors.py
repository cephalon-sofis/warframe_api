import time
import configparser
from pprint import pprint

from warframe_api.client import Client
from warframe_api.exceptions import ExtractorNotFinishedException
from warframe_api import data

if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read('config.ini')

    planet_names = [config['extractor']['planet1'],
                    config['extractor']['planet2'],
                    config['extractor']['planet3']]
    if any(name not in data.systems() for name in planet_names):
        raise ValueError('Make sure all of the planets exist in the game and are properly capitalized.')

    with Client(config['login']['email'], config['login']['password']) as client:
        active_planets = set()
        active_extractors = client.get_active_extractors()
        for extractor in active_extractors:
            try:
                client.collect_extractor(extractor, active_extractors=active_extractors)
                print('Collected extractor from system {0}'.format(extractor['System']))
            except ExtractorNotFinishedException:
                active_planets.add(extractor['System'])

        print('Active planets: {0}'.format(len(active_planets)))

        if len(active_planets) < 3:
            inventory = client.get_inventory()
            planets = set([data.systems()[planet]['systemIndex']
                           for planet in planet_names]) - active_planets
            drones = sorted(inventory['Drones'], key=lambda d: d['CurrentHP'])

            active_extractors = client.get_active_extractors()
            for planet, drone in zip(planets, drones):
                percent_health = float(drone['CurrentHP']) / data.drones()[drone['ItemType']]['durability']
                if percent_health > 0.3:
                    client.deploy_extractor(drone, planet,
                                            active_extractors=active_extractors)
                    print('Deployed drone to {planet}'.format(planet=planet))

        print('Active extractors:')
        pprint(client.get_active_extractors())
