from glob import glob

from setuptools import setup

package_name = "roi_image_cropper"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="lee-junyoung",
    maintainer_email="lee-junyoung@todo.todo",
    description="Simple ROS2 image ROI cropper.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "roi_image_cropper = roi_image_cropper.roi_image_cropper:main",
        ],
    },
)
