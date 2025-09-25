#!/bin/bash

# Uninstall any old discord packages
pip uninstall -y discord py-cord discord.py

# Install required packages
pip install discord.py==2.2.2
pip install transformers torch flask matplotlib
