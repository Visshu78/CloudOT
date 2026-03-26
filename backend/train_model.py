import os
import glob
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import precision_score
import joblib

from models import CNN_LSTM

# Check CUDA availability
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

def main():
    # 1. Load Preprocessed Data
    print("Loading preprocessed data...")
    if not os.path.exists("train_dataset.pt") or not os.path.exists("preprocessors.joblib"):
        print("Preprocessed data not found. Please run preprocess.py first.")
        return

    X_train_tensor, y_train_tensor = torch.load("train_dataset.pt")
    
    preprocessors = joblib.load("preprocessors.joblib")
    num_classes = preprocessors['num_classes']
    input_features = preprocessors['input_features']
    
    print(f"Loaded {len(X_train_tensor)} training samples. Found {num_classes} classes.")
    
    dataset = TensorDataset(X_train_tensor, y_train_tensor)
    dataloader = DataLoader(dataset, batch_size=64, shuffle=True)
    
    # 2. Model, Loss, Optimizer
    model = CNN_LSTM(input_features=input_features, num_classes=num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    # 3. Train
    epochs = 60
    print(f"Starting training for {epochs} epochs...")
    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        
        all_preds = []
        all_targets = []
        
        for batch_X, batch_y in dataloader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            running_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            
            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(batch_y.cpu().numpy())
            
        # Calculate metrics for the epoch
        correct = sum(p == t for p, t in zip(all_preds, all_targets))
        total = len(all_targets)
        accuracy = 100 * correct / total
        
        precision = precision_score(all_targets, all_preds, average='weighted', zero_division=0) * 100
        
        avg_loss = running_loss / len(dataloader)
        print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}, Accuracy: {accuracy:.2f}%, Precision: {precision:.2f}%")
        
    print("Training Complete!")
    
    # 4. Save Model state
    print("Saving model state...")
    torch.save(model.state_dict(), "model.pth")
    print("Saved to model.pth (Preprocessors are already saved in preprocessors.joblib)")

if __name__ == "__main__":
    main()
