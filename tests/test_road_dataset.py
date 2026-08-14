import os
import sys

REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_DIR)

from road_dataset import RoadFollowingDataset
from torch.utils.data import DataLoader
import cv2
import torch


def transform(image):
    """Transform tối giản, không phụ thuộc torchvision."""
    image = cv2.resize(image, (224, 224))
    image = torch.from_numpy(image).permute(2, 0, 1)
    return image.float() / 255.0

SESSION_DIR = os.path.join(REPO_DIR, "datasets", "sess_20260813_130408")
IMAGES_DIR = (
    os.path.join(SESSION_DIR, "images")
    if os.path.isdir(os.path.join(SESSION_DIR, "images"))
    else SESSION_DIR
)

dataset = RoadFollowingDataset(
    csv_path=os.path.join(SESSION_DIR, "labels.csv"),
    images_dir=IMAGES_DIR,
    transform=transform,
)

print(f"Tổng số sample: {len(dataset)}")

loader = DataLoader(dataset, batch_size=4, shuffle=True)
images, extras, labels = next(iter(loader))

print("images shape:", images.shape)   # kỳ vọng: (4, 3, 224, 224)
print("extras shape:", extras.shape)   # kỳ vọng: (4, 2)
print("labels shape:", labels.shape)   # kỳ vọng: (4, 1)
print("extras sample:", extras[0])
print("label sample:", labels[0])
