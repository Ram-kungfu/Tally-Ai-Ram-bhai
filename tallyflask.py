
import os
from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

app = Flask(__name__)

# Firebase Setup
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Error: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_entry', methods=['POST'])
def add_entry():
    try:
        data = request.get_json()
        
        item = data.get('item', 'Unknown Item')
        # सुरक्षित फ्लोट कन्वर्जन
        buy = float(data.get('buy', 0))
        sell = float(data.get('sell', 0))
        
        # Calculation
        gst_rate = 18
        tax_amount = round((sell * gst_rate) / 100, 2)
        profit = round(sell - buy - tax_amount, 2)
        
        record = {
            'item_name': item,
            'purchase_price': buy,
            'sale_price': sell,
            'gst_tax_18': tax_amount,
            'net_profit': profit,
            # स्ट्रिंग के साथ-साथ असली टाइमस्टैम्प भी रखें (Sorting के लिए आसान)
            'timestamp': datetime.now(), 
            'date_str': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'currency': 'INR'
        }
        
        db.collection('Company_Accounts').add(record)
        
        return jsonify({
            "status": "success", 
            "message": f"{item} का डेटा सेव हो गया!",
            "data": {"profit": profit, "tax": tax_amount}
        })

    except ValueError:
        return jsonify({"status": "error", "message": "कृपया सही नंबर भरें (Price digits only)"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
