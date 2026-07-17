#!/usr/bin/env python3
"""Convenience launcher — run NexScope without installing.

    python3 run_nexscope.py --simulate
"""
import sys
from nexscope.app import main

sys.exit(main())
