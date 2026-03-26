import os
import glob
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import joblib
import torch

def preprocess_data():
    print("Starting Data Preprocessing Pipeline...")
    
    data_dir = r"../archive/wataiData/csv/CICIoT2023"
    csv_files = glob.glob(os.path.join(data_dir, "part-*.csv"))
    if not csv_files:
        print("No CSV files found in the dataset folder.")
        return
    
    print(f"Loading data from {csv_files[0]}...")
    df = pd.read_csv(csv_files[0])
    
    # Use an optimized subset for fast 25-epoch 98% accuracy
    df = df.sample(n=min(150000, len(df)), random_state=42)
    
    print("1. Cleaning Data (Dropping NaNs and Infs)...")
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    
    print("2. Separating Features and Labels...")
    X = df.drop(columns=['label'])
    y = df['label']
    
    print("3. Scaling Numerical Features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    print("4. Encoding Labels...")
    label_encoder = LabelEncoder()
    y_encoded = label_encoder.fit_transform(y)
    
    num_classes = len(label_encoder.classes_)
    print(f"Target variable has {num_classes} distinct classes.")
    
    print("5. Splitting into Train and Validation sets...")
    X_train, X_val, y_train, y_val = train_test_split(X_scaled, y_encoded, test_size=0.2, random_state=42)
    
    print("6. Converting to PyTorch Tensors...")
    X_train_tensor = torch.tensor(X_train, dtype=torch.float32)
    y_train_tensor = torch.tensor(y_train, dtype=torch.long)
    
    X_val_tensor = torch.tensor(X_val, dtype=torch.float32)
    y_val_tensor = torch.tensor(y_val, dtype=torch.long)
    
    print("7. Saving Preprocessed Data and Scalers...")
    torch.save((X_train_tensor, y_train_tensor), "train_dataset.pt")
    torch.save((X_val_tensor, y_val_tensor), "val_dataset.pt")
    
    joblib.dump({
        'scaler': scaler,
        'label_encoder': label_encoder,
        'input_features': X.shape[1],
        'num_classes': num_classes
    }, "preprocessors.joblib")
    
    print("preprocessing completed! Files saved as `train_dataset.pt`, `val_dataset.pt`, and `preprocessors.joblib`.")

if __name__ == "__main__":
    preprocess_data()
