import pandas as pd

df = pd.read_parquet(r"C:\Users\debor\OneDrive\Desktop\agentic_healthcare_ai\data\followup_q\train-00000-of-00001.parquet")

print(df.head())
print(df.columns)

df.to_csv(r"C:\Users\debor\OneDrive\Desktop\agentic_healthcare_ai\data\followupq.csv", index=False)

print("CSV saved successfully!")