from setuptools import setup, find_packages


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='wishful_agent',
    version='0.1.0',
    packages=find_packages(),
    scripts=['wishful_agent/bin/uniflex-agent',
             'wishful_agent/bin/uniflex-broker'],
    url='http://www.wishful-project.eu/software',
    license='',
    author='Piotr Gawlowicz, Mikolaj Chwalisz',
    author_email='{gawlowicz, chwalisz}@tkn.tu-berlin.de',
    description='WiSHFUL Agent Implementation Framework',
    long_description='Implementation of a wireless agent using the unified programming interfaces (UPIs) of the Wishful project.',
    keywords='wireless control',
    install_requires=['apscheduler', 'pyzmq', 'dill', 'protobuf', 'decorator'],
)
