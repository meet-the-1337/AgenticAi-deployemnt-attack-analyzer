import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.train_agentdojo import load_agentdojo_samples
import random

def main():
    samples, _ = load_agentdojo_samples(Path("dataset"), "agentdojo_banking_only")
    
    # We want 5 successful attacks and 5 failed attacks
    # An attack is successful if label_outcome in (2, 3) (partial or full_success)
    # An attack is failed if label_outcome == 1 (ignored) and is_attack == True
    
    successful = [s for s in samples if s.is_attack and s.label_outcome in (2, 3)]
    failed = [s for s in samples if s.is_attack and s.label_outcome == 1]
    
    random.seed(42)
    sample_success = random.sample(successful, min(5, len(successful)))
    sample_failed = random.sample(failed, min(5, len(failed)))
    
    print("==================================================")
    print("5 SUCCESSFUL ATTACKS (System executed the payload)")
    print("==================================================")
    for i, s in enumerate(sample_success):
        # Let's print the first text pair (hop 0) where the attack usually lives
        print(f"\n[SUCCESSFUL ATTACK {i+1}] - Run ID: {s.run_id}")
        # text_pairs[0] is typically the first hop
        print("-" * 50)
        print(s.text_pairs[0][:500] + "... [TRUNCATED]")
        
    print("\n\n==================================================")
    print("5 FAILED ATTACKS (System ignored the payload)")
    print("==================================================")
    for i, s in enumerate(sample_failed):
        print(f"\n[FAILED ATTACK {i+1}] - Run ID: {s.run_id}")
        print("-" * 50)
        print(s.text_pairs[0][:500] + "... [TRUNCATED]")

if __name__ == "__main__":
    main()
