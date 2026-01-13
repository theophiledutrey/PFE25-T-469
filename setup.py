from setuptools import setup, find_packages

setup(
    name='reef-manager',
    version='0.1.0',
    description='PME Security Infrastructure Manager',
    packages=find_packages(),
    py_modules=['entry', 'main'],
    include_package_data=True,
    install_requires=[
        'click',
        'rich',
        'ruamel.yaml',
        'nicegui',
        'ansible-core'
        # pytest is for testing, so maybe extras_require, but keeping it simple as per requirements.txt
    ],
    entry_points={
        'console_scripts': [
            'reef=entry:main',
        ],
    },
)
