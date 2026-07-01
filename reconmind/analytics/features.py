"""
reconmind/analytics/features.py
===============================
Extracts run-level features from events + runs CSVs for ML modeling.
"""

import pandas as pd
import numpy as np

def extract_run_features(runs_df: pd.DataFrame, events_df: pd.DataFrame, audit_results: dict) -> pd.DataFrame:
    # 1. Drop bad rows
    drop_run_ids = audit_results.get("drop_run_ids", [])
    runs_df = runs_df[~runs_df['run_id'].isin(drop_run_ids)].copy()
    
    # Encode defense_active
    def_map = {"none": 0, "heuristic": 1, "judge": 2}
    runs_df['defense_active_encoded'] = runs_df['defense_config'].map(def_map).fillna(0).astype(int)
    
    # 2. Extract features from events
    # We want to pivot events into run-level features
    events_df = events_df[events_df['run_id'].isin(runs_df['run_id'])].copy()
    
    # Calculate event-level metrics
    events_df['output_tokens'] = events_df['output_text'].str.split().str.len().fillna(0)
    events_df['latency_ms'] = pd.to_numeric(events_df['latency_ms'], errors='coerce').fillna(0)
    events_df['defense_confidence_score'] = pd.to_numeric(events_df['defense_confidence_score'], errors='coerce').fillna(0)
    
    # Aggregate to run level
    run_features = []
    
    for run_id, group in events_df.groupby('run_id'):
        feats = {'run_id': run_id}
        
        feats['num_events'] = len(group)
        feats['total_latency_ms'] = group['latency_ms'].sum()
        feats['total_input_tokens'] = group['input_prompt_text'].str.split().str.len().sum()
        feats['total_output_tokens'] = group['output_tokens'].sum()
        
        feats['defense_triggered_any'] = int(any(group['defense_triggered'] == '1'))
        feats['defense_max_confidence'] = group['defense_confidence_score'].max()
        
        # Agent-specific metrics
        intake = group[group['agent_role'] == 'intake']
        retrieval = group[group['agent_role'] == 'retrieval']
        action = group[group['agent_role'] == 'action']
        
        feats['intake_output_tokens'] = intake['output_tokens'].sum() if not intake.empty else 0
        feats['retrieval_output_tokens'] = retrieval['output_tokens'].sum() if not retrieval.empty else 0
        feats['action_output_tokens'] = action['output_tokens'].sum() if not action.empty else 0
        
        feats['tool_was_called'] = int(group['tool_called'].notna().any() and any(group['tool_called'] != ''))
        feats['escalate_called'] = int(any(group['tool_called'] == 'escalate_to_admin'))
        feats['send_email_called'] = int(any(group['tool_called'] == 'send_email'))
        
        # Memory write count heuristic (check if state keys changed - simplistic proxy)
        feats['memory_write_count'] = group['memory_ops_summary'].nunique() - 1 if group['memory_ops_summary'].nunique() > 0 else 0
        
        feats['action_latency_ms'] = action['latency_ms'].sum() if not action.empty else 0
        feats['output_length_ratio'] = (feats['action_output_tokens'] / feats['intake_output_tokens']) if feats['intake_output_tokens'] > 0 else 0
        
        feats['defense_triggered_at_intake'] = int(any(intake['defense_triggered'] == '1'))
        feats['defense_triggered_at_retrieval'] = int(any(retrieval['defense_triggered'] == '1'))
        
        run_features.append(feats)
        
    features_df = pd.DataFrame(run_features)
    
    # 3. Merge with runs table
    merged_df = pd.merge(runs_df[['run_id', 'defense_active_encoded', 'injection_type', 'attack_success_binary']], 
                         features_df, on='run_id', how='inner')
                         
    # Drop bad columns identified in M11
    drop_columns = audit_results.get("drop_columns", [])
    cols_to_drop = [c for c in drop_columns if c in merged_df.columns]
    merged_df = merged_df.drop(columns=cols_to_drop)
    
    # Assert no leakage
    leakage_cols = ['injection_present_this_event', 'injection_outcome', 'expected_signal', 'detecting_defense']
    for col in leakage_cols:
        if col in merged_df.columns:
            raise ValueError(f"LEAKAGE DETECTED: Column '{col}' found in feature set!")
            
    return merged_df
