"""Setup for icxblock XBlock."""

import os
from setuptools import setup


def package_data(pkg, roots):
    """Generic function to find package_data.

    All of the files under each of the `roots` will be declared as package
    data for package `pkg`.

    """
    data = []
    for root in roots:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}


setup(
    name='icxblock-xblock',
    version='0.2',
    description='icxblock XBlock',   # TODO: write a better description.
    license='UNKNOWN',          # TODO: choose a license: 'AGPL v3' and 'Apache 2.0' are popular.
    packages=[
        'icxblock',
    ],
    install_requires=[
        'XBlock==1.2.9',
        'lxml==4.6.3',
        'web-fragments==0.2.2',
    ],
    entry_points={
        'xblock.v1': [
            'icxblock = icxblock:CertificateXBlock',
        ]
    },
    package_data=package_data("icxblock", ["static", "public"]),
)
