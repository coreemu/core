from setuptools import setup, find_packages

setup(
    name="chatapp",
    version="0.1.0",
    packages=find_packages(),
    description="Chat App",
    entry_points={
        "console_scripts": [
            "chatapp-client = chatapp.client:main",
            "chatapp-server = chatapp.server:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.6",
)
