import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyjvc",
    version="0.0.18",
    author="iloveicedgreentea2",
    description="A package to control JVC projectors over IP",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/iloveicedgreentea/jvc_projector_improved",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
