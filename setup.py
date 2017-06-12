from setuptools import setup

__version__ = 0.1
__release__ = 0.1

setup(name='ezpool',
	  version=__version__,
	  description='Pool of workers for scientific computing',
	  long_description='Pool of workers for scientific computing',
	  author='Marc Sanchez Net',
	  author_email='msancheznet@gmail.com',
	  license='Apache License, Version 2.0',
	  url='',
	  packages=['ezpool'],						# Path is relative to the setup.py location
	  package_data={'':'docs.build.html'},		# Distribute the html docs
	  install_requires=[
	  	'Pyro4>=4.59',
	  	'selectors34>=1.1',
	  	'serpent>=1.19',
	  ]
	)