from setuptools import setup, find_namespace_packages

setup(
    name="model-predictor",
    version="0.1.4",
    python_requires=">=3.7",
    install_requires=["pandas~=1.2", "html5lib~=1.1", "bs4~=0.0.1", "pulp~=2.4"],
    packages=find_namespace_packages(where="src", exclude=["tests"]),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={"console_scripts": ["sportpools=sportpools.__main__:main"],},
    description="Sportpools tennis selection optimizer.",
    package_data={"sportpools": ["src/sportpools/resources/*"]},
    data_files=[("model", ["logger.ini"])],
)
