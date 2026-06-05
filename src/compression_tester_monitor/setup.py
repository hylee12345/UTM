from setuptools import setup

package_name = "compression_tester_monitor"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", ["launch/red_dot_monitor.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="lee-junyoung",
    maintainer_email="lee-junyoung@todo.todo",
    description="Red marker based compression tester state monitor.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "red_dot_monitor = compression_tester_monitor.red_dot_monitor:main",
        ],
    },
)
