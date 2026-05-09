import os
from flask import Flask, render_template, request, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# यहाँ पक्का करें कि Flask को पता हो कि templates फोल्डर कहाँ है
app = Flask(__name__, template_folder='templates')

# --- Firebase Setup ---
firebase_path = "/etc/secrets/serviceAccountKey.json"
local_path = "serviceAccountKey.json"

db = None # शुरुआत में खाली रखें

try:
    if not firebase_admin._apps:
        if os.path.exists(firebase_path):
            cred = credentials.Certificate(firebase_path)
            firebase_admin.initialize_app(cred)
            print("Connected using Render Secrets")
        elif os.path.exists(local_path):
            cred = credentials.Certificate(local_path)
            firebase_admin.initialize_app(cred)
            print("Connected using Local file")
        else:
            print("WARNING: No serviceAccountKey.json found anywhere!")
            
    if firebase_admin._apps:
        db = firestore.client()
except Exception as e:
    print(f"Firebase Setup Error: {e}")

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        # अगर index.html नहीं मिली, तो ये मैसेज दिखेगा
        return f"Error: HTML file not found in templates folder. Details: {e}", 500

@app.route('/add_entry', methods=['POST'])
def add_entry():
    if db is None:
        return jsonify({"status": "error", "message": "Database not connected!"}), 500
    
    try:
        data = request.get_json()
        item = data.get('item', 'Unknown')
        buy = float(data.get('buy', 0))
        sell = float(data.get('sell', 0))
        
        gst = round((sell * 18) / 100, 2)
        profit = round(sell - buy - gst, 2)
        
        record = {
            'item_name': item,
            'purchase_price': buy,
            'sale_price': sell,
            'gst_tax_18': gst,
            'net_profit': profit,
            'timestamp': datetime.now(),
            'date_str': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        db.collection('Company_Accounts').add(record)
        return jsonify({"status": "success", "profit": profit})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
