import json
import time
import hashlib
from urllib.parse import urlencode
from functools import wraps

from . import data

import requests

class LoginError(Exception):
    def __init__(self, text, code):
        self.text = text
        self.code = code

    def __str__(self):
        return self.text

class NotLoggedInException(Exception):
    pass

class AlreadyLoggedInException(LoginError):
    def __init__(self):
        super().__init__('Already logged in', 409)

class VersionOutOfDateException(LoginError):
    def __init__(self):
        super().__init__('Version out of date', 400)

def login_required(func):
    @wraps(func)
    def wrap(self, *args, **kwargs):
        if not self._session_data:
            raise NotLoggedInException()

        return func(self, *args, **kwargs)
    return wrap

class Client():
    def __init__(self, email, password):
        self._email = email
        self._password_hash = hashlib.new('whirlpool', password.encode()).hexdigest()
        self._session_data = None

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._session_data:
            self.logout()

    def _post_message(self, url, data):
        headers={
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': '',
        }

        r = requests.post(url, data=data, headers=headers)
        r.raise_for_status()
        try:
            return r.json()
        except json.decoder.JSONDecodeError:
            return r.text

    def login(self):
        url = 'https://api.warframe.com/API/PHP/login.php'

        # While most data is form-encoded, login data is sent as JSON for some reason...
        data = json.dumps({
            'email': self._email,
            'password': self._password_hash,
            'time': int(time.time()),

            # This seems to be based on the phone's device ID.
            # Not sure how it's used, but it is required.
            'date': 9999999999999999,

            # mobile=True prevents clobbering an active player's session.
            'mobile': True,

            # Taken from the Android app.
            'appVersion': '4.1.2.4',
        }, separators=(',', ':')) # Compact encoding.

        try:
            login_info = self._post_message(url, data)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                raise AlreadyLoggedInException() from e
            elif e.response.status_code == 400 and 'version out of date' in e.response.text:
                raise VersionOutOfDateException() from e
            else:
                raise LoginError(e.response.text, e.response.status_code) from e

        #print(login_info)
        self._session_data = {
            'mobile': True,
            'accountId': login_info['id'],
            'nonce': login_info['Nonce']
        }

    @login_required
    def logout(self):
        url = 'https://api.warframe.com/API/PHP/logout.php'
        self._post_message(url, self._session_data)
        self._session_data = None

    @login_required
    def get_inventory(self):
        url = 'https://api.warframe.com/API/PHP/inventory.php'
        return self._post_message(url, self._session_data)

    def get_recipe_details(self, blueprint_unique_names):
        url = 'https://api.warframe.com/API/PHP/mobileRetrieveRecipes.php'
        data = {
            'recipes': json.dumps([{'ItemType': blueprint} for blueprint in blueprint_unique_names]),
            'mobile': True
        }
        return self._post_message(url, data)

    @login_required
    def start_recipe(self, blueprint_unique_name):
        query_string = urlencode(self._session_data)
        url = 'https://api.warframe.com/API/PHP/startRecipe.php?' + query_string

        recipe_details = self.get_recipe_details([blueprint_unique_name])[0]
        data = json.dumps({
            'RecipeName': blueprint_unique_name,
            'Ids': ['' for ingredient in recipe_details['Ingredients']]
        })
        return self._post_message(url, data)

    @login_required
    def claim_recipe(self, blueprint_unique_name, rush=False):
        query_string = urlencode({**self._session_data,
                                  **{'mobile': 'true', 'recipeName': blueprint_unique_name}})
        url = 'https://api.warframe.com/API/PHP/claimCompletedRecipe.php?' + query_string
        if rush:
            url += '&rush=true'
        return self._post_message(url, {})

    @login_required
    def get_active_extractors(self):
        query_string = urlencode({**self._session_data,
                                  **{'mobile': 'true', 'GetActive': 'true'}})
        url = 'https://api.warframe.com/API/PHP/drones.php?' + query_string
        return self._post_message(url, {})

    @login_required
    def deploy_extractor(self, extractor, system_index):
        extractor_id = extractor['ItemId']['$id']
        query_string = urlencode({**self._session_data,
                                  **{'mobile': 'true',
                                     'droneId': extractor_id,
                                     'systemIndex': system_index}})
        url = 'https://api.warframe.com/API/PHP/drones.php?' + query_string

        extractor_data = data.drones()[extractor['ItemType']]

        post_data = json.dumps({
            'droneRes': extractor_data['uniqueName'],
            'binCount': extractor_data['binCount'],
            'binCapacity': extractor_data['binCapacity'],
            'droneDurability': extractor_data['durability'],
            'fillRate': extractor_data['fillRate'],
            'repairRate': extractor_data['repairRate'],
            'capacityMultipliers': extractor_data['capacityMultiplier'],
            'probabilities': extractor_data['probabilty'], #sic
            'specialities': extractor_data['specialities']
        })
        return self._post_message(url, post_data)
