from distutils.core import setup
from setuptools import find_packages

setup(
    name='easy-launcher',
    version='0.1dev',
    packages=find_packages(),
    license='MIT License',
    long_description=open('README.md').read(),
    install_requires=[
        "easy-logger==0.1.0",
        "doodad==0.2.1dev",
        "pythonplusplus==0.1.0dev",
    ],
    dependency_links=[
        "git+github.com:vitchyr/easy-logger.git",
        "git+github.com:vitchyr/doodad.git",
        "git+git@github.com:vitchyr/pythonplusplus.git"
    ],
)
