import os
import glob

base_path = ".venv/lib/python3.14/site-packages/agentdojo/default_suites/v1"
suites = ["workspace", "banking", "travel", "slack"]

total_tasks = 0
for suite in suites:
    # Look for task_*.py or similar files in the suite directory
    suite_dir = os.path.join(base_path, suite)
    if os.path.exists(suite_dir):
        # find tasks
        tasks = glob.glob(os.path.join(suite_dir, "task*.py"))
        print(f"Suite {suite}: {len(tasks)} tasks")
        total_tasks += len(tasks)
        
print(f"Total tasks: {total_tasks}")
