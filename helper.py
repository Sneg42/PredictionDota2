import pandas as pd
import numpy as np

def load_table (file, y_answer, ratio_or_testRows):
        matches = pd.read_csv(file, index_col=0)
        if ratio_or_testRows < 1:
            ratio = len(matches) - int(len(matches)*ratio_or_testRows)
        else:
            ratio = len(matches) - 400
          
        X, y = np.split(matches, [ratio])
        
        X_train = X.drop([y_answer], axis=1)
        y_train = X[y_answer]
    
        X_test = y.drop([y_answer], axis=1)
        y_test = y[y_answer]
        
        return X_train, X_test, y_train, y_test;
    
# Составить список из predict proba больще чем perc
def predict_proba (pred_prob, perc):
        arr = []
        for x in pred_prob:
            if (x[0]>=perc):
                arr.append(0)
                continue
            if(x[1]>=perc):
                arr.append(1)
                continue
            else:
                arr.append('X')
                continue
        return np.array(arr);



