import kagglehub

path = kagglehub.datasets.dataset_download("wcukierski/enron-email-dataset", output_dir = './data/raw')

print(f"Downloaded dataset to {path}")