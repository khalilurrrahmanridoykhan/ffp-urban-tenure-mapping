"""Tiled train/val dataset for the boundary-extraction model, built from
real drone imagery + real OSM building footprints (see
scripts/real_data_source.py) over 12 train + 3 val AOIs, all spatially
disjoint from each other and from the canonical AOI Phase 1 committed --
so evaluation in predict_boundaries.py is on real imagery the model
never trained on, not just an unseen procedural variation.
"""

import os
import sys

import numpy as np
import torch
from torch.utils.data import Dataset

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from real_data_source import AOIS_4326, build_real_settlement, get_all_buildings  # noqa: E402
from settlement_gen import rasterize_parcel_mask  # noqa: E402

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".oam_cache")

TRAIN_AOIS = [k for k in AOIS_4326 if k.startswith("train_")]  # 12 AOIs for training
VAL_AOIS = [k for k in AOIS_4326 if k.startswith("val_")]      # 3 held-out AOIs for validation
CANONICAL_AOI = "canonical"                                     # Phase 1's committed AOI -- never used for training/val


class SettlementTileDataset(Dataset):
    def __init__(self, aoi_keys, tile_size=256, stride=224, augment=False):
        self.tile_size = tile_size
        self.augment = augment
        self._settlements = {}
        self.index = []

        all_buildings = get_all_buildings(cache_path=os.path.join(CACHE_DIR, "mburahati_buildings.geojson"))

        for key in aoi_keys:
            s = build_real_settlement(AOIS_4326[key], all_buildings, cache_dir=CACHE_DIR)
            mask = rasterize_parcel_mask(s["parcels_gdf"], s["transform"], s["width"], s["height"])
            self._settlements[key] = (s["image"], mask)

            h, w = mask.shape
            for y in range(0, max(h - tile_size, 0) + 1, stride):
                for x in range(0, max(w - tile_size, 0) + 1, stride):
                    self.index.append((key, y, x))

    def __len__(self):
        return len(self.index)

    def __getitem__(self, i):
        key, y, x = self.index[i]
        img, mask = self._settlements[key]
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
