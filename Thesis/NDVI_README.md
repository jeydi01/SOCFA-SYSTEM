# NDVI Analysis Feature - SoCFA System

## Overview
The NDVI (Normalized Difference Vegetation Index) Analysis feature provides AI-powered vegetation health assessment for agricultural fields using computer vision and machine learning.

## Technical Implementation

### Architecture
- **Frontend**: HTML5 Canvas-based image upload and cropping interface
- **Backend API**: Python Flask server with TensorFlow CNN model
- **Database**: Firebase Realtime Database for storing analysis results
- **Model**: Convolutional Neural Network trained on 64×64 RGB vegetation images

### CNN Model Details
- **Input**: 64×64 RGB images
- **Architecture**: Convolutional Neural Network
- **Output Classes**: Healthy, Moderate, Poor vegetation health
- **Framework**: TensorFlow 2.x
- **Training Data**: Agricultural field images with vegetation health labels

### NDVI Calculation
The system estimates NDVI values using color-based analysis:
- **Healthy**: NDVI 0.6-1.0 (green vegetation)
- **Moderate**: NDVI 0.3-0.6 (yellowing/stressed plants)
- **Poor**: NDVI 0.0-0.3 (brown/dry vegetation)

### API Endpoints
- `POST /analyze`: Accepts base64 image data, returns CNN classification and NDVI estimate
- `GET /history/<field_name>`: Retrieves analysis history from Firebase

## Usage Instructions

### For Defense Presentation:
1. **Load Drone Image**: Click "Load Drone Image" to display pre-generated aerial agricultural imagery
2. **Select Area**: Click and drag on the image to select vegetation area for analysis
3. **Crop**: Click "Crop" to confirm the selection
4. **Analyze**: Click "Analyze" to run CNN classification
5. **View Results**: See health classification, confidence score, and recommendations

### Demo Flow:
- **Step 1**: Load the drone image (shows aerial view of agricultural field)
- **Step 2**: Select different areas (healthy green, moderate yellow-green, stressed yellow)
- **Step 3**: Analyze each area to demonstrate CNN classification accuracy
- **Step 4**: Show results with NDVI values and health recommendations

## Limitations & Future Improvements
- **Current**: RGB-based NDVI estimation (proof of concept)
- **Future**: Integration with actual multispectral drone sensors
- **Accuracy**: Depends on image quality and lighting conditions
- **Training**: Model could be improved with larger, more diverse dataset

## Files Involved
- `ndvi.html`: Main interface
- `ndvi.js`: Frontend logic for image handling and API communication
- `ndvi.css`: Styling and responsive design
- `app.py`: Flask API server with TensorFlow model
- `model/ndvi_cnn.h5`: Trained CNN model
- `firebase_config.py`: Database integration

## Demo Script for Defense
1. Show the NDVI explanation panel
2. Load demo image
3. Demonstrate area selection and cropping
4. Run analysis and show results
5. Explain the CNN model architecture
6. Discuss future improvements with real NDVI sensors