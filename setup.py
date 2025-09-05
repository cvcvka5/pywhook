from setuptools import setup, find_packages

setup(
    name='pywhook',
    version='1.1.5', 
    author='Ulus Vatansever',
    author_email='ulusvatansever@gmail.com',
    description='Python wrapper for webhook.site API',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/cvcvka5/pywhook',
    packages=find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
    install_requires=[
        'requests>=2.20.0'
    ],
)
