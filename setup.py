from distutils.core import setup

setup(
    name='chimera_template',
    version='0.0.1',
    packages=['chimera_too', 'chimera_too.controllers'],
    install_requires=['python-telegram-bot', 'pygcn'],
    scripts=[],
    url='http://github.com/astroufsc/chimera-too',
    license='GPL v2',
    author='William Schoenell',
    author_email='wschoenell@gmail.com',
    description='Chimera plugin for Target of Opportunity fast reaction'
)
