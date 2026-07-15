import pandas as pd

df = pd.read_parquet(
    "data/followup_q/train-00000-of-00001.parquet"
)

print(df.head())

print("\nColumns:\n")
print(df.columns)

examples = []

for _, row in df.iterrows():

    examples.append({

        "complaint":
            row["Message"],

        "questions":
            row["Questions"]
    })

print(examples[0])