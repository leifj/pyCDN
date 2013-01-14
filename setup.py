#!/usr/bin/env python
from setuptools import setup, find_packages
import sys, os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
NEWS = open(os.path.join(here, 'NEWS.txt')).read()


version = '0.1dev'

install_requires = [
    'eventlet',
    'httplib2'
]


setup(name='pyCDN',
    version=version,
    description="Simple CDN",
    long_description=README + '\n\n' + NEWS,
    classifiers=[
      # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    ],
    keywords='cdn',
    author='Leif Johansson',
    author_email='leifj@mnt.se',
    url='http://blogs.mnt.se',
    license='BSD',
    packages=find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    entry_points={
        'console_scripts':
            ['pycdn=pycdn:main']
    },
    requires=install_requires
)
