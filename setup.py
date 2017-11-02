from setuptools import setup, find_packages

setup(
    name='ccem',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click',
        'numpy'
    ],
    entry_points='''
        [console_scripts]
        culvert_eval=core.culvert_eval:culvert_eval
        culvert_batch=core.culvert_eval:county_processing
    '''
)