"""
reconmind.verify
================
Ground Truth Verification Oracle.
Determines the injection_outcome of an attack run.
"""

from reconmind.verify.oracle import verify_run

__all__ = ["verify_run"]
