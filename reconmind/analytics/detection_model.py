"""
reconmind/analytics/detection_model.py
======================================
Trains and evaluates binary classifiers for attack detection.
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, roc_curve

from xgboost import XGBClassifier

from .evaluation import EvaluationReport, get_feature_importance

def prepare_data(features_df: pd.DataFrame):
    # Ensure no leakage columns
    leakage = ['injection_present_this_event', 'injection_outcome', 'expected_signal', 'detecting_defense']
    for l in leakage:
        assert l not in features_df.columns, f"Leakage column {l} found in features!"
        
    y = features_df['attack_success_binary']
    # We also drop non-feature identifying columns and target
    drop_cols = ['run_id', 'injection_type', 'attack_success_binary']
    X = features_df.drop(columns=[c for c in drop_cols if c in features_df.columns])
    
    # Stratified split on label to preserve class balance
    # M11 confirmed these are run-level features (1 row = 1 run), so splitting randomly 
    # correctly splits on run_id groups without data leakage.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    
    return X_train, X_test, y_train, y_test

def train_baseline(X_train: pd.DataFrame, y_train: pd.Series) -> dict:
    models = {}
    
    # 1. Logistic Regression (needs scaling)
    lr_pipe = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42))
    ])
    lr_pipe.fit(X_train, y_train)
    models['Logistic Regression'] = lr_pipe
    
    # 2. Random Forest
    rf_pipe = Pipeline([
        ('classifier', RandomForestClassifier(n_estimators=100, class_weight='balanced', random_state=42))
    ])
    rf_pipe.fit(X_train, y_train)
    models['Random Forest'] = rf_pipe
    
    # 3. XGBoost (GPU Accelerated)
    xgb_pipe = Pipeline([
        ('classifier', XGBClassifier(
            n_estimators=100, 
            scale_pos_weight=(y_train==0).sum()/(y_train==1).sum(), 
            random_state=42, 
            use_label_encoder=False, 
            eval_metric='logloss',
            device='cuda'  # Offloads model training to your RTX 4060 GPU
        ))
    ])
    xgb_pipe.fit(X_train, y_train)
    models['XGBoost'] = xgb_pipe
    
    return models

def evaluate_models(models: dict, X_test: pd.DataFrame, y_test: pd.Series) -> EvaluationReport:
    metrics = {}
    cms = {}
    rocs = {}
    
    feature_importances = pd.DataFrame(index=X_test.columns)
    
    for name, pipeline in models.items():
        model = pipeline.named_steps['classifier']
        
        preds = pipeline.predict(X_test)
        probas = pipeline.predict_proba(X_test)[:, 1]
        
        metrics[name] = {
            'accuracy': accuracy_score(y_test, preds),
            'precision': precision_score(y_test, preds, zero_division=0),
            'recall': recall_score(y_test, preds, zero_division=0),
            'f1': f1_score(y_test, preds, zero_division=0),
            'roc_auc': roc_auc_score(y_test, probas)
        }
        
        cms[name] = confusion_matrix(y_test, preds)
        fpr, tpr, _ = roc_curve(y_test, probas)
        rocs[name] = (fpr, tpr)
        
        # Collect feature importance if available
        imp = get_feature_importance(model, X_test.columns)
        feature_importances[name] = imp
        
    return EvaluationReport(
        metrics=metrics,
        confusion_matrices=cms,
        roc_curves=rocs,
        feature_importances=feature_importances
    )
