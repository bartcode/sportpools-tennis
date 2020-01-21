from setuptools import find_packages
from setuptools import setup

setup(
    name='sportpools-predictor',
    version='0.1.3',
    python_requires='>=3.7',
    install_requires=[
        'pandas==0.25.3',
        'html5lib==1.0.1',
        'bs4==0.0.1',
        'pulp==2.0'
    ],
    packages=find_packages(),
    include_package_data=True,
    entry_points={
        'console_scripts': ['sportpools=src.__main__:main'],
    },
    description='Sportpools tennis selection optimizer.',
    data_files=[('sportpools', ['logger.ini'])]
)
