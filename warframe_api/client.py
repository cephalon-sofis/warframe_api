import json
import time
import hashlib
from urllib.parse import urlencode
from functools import wraps

from . import data

from .exceptions import *

import requests

def login_required(func):
    @wraps(func)
    def wrap(self, *args, **kwargs):
        if not self._session_data:
            raise NotLoggedInException()

        return func(self, *args, **kwargs)
    return wrap

class Client():
    URL_BASE = 'https://api.warframe.com'

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
        headers = {
            # This is the Android app's ID.
            'X-Titanium-Id': '9bbd1ddd-f7f2-402d-9777-873f458cb50c',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': '',
        }

        r = requests.post(url, data=data, headers=headers)
        r.raise_for_status()
        try:
            return r.json()
        except json.decoder.JSONDecodeError:
            return r.text

    def _get_message(self, url):
        headers = {
            # This is the Android app's ID.
            'X-Titanium-Id': '9bbd1ddd-f7f2-402d-9777-873f458cb50c',
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': '',
        }

        r = requests.get(url, headers=headers)
        r.raise_for_status()
        try:
            return r.json()
        except json.decoder.JSONDecodeError:
            return r.text

    def login(self):
        url = Client.URL_BASE + '/API/PHP/login.php'

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
            'appVersion': '4.2.8.0',
        })

        try:
            login_info = self._post_message(url, data)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                raise AlreadyLoggedInException() from e
            elif e.response.status_code == 400 and 'new hardware detected' in e.response.text:
                print(e.response.text)
                code = input('please check email and input a code. \n> ')
                try:
                    self._get_message(Client.URL_BASE + '/API/PHP/authorizeNewHwid.php?code={0}&mobile=true'.format(code))
                except requests.exceptions.HTTPError as e:
                    print(e.response.text)
                    print(e.response.status_code)
                pass
            elif e.response.status_code == 400 and 'version out of date' in e.response.text:
                raise VersionOutOfDateException() from e
            else:
                raise LoginError(e.response.text, e.response.status_code) from e

        self._session_data = {
            'mobile': 'true',
            'accountId': login_info['id'],
            'nonce': login_info['Nonce']
        }
        return login_info

    @login_required
    def logout(self):
        url = Client.URL_BASE + '/API/PHP/logout.php'
        self._post_message(url, self._session_data)
        self._session_data = None

    @login_required
    def get_inventory(self):
        url = Client.URL_BASE + '/API/PHP/inventory.php'
        return self._post_message(url, self._session_data)

    def get_recipe_details(self, blueprint_unique_names):
        url = Client.URL_BASE + '/API/PHP/mobileRetrieveRecipes.php'
        data = {
            'recipes': json.dumps([{'ItemType': blueprint} for blueprint in blueprint_unique_names]),
            'mobile': True
        }
        return self._post_message(url, data)

    @login_required
    def start_recipe(self, blueprint_unique_name, inventory=None):
        if inventory is None:
            inventory = self.get_inventory()

        for recipe in inventory['PendingRecipes']:
            if recipe['ItemType'] == blueprint_unique_name:
                # The server will let you start a recipe more than once,
                # but the game gets really confused by this when you go to claim them.
                # It's best to not do suspicious things like that.
                raise RecipeAlreadyStartedException()

        query_string = urlencode(self._session_data)
        url = Client.URL_BASE + '/API/PHP/startRecipe.php?' + query_string

        recipe_details = self.get_recipe_details([blueprint_unique_name])[0]
        data = json.dumps({
            'RecipeName': blueprint_unique_name,
            # This is what the mobile app does. It's probably why you can't
            # start recipes that include weapons as ingredients.
            'Ids': ['' for ingredient in recipe_details['Ingredients']]
        })
        return self._post_message(url, data)

    @login_required
    def claim_recipe(self, blueprint_unique_name, rush=False, inventory=None):
        if inventory is None:
            inventory = self.get_inventory()

        for recipe in inventory['PendingRecipes']:
            if recipe['ItemType'] == blueprint_unique_name:
                if not rush and time.time() < recipe['CompletionDate']['sec']:
                    raise RecipeNotFinishedException()
                break
        else:
            # Can't claim a recipe that hasn't been started, and it might
            # look suspicious to make a request to do so.
            raise RecipeNotStartedException()

        query_string = urlencode({**self._session_data,
                                  **{'recipeName': blueprint_unique_name}})
        url = Client.URL_BASE + '/API/PHP/claimCompletedRecipe.php?' + query_string
        if rush:
            url += '&rush=true'
        return self._post_message(url, {})

    @login_required
    def get_active_extractors(self):
        query_string = urlencode({**self._session_data,
                                  **{'GetActive': 'true'}})
        url = Client.URL_BASE + '/API/PHP/drones.php?' + query_string
        response = self._post_message(url, {})
        return response.get('ActiveDrones', [])

    @login_required
    def deploy_extractor(self, extractor, system_index, active_extractors=None):
        extractor_id = extractor['ItemId']['$id']
        if active_extractors is None:
            active_extractors = self.get_active_extractors()

        for active_extractor in active_extractors:
            if active_extractor['ItemId']['$id'] == extractor_id:
                raise ExtractorAlreadyDeployedException()

        query_string = urlencode({**self._session_data,
                                  **{'droneId': extractor_id,
                                     'systemIndex': system_index}})
        url = Client.URL_BASE + '/API/PHP/drones.php?' + query_string
        post_data = data.extractor_json(extractor['ItemType'])
        return self._post_message(url, post_data)

    @login_required
    def collect_extractor(self, extractor, force_if_early=False, active_extractors=None):
        extractor_id = extractor['ItemId']['$id']
        if active_extractors is None:
            active_extractors = self.get_active_extractors()

        for active_extractor in active_extractors:
            if active_extractor['ItemId']['$id'] == extractor_id:
                deploy_time = active_extractor['DeployTime']['sec'] + float(active_extractor['DeployTime']['usec']) / 1e6
                fill_time = data.drones()[active_extractor['ItemType']]['fillRate'] * 60 * 60
                finish_time = deploy_time + fill_time
                if not force_if_early and time.time() < finish_time:
                    raise ExtractorNotFinishedException()
                break
        else:
            raise ExtractorNotDeployedException()

        query_string = urlencode({**self._session_data,
                                  **{'collectDroneId': extractor_id,
                                     'binIndex': -1}})
        url = Client.URL_BASE + '/API/PHP/drones.php?' + query_string
        post_data = data.extractor_json(extractor['ItemType'])
        return self._post_message(url, post_data)

    @login_required
    def get_inbox(self):
        query_string = urlencode(self._session_data)
        url = Client.URL_BASE + '/API/PHP/inbox.php?' + query_string
        return self._post_message(url, {})

    @login_required
    def get_friends(self):
        query_string = urlencode(self._session_data)
        url = Client.URL_BASE + '/API/PHP/getFriends.php?' + query_string
        return self._post_message(url, {})

    @login_required
    def get_guild(self):
        query_string = urlencode(self._session_data)
        url = Client.URL_BASE + '/API/PHP/getGuild.php?' + query_string
        return self._post_message(url, {})

    @login_required
    def get_guild_log(self):
        query_string = urlencode(self._session_data)
        url = Client.URL_BASE + '/API/PHP/getGuildLog.php?' + query_string
        return self._post_message(url, {})
