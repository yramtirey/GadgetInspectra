from setuptools import find_packages, setup

package_name = 'gadget_inspectra_core'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),

        ("share/" + package_name + "/launch",
            ["launch/inspection_system.launch.py"],
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        "console_scripts": [
            "inspection_controller = gadget_inspectra_core.inspection_controller:main",
            "operator_console = gadget_inspectra_core.operator_console:main",
        ],
    },
)
