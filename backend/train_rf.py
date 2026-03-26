import os
import torch
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score

def main():
    print("Loading preprocessed PyTorch tensors for Random Forest...")
    if not os.path.exists("train_dataset.pt") or not os.path.exists("preprocessors.joblib"):
        print("Preprocessed data not found. Please run preprocess.py first.")
        return

    # Load preprocessed datasets
    X_train_tensor, y_train_tensor = torch.load("train_dataset.pt")
    X_val_tensor, y_val_tensor = torch.load("val_dataset.pt")
    
    preprocessors = joblib.load("preprocessors.joblib")
    num_classes = preprocessors['num_classes']
    
    # Convert PyTorch tensors back to NumPy arrays for Scikit-Learn
    X_train = X_train_tensor.numpy()
    y_train = y_train_tensor.numpy()
    X_val = X_val_tensor.numpy()
    y_val = y_val_tensor.numpy()
    
    print(f"Loaded {len(X_train)} training samples and {len(X_val)} validation samples. Found {num_classes} classes.")
    
    # Initialize and Train Random Forest
    print("Training Random Forest with 250 Estimators... (This might take a minute)")
    rf_model = RandomForestClassifier(n_estimators=250, random_state=42, n_jobs=-1)
    rf_model.fit(X_train, y_train)
    
    # Evaluate on Train Set
    train_preds = rf_model.predict(X_train)
    train_acc = accuracy_score(y_train, train_preds) * 100
    train_prec = precision_score(y_train, train_preds, average='weighted', zero_division=0) * 100
    
    print("\n--- Training Metrics ---")
    print(f"Accuracy:  {train_acc:.2f}%")
    print(f"Precision: {train_prec:.2f}%")
    
    # Evaluate on Validation Set
    val_preds = rf_model.predict(X_val)
    val_acc = accuracy_score(y_val, val_preds) * 100
    val_prec = precision_score(y_val, val_preds, average='weighted', zero_division=0) * 100
    
    print("\n--- Validation Metrics ---")
    print(f"Accuracy:  {val_acc:.2f}%")
    print(f"Precision: {val_prec:.2f}%")
    
    # Save Model
    print("\nSaving model state...")
    joblib.dump(rf_model, "rf_model.joblib")
    print("Saved to rf_model.joblib (Preprocessors are already saved in preprocessors.joblib)")

if __name__ == "__main__":
    main()
