#!/usr/bin/env python3
import argparse
import os
import urllib.request
import zipfile

MOVIELENS_100K_ZIP = "https://files.grouplens.org/datasets/movielens/ml-100k.zip"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="data/movielens", help="Where to extract dataset")
    ap.add_argument("--force", action="store_true", help="Re-download and re-extract")
    args = ap.parse_args()

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)

    zip_path = os.path.join(out_dir, "ml-100k.zip")
    extract_dir = os.path.join(out_dir, "ml-100k")

    if args.force:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    if not os.path.exists(zip_path):
        print(f"Downloading: {MOVIELENS_100K_ZIP}")
        urllib.request.urlretrieve(MOVIELENS_100K_ZIP, zip_path)
        print(f"Saved to: {zip_path}")
    else:
        print(f"Zip already exists: {zip_path}")

    if args.force and os.path.isdir(extract_dir):
        # simple cleanup: remove extracted files
        for root, _, files in os.walk(extract_dir):
            for f in files:
                os.remove(os.path.join(root, f))

    if not os.path.isdir(extract_dir) or not os.listdir(extract_dir):
        print(f"Extracting to: {extract_dir}")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(out_dir)
        print("Done.")
    else:
        print(f"Already extracted: {extract_dir}")

if __name__ == "__main__":
    main()
