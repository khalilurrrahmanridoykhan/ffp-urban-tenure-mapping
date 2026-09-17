"""Phase 2: trains the parcel-footprint segmentation model on synthetic
settlements (seeds 1-12 train, 101-103 validation -- never the canonical
seed-42 settlement Phase 1 committed, so predict_boundaries.py evaluates
on a settlement the model has genuinely never seen).

Run: python3 model/train.py [--epochs 20]
Output: model/checkpoints/unet_boundary.pt, model/training_log.md
"""

import argparse
import os
import time

import torch
from torch.utils.data import DataLoader

from dataset import TRAIN_SEEDS, VAL_SEEDS, SettlementTileDataset
from unet import UNet

CKPT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
LOG_PATH = os.path.join(os.path.dirname(__file__), "training_log.md")


def dice_loss(logits, target, eps=1e-6):
    probs = torch.sigmoid(logits)
    inter = (probs * target).sum(dim=(1, 2, 3))
    union = probs.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3))
    return 1 - ((2 * inter + eps) / (union + eps)).mean()


def iou(logits, target, threshold=0.5, eps=1e-6):
    preds = (torch.sigmoid(logits) > threshold).float()
    inter = (preds * target).sum(dim=(1, 2, 3))
    union = ((preds + target) > 0).float().sum(dim=(1, 2, 3))
    return ((inter + eps) / (union + eps)).mean().item()


def main(epochs, batch_size, lr):
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Device: {device}")

    train_ds = SettlementTileDataset(TRAIN_SEEDS, augment=True)
    val_ds = SettlementTileDataset(VAL_SEEDS, augment=False)
    print(f"Train tiles: {len(train_ds)}, val tiles: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = UNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    bce = torch.nn.BCEWithLogitsLoss()

    os.makedirs(CKPT_DIR, exist_ok=True)
    log_lines = ["# Training log\n", "| epoch | train_loss | val_iou | seconds |", "|---|---|---|---|"]

    for epoch in range(1, epochs + 1):
        t0 = time.time()
        model.train()
        total_loss = 0.0
        for imgs, masks in train_loader:
            imgs, masks = imgs.to(device), masks.to(device)
            opt.zero_grad()
            logits = model(imgs)
            loss = bce(logits, masks) + dice_loss(logits, masks)
            loss.backward()
            opt.step()
            total_loss += loss.item() * imgs.size(0)
        train_loss = total_loss / len(train_ds)

        model.eval()
        ious = []
        with torch.no_grad():
            for imgs, masks in val_loader:
                imgs, masks = imgs.to(device), masks.to(device)
                logits = model(imgs)
                ious.append(iou(logits, masks))
        val_iou = sum(ious) / len(ious)
        dt = time.time() - t0

        line = f"| {epoch} | {train_loss:.4f} | {val_iou:.4f} | {dt:.1f} |"
        print(line)
        log_lines.append(line)

    torch.save(model.state_dict(), os.path.join(CKPT_DIR, "unet_boundary.pt"))
    with open(LOG_PATH, "w") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"Saved checkpoint to {CKPT_DIR}/unet_boundary.pt")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    main(args.epochs, args.batch_size, args.lr)
