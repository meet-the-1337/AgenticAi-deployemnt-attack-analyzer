"""
reconmind/analytics/evaluation.py
=================================
Shared metrics: confusion matrix, ROC, reports.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, roc_curve

from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class EvaluationReport:
    metrics: Dict[str, Dict[str, float]]
    confusion_matrices: Dict[str, np.ndarray]
    roc_curves: Dict[str, tuple]
    feature_importances: pd.DataFrame = None

def get_feature_importance(model, feature_names) -> pd.Series:
    if hasattr(model, 'feature_importances_'):
        return pd.Series(model.feature_importances_, index=feature_names)
    elif hasattr(model, 'coef_'):
        return pd.Series(abs(model.coef_[0]), index=feature_names)
    return pd.Series(0, index=feature_names)

def render_report(report: EvaluationReport, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*50)
    print("MODEL EVALUATION REPORT")
    print("="*50)
    
    for model_name, mets in report.metrics.items():
        print(f"\n[{model_name}]")
        print(f"  Accuracy:  {mets['accuracy']:.4f}")
        print(f"  Precision: {mets['precision']:.4f}")
        print(f"  Recall:    {mets['recall']:.4f}")
        print(f"  F1 Score:  {mets['f1']:.4f}")
        print(f"  ROC-AUC:   {mets['roc_auc']:.4f}")
        
    print("\nNote: Recall is the most critical metric. Missing an attack is worse than a false alarm.")
        
    # Plot ROC Curves
    plt.figure(figsize=(8, 6))
    for model_name, (fpr, tpr) in report.roc_curves.items():
        roc_auc = report.metrics[model_name]['roc_auc']
        plt.plot(fpr, tpr, label=f"{model_name} (AUC = {roc_auc:.2f})")
    plt.plot([0, 1], [0, 1], 'k--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curves - Attack Detection')
    plt.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig(output_dir / 'roc_curves.png', dpi=300)
    plt.close()
    
    # Plot Confusion Matrices
    fig, axes = plt.subplots(1, len(report.confusion_matrices), figsize=(5 * len(report.confusion_matrices), 4))
    if len(report.confusion_matrices) == 1: axes = [axes]
    for ax, (model_name, cm) in zip(axes, report.confusion_matrices.items()):
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax)
        ax.set_title(f"{model_name} Confusion Matrix")
        ax.set_xlabel('Predicted')
        ax.set_ylabel('Actual')
    plt.tight_layout()
    plt.savefig(output_dir / 'confusion_matrices.png', dpi=300)
    plt.close()
    
    # Plot Feature Importance
    if report.feature_importances is not None and not report.feature_importances.empty:
        plt.figure(figsize=(10, 8))
        # Plot top 10 features of the best model (usually RF or XGB)
        top_features = report.feature_importances.mean(axis=1).sort_values(ascending=True).tail(12)
        top_features.plot(kind='barh', color='#388bfd')
        plt.title('Top Feature Importances (Averaged across Tree Models)')
        plt.xlabel('Relative Importance')
        plt.tight_layout()
        plt.savefig(output_dir / 'feature_importance.png', dpi=300)
        plt.close()
        
    print(f"\nFigures saved to {output_dir}")
