"""Tiled train/val dataset for the boundary-extraction model. Generates
settlements on the fly from settlement_gen.py (never touching the
canonical seed-42 settlement Phase 1 committed, so evaluation on that
settlement in predict_boundaries.py is on data the model never trained
on) and slices each into fixed-size tiles for the U-Net.
"""

import os
import sys

import numpy as np
import torch
from torch.utils.data import Dataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from settlement_gen import build_settlement, rasterize_parcel_mask, render_imagery  # noqa: E402

TRAIN_SEEDS = list(range(1, 13))   # 12 settlements for training
VAL_SEEDS = list(range(101, 104))  # 3 held-out settlements for validation
CANONICAL_SEED = 42                # Phase 1's committed settlement -- never used for training/val


class SettlementTileDataset(Dataset):
    def __init__(self, seeds, tile_size=256, stride=224, augment=False):
        self.tile_size = tile_size
        self.augment = augment
        self._settlements = {}
        self.index = []

        for seed in seeds:
            s = build_settlement(seed)
            img = render_imagery(
                s["boundary"], s["road"], s["canal"], s["parcels_gdf"], s["paths"], s["rng"],
                transform=s["transform"], width=s["width"], height=s["height"],
            )
            mask = rasterize_parcel_mask(s["parcels_gdf"], s["transform"], s["width"], s["height"])
            self._settlements[seed] = (img, mask)

            h, w = mask.shape
            for y in range(0, max(h - tile_size, 0) + 1, stride):
                for x in range(0, max(w - tile_size, 0) + 1, stride):
                    self.index.append((seed, y, x))

    def __len__(self):
        return len(self.index)

    def __getitem__(self, i):
        seed, y, x = self.index[i]
        img, mask = self._settlements[seed]
        t = self.tile_size
        img_tile = img[y:y + t, x:x + t, :]
        mask_tile = mask[y:y + t, x:x + t]

        if img_tile.shape[0] != t or img_tile.shape[1] != t:
            pad_h, pad_w = t - img_tile.shape[0], t - img_tile.shape[1]
            img_tile = np.pad(img_tile, ((0, pad_h), (0, pad_w), (0, 0)))
            mask_tile = np.pad(mask_tile, ((0, pad_h), (0, pad_w)))

        if self.augment:
            if np.random.rand() < 0.5:
                img_tile, mask_tile = img_tile[:, ::-1, :], mask_tile[:, ::-1]
            if np.random.rand() < 0.5:
                img_tile, mask_tile = img_tile[::-1, :, :], mask_tile[::-1, :]

        img_t = torch.from_numpy(np.ascontiguousarray(img_tile)).float().permute(2, 0, 1) / 255.0
        mask_t = torch.from_numpy(np.ascontiguousarray(mask_tile)).float().unsqueeze(0)
        return img_t, mask_t
