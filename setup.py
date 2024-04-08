import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyjvc",
    version="4.4.21",
    author="iloveicedgreentea2",
    description="A package to control JVC projectors over IP",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/iloveicedgreentea/jvc_projector_improved",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
