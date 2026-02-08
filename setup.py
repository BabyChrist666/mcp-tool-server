"""Setup script for mcp-tool-server."""

from setuptools import setup, find_packages

setup(
    name="mcp-tool-server",
    version="0.1.0",
    description="Production MCP server with file, shell, and search tools",
    author="BabyChrist666",
    author_email="",
    url="https://github.com/BabyChrist666/mcp-tool-server",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
