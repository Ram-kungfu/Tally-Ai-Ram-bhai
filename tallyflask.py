import os
from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

app = Flask(__name__)

# --- Firebase Setup ---
# Render पर Secret Files /etc/secrets/ फोल्डर में होती हैं
firebase_path = "/etc/secrets/serviceAccountKey.json"

try:
    if not firebase_admin._apps:
        # यहाँ हमने सही रास्ता (Path) डाल दिया है
        if os.path.exists(firebase_path):
            cred = credentials.Certificate(firebase_path)
            firebase_admin.initialize_app(cred)
            print("Firebase connected successfully!")
        else:
            # अगर फाइल वहां नहीं है, तो लोकल चेक करेगा (Testing के लिए)
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            
    db = firestore.client()
except Exception as e:
    print(f"Firebase Error: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_entry', methods=['POST'])
def add_entry():
    try:
        data = request.get_json()
        
        item = data.get('item', 'Unknown Item')
        buy = float(data.get('buy', 0))
        sell = float(data.get('sell', 0))
        
        # Calculation Logic
        gst_rate = 18
        tax_amount = round((sell * gst_rate) / 100, 2)
        profit = round(sell - buy - tax_amount, 2)
        
        record = {
            'item_name': item,
            'purchase_price': buy,
            'sale_price': sell,
            'gst_tax_18': tax_amount,
            'net_profit': profit,
            'timestamp': datetime.now(), 
            'date_str': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'currency': 'INR'
        }
        
        # Firestore में डेटा सेव करना
        db.collection('Company_Accounts').add(record)
        
        return jsonify({
            "status": "success", 
            "message": f"{item} का डेटा सेव हो गया!",
            "data": {"profit": profit, "tax": tax_amount}
        })

    except ValueError:
        return jsonify({"status": "error", "message": "कृपया सही नंबर भरें"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Render के लिए पोर्ट 5000 के बजाय environment port लेना बेहतर है
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
