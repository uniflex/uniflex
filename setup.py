from setuptools import setup, find_packages


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='uniflex',
    version='0.1.0',
    packages=find_packages(),
    scripts=['uniflex/bin/uniflex-agent',
             'uniflex/bin/uniflex-broker'],
    url='https://github.com/uniflex',
    license='MIT',
    author='Piotr Gawlowicz, Mikolaj Chwalisz',
    author_email='{gawlowicz, chwalisz}@tkn.tu-berlin.de',
    description='UniFlex Framework',
    long_description='Implementation of UniFlex Framework',
    keywords='wireless control',
    install_requires=['apscheduler', 'pyzmq', 'dill', 'protobuf', 'decorator'],
)
