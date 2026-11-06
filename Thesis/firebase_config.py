import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

def save_analysis_result(field_name, ndvi_value, health_class, confidence, coordinates=None, grvi_value=None):
    """Save CNN analysis result to Firestore.
    ndvi_value: real NDVI from the NoIR camera, or None for RGB-only uploads.
    grvi_value: greenness (GRVI) from the RGB photo."""
    doc = {
        'field': field_name,
        'ndvi_value': round(ndvi_value, 4) if ndvi_value is not None else None,
        'grvi_value': round(grvi_value, 4) if grvi_value is not None else None,
        'health_class': health_class,
        'confidence': round(confidence, 4),
        'coordinates': coordinates or {},
        'timestamp': datetime.now().isoformat(),
        'analyzed_by': 'CNN_v1'
    }
    db.collection('ndvi_results').add(doc)
    print(f"✅ Saved to Firebase: {health_class} ({confidence:.1%})")
    return doc

def get_field_history(field_name, limit=10):
    """Get recent analysis history for a field."""
    results = (db.collection('ndvi_results')
               .where('field', '==', field_name)
               .order_by('timestamp', direction=firestore.Query.DESCENDING)
               .limit(limit)
               .stream())
    return [r.to_dict() for r in results]