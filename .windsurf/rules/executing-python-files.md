---
trigger: always_on
---

When executing python files, use python3 instead of python because that adheres to project's venv. Additionally, if you haven't activated venv yet, you have to activate it or else the execution will fail with module not found exception. For this project, it's venv is in project's root, so activate it by running "source .venv/bin/activate" - do NOT modify this command if you are willing to activate.