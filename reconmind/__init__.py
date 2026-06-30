"""
reconmind — agentic AI security research platform.

Milestones implemented:
  M1 — Config system + SQLite schema bootstrap
  M2 — LangGraph agent skeleton + @logged_node decorator
  M3 — LLM client wrapper (Ollama) + real agent calls

Sub-packages:
  reconmind.config      — singleton Config object (import cfg from here)
  reconmind.db          — schema, init_db, migrations
  reconmind.llm         — LLMClient interface + Ollama implementation + factory
  reconmind.platform_   — LangGraph graph, nodes, state, prompts
  reconmind.attacks     — (Milestone 4)
  reconmind.defenses    — (Milestone 5)
  reconmind.analytics   — (Milestone 7)
"""
