"""Standalone IT remediation engine.

Connects to any IT monitoring source (net-runner simulator or real infrastructure)
via REST + WebSocket, applies rules/ML/LLM analysis, and executes approved actions
by calling back to the source's action endpoints.
"""
