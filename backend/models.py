import torch
import torch.nn as nn

class CNN_LSTM(nn.Module):
    def __init__(self, input_features, num_classes):
        super(CNN_LSTM, self).__init__()
        self.conv1 = nn.Conv1d(in_channels=1, out_channels=64, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm1d(64)
        self.conv2 = nn.Conv1d(in_channels=64, out_channels=128, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(128)
        self.relu = nn.ReLU()
        self.pool = nn.MaxPool1d(kernel_size=2)
        
        self.lstm = nn.LSTM(input_size=128, hidden_size=128, num_layers=2, batch_first=True, dropout=0.2)
        
        self.fc1 = nn.Linear(128, 64)
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(64, num_classes)

    def forward(self, x):
        x = x.unsqueeze(1)
        
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        
        x = self.conv2(x)
        x = self.bn2(x)
        x = self.relu(x)
        
        x = self.pool(x)
        
        # Prepare for LSTM: (batch_size, sequence_length, input_size)
        x = x.permute(0, 2, 1)
        
        # LSTM
        lstm_out, _ = self.lstm(x)
        last_out = lstm_out[:, -1, :] 
        
        # Fully Connected
        x = self.fc1(last_out)
        x = self.relu(x)
        x = self.dropout(x)
        out = self.fc2(x)
        return out
