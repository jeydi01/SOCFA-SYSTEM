#!/usr/bin/env python3
"""
NDVI CNN Training Script - Optimized for RTX 2050 + 8GB RAM
70% Train / 20% Validation / 10% Test split
"""

import os
import glob as glob_module
import random
import re
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns


# ─────────────────────────────────────────────
# FIX RANDOMNESS
# ─────────────────────────────────────────────
SEED = 42
os.environ['PYTHONHASHSEED'] = str(SEED)
random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
IMAGE_SIZE    = (64, 64)
BATCH_SIZE    = 16
EPOCHS        = 20
LEARNING_RATE = 0.001
DATASET_DIR   = 'dataset'
CLASSES       = ['healthy', 'moderate', 'poor']
NUM_CLASSES   = len(CLASSES)

# ─────────────────────────────────────────────
# GPU SETUP
# ─────────────────────────────────────────────
gpus = tf.config.list_physical_devices('GPU')
if gpus:
    try:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        print(f"✅ GPU found: {len(gpus)} GPU(s) — RTX 2050 will be used!")
    except RuntimeError as e:
        print(f"⚠️ GPU setup error: {e}")
else:
    print("⚠️ No GPU found — using CPU")

# ─────────────────────────────────────────────
# LOAD DATASET
# ─────────────────────────────────────────────

def load_dataset(dataset_dir):
    print(f"\n📂 Loading dataset from '{dataset_dir}'...")
    all_images = []
    all_labels = []

    for class_idx, class_name in enumerate(CLASSES):
        class_dir = os.path.join(dataset_dir, class_name)
        if not os.path.exists(class_dir):
            print(f"  ⚠️  Missing: {class_dir}")
            continue

        files = []
        for ext in ['*.png', '*.PNG', '*.jpg', '*.JPG']:
            files += glob_module.glob(os.path.join(class_dir, ext))
        files = list(set(files))  # remove duplicates

        all_images.extend(files)
        all_labels.extend([class_idx] * len(files))
        print(f"  {class_name:10s}: {len(files)} images")

    print(f"  TOTAL: {len(all_images)} images\n")
    return all_images, all_labels


def source_photo(filepath):
    """Photo a tile was cut from, read from its file name.
    prepare_rgb_dataset.py names tiles NNNN_<source>_<photo>_r<row>c<col>.jpg,
    so dropping the tile number and grid position leaves the photo.
    Files not named that way count as their own photo."""
    stem = os.path.splitext(os.path.basename(filepath))[0]
    m = re.match(r'^\d{4}_(.+)_r\d+c\d+$', stem)
    return m.group(1) if m else stem


def split_by_photo(image_paths, labels, train_frac=0.70, val_frac=0.20):
    """Whole photos go to one split, so the test set only has unseen photos."""
    groups = {}
    for path, label in zip(image_paths, labels):
        groups.setdefault(source_photo(path), []).append((path, label))
    photos = sorted(groups)
    random.Random(SEED).shuffle(photos)

    total = len(image_paths)
    splits = {'train': [], 'val': [], 'test': []}
    count = 0
    for photo in photos:
        if count < total * train_frac:
            name = 'train'
        elif count < total * (train_frac + val_frac):
            name = 'val'
        else:
            name = 'test'
        splits[name].extend(groups[photo])
        count += len(groups[photo])

    seen = {n: {source_photo(p) for p, _ in items} for n, items in splits.items()}
    assert not (seen['train'] & seen['test']) and not (seen['train'] & seen['val'])         and not (seen['val'] & seen['test']), "a photo landed in two splits"
    print(f"Split by source photo: {len(photos)} photos, no photo shared between splits")
    for n, items in splits.items():
        per_class = [sum(1 for _, l in items if l == i) for i in range(NUM_CLASSES)]
        print(f"  {n:5s}: {len(items):4d} tiles from {len(seen[n]):4d} photos   "
              + "  ".join(f"{c}={k}" for c, k in zip(CLASSES, per_class)))
    return ([p for p, _ in splits['train']], [l for _, l in splits['train']],
            [p for p, _ in splits['val']],   [l for _, l in splits['val']],
            [p for p, _ in splits['test']],  [l for _, l in splits['test']])


def parse_image(filepath, label):
    image = tf.io.read_file(filepath)
    image = tf.image.decode_png(image, channels=3)
    image = tf.image.resize(image, IMAGE_SIZE)
    image = tf.cast(image, tf.float32) / 255.0
    label = tf.one_hot(label, NUM_CLASSES)
    return image, label


def augment(image, label):
    image = tf.image.random_flip_left_right(image, seed=SEED)
    image = tf.image.random_flip_up_down(image, seed=SEED)
    image = tf.image.random_brightness(image, 0.2, seed=SEED)
    image = tf.image.random_contrast(image, 0.8, 1.2, seed=SEED)
    image = tf.clip_by_value(image, 0.0, 1.0)
    return image, label

def build_tf_dataset(image_paths, labels, training=False):
    dataset = tf.data.Dataset.from_tensor_slices((image_paths, labels))
    if training:
        dataset = dataset.shuffle(buffer_size=1000, seed=SEED)
    dataset = dataset.map(parse_image, num_parallel_calls=tf.data.AUTOTUNE)
    if training:
        dataset = dataset.map(augment, num_parallel_calls=tf.data.AUTOTUNE)
    dataset = dataset.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    return dataset

# ─────────────────────────────────────────────
# CNN MODEL
# ─────────────────────────────────────────────

def create_model():
    # No BatchNormalization: with batch size 16 and ~1,000 tiles its running
    # statistics never settle, so the model collapsed to one class at evaluation.
    model = keras.Sequential([
        layers.Input(shape=(IMAGE_SIZE[0], IMAGE_SIZE[1], 3)),

        layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        layers.Conv2D(256, (3, 3), activation='relu', padding='same'),
        layers.MaxPooling2D((2, 2)),
        layers.Dropout(0.25),

        layers.Flatten(),
        layers.Dense(256, activation='relu'),
        layers.Dropout(0.5),

        layers.Dense(NUM_CLASSES, activation='softmax')
    ])

    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    return model

# ─────────────────────────────────────────────
# TRAIN
# ─────────────────────────────────────────────

def train():
    print("=" * 50)
    print("NDVI CNN Training — Seasonal Separation Approach")
    print("=" * 50)

    image_paths, labels = load_dataset(DATASET_DIR)

    if len(image_paths) == 0:
        print("❌ No images found! Run prepare_ndvi_dataset.py first.")
        return

    # 70 / 20 / 10 split by source photo (tiles of one photo never cross splits)
    (train_paths, train_labels,
     val_paths,   val_labels,
     test_paths,  test_labels) = split_by_photo(image_paths, labels)
    print()

    train_ds = build_tf_dataset(train_paths, train_labels, training=True)
    val_ds   = build_tf_dataset(val_paths,   val_labels,   training=False)
    test_ds  = build_tf_dataset(test_paths,  test_labels,  training=False)

    model = create_model()
    model.summary()

    os.makedirs('model', exist_ok=True)
    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor='val_loss', patience=5, restore_best_weights=True),
        keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss', factor=0.5, patience=3, min_lr=1e-6),
        keras.callbacks.ModelCheckpoint(
            'model/ndvi_cnn_best.h5',
            monitor='val_accuracy', save_best_only=True, mode='max')
    ]

    print("\n🚀 Training started...")
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=EPOCHS,
        callbacks=callbacks,
        verbose=1
    )

    # ─────────────────────────────────────────
    # EVALUATE
    # ─────────────────────────────────────────
    print("\n📊 Evaluating on test set...")
    y_pred, y_true = [], []

    for images, labels_batch in test_ds:
        preds = model.predict(images, verbose=0)
        y_pred.extend(np.argmax(preds, axis=1))
        y_true.extend(np.argmax(labels_batch.numpy(), axis=1))

    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=CLASSES))

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=CLASSES, yticklabels=CLASSES)
    plt.title('Confusion Matrix')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.savefig('model/confusion_matrix.png')
    plt.close()

    # Training history
    plt.figure(figsize=(12, 4))
    plt.subplot(1, 2, 1)
    plt.plot(history.history['accuracy'],     label='Train Accuracy')
    plt.plot(history.history['val_accuracy'], label='Val Accuracy')
    plt.title('Model Accuracy')
    plt.xlabel('Epoch')
    plt.ylabel('Accuracy')
    plt.legend()

    plt.subplot(1, 2, 2)
    plt.plot(history.history['loss'],     label='Train Loss')
    plt.plot(history.history['val_loss'], label='Val Loss')
    plt.title('Model Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()

    plt.tight_layout()
    plt.savefig('model/training_history.png')
    plt.close()

    test_loss, test_acc = model.evaluate(test_ds, verbose=0)
    print(f"\n{'='*50}")
    print(f"✅ Final Test Accuracy: {test_acc*100:.2f}%")
    print(f"{'='*50}")
    print("Model saved:  model/ndvi_cnn_best.h5")
    print("Plots saved:  model/confusion_matrix.png")
    print("              model/training_history.png")


if __name__ == "__main__":
    train()