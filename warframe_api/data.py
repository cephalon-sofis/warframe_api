import os
import sys
import requests
import json

CACHE_DIR = '.data_cache'
EXPORT_URL_BASE = 'http://content.warframe.com/MobileExport'

_DATA = {}

def _generate_data_func(data_type):
    ''' Dynamically generate a function that manages the caching and retrieval
    of the associated data. '''

    def data_func():
        ''' All of the available data about {0}
        Returns a dictionary of {{uniqueName: data}}'''
        if data_type in _DATA:
            return _DATA[data_type]

        filename = 'Export' + data_type + '.json'
        cache_path = os.path.join(CACHE_DIR, filename)
        if not os.path.exists(cache_path):
            url = EXPORT_URL_BASE + '/Manifest/' + filename
            r = requests.get(url)
            data = r.json(strict=False)
            data_values = data.popitem()[1]

            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache_path, 'w') as f:
                json.dump({value['uniqueName']: value for value in data_values}, f)

        with open(cache_path) as f:
            _DATA[data_type] = json.load(f, strict=False)

        return _DATA[data_type]

    data_func.__doc__ = data_func.__doc__.format(data_type)
    return data_func

current_module = sys.modules[__name__]
for data_type in {'Manifest', 'Upgrades', 'Weapons', 'Warframes', 'Sentinels',
                  'Enemies', 'Resources', 'Drones', 'Customs', 'Flavour', 'Keys',
                  'Gear', 'Regions'}:
    setattr(current_module, data_type.lower(), _generate_data_func(data_type))

def systems():
    ''' All of the regions grouped by system. '''
    if 'Systems' in _DATA:
        return _DATA['Systems']

    all_systems = {}
    for region in current_module.regions().values():
        system_name = region['systemName']
        if system_name not in all_systems:
            all_systems[system_name] = {
                'systemIndex': region['systemIndex'],
                'regions': []
            }
        all_systems[system_name]['regions'].append(region['uniqueName'])

    _DATA['Systems'] = all_systems
    return all_systems

def extractor_json(unique_name):
    ''' Reformat the drones data for use with the extractor API. '''
    extractor = current_module.drones()[unique_name]
    return json.dumps({
        'droneRes': extractor['uniqueName'],
        'binCount': extractor['binCount'],
        'binCapacity': extractor['binCapacity'],
        'droneDurability': extractor['durability'],
        'fillRate': extractor['fillRate'],
        'repairRate': extractor['repairRate'],
        'capacityMultipliers': extractor['capacityMultiplier'],
        'probabilities': extractor['probabilty'], #sic
        'specialities': extractor['specialities']
    })

def image_url(unique_name):
    texture_location = current_module.manifest()[unique_name]['textureLocation']
    url = EXPORT_URL_BASE + texture_location
    return url.replace('\\', '/')
