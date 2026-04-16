"""Bundled Fluigent package used by the application."""

try:
    __import__("pkg_resources").declare_namespace(__name__)
except ModuleNotFoundError:
    # pkg_resources comes from setuptools and is optional for the bundled SDK.
    pass
