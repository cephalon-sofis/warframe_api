from setuptools import setup

setup(name='warframe_api',
      version='0.1',
      description='Access the in-game API for Warframe.',
      url='https://github.com/cephalon-sofis/warframe_api',
      author='Cephalon Sofis',
      author_email='cephalon.sofis@gmail.com',
      license='MIT',
      packages=['warframe_api'],
      install_requires=['requests'],
      zip_safe=False)
