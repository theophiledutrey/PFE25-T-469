from setuptools import setup, find_packages

setup(
    name='reef-manager',
    version='0.1.0',
    description='PME Security Infrastructure Manager',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    include_package_data=True,
    install_requires=[
        'click',
        'rich',
        'ruamel.yaml',
        'nicegui',
        'ansible-core',
        'httpx'
        # pytest is for testing, so maybe extras_require, but keeping it simple as per requirements.txt
    ],
    entry_points={
        'console_scripts': [
            'reef=reef.entry:main',
        ],
    },
)
