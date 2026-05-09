import os
import json
import requests
import io
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials

app = Flask(__name__, template_folder='.')
app.secret_key = "ram_bhai_tally_pro_secure_key"

# --- CONFIGURATION ---
CLIENT_SECRETS_FILE = "client_secret.json"

SCOPES = [
    'https://www.googleapis.com/auth/drive.file', 
    'https://www.googleapis.com/auth/spreadsheets',
    'openid', 
    'https://www.googleapis.com/auth/userinfo.email'
]

# आपकी मुख्य Google Sheet ID
SPREADSHEET_ID = '1xZueFLMVfy6xp26xULXJ3mDKzYvWC6gnQXnwV8LH_YE'

# --- FIREBASE SETUP ---
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("✅ Ram Bhai Tally Engine Live!")
except Exception as e:
    print(f"❌ Firebase Error: {e}")

# --- GOOGLE AUTH ROUTES ---

@app.route('/login')
def login():
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES)
    flow.redirect_uri = url_for('callback', _external=True)
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='select_account', 
        include_granted_scopes='true'
    )
    session['state'] = state
    session['code_verifier'] = flow.code_verifier
    return redirect(auth_url)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/callback')
def callback():
    state = session.get('state')
    verifier = session.get('code_verifier')
    if not state or not verifier: return redirect(url_for('login'))
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('callback', _external=True)
    flow.code_verifier = verifier
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session['credentials'] = {
        'token': creds.token, 'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri, 'client_id': creds.client_id,
        'client_secret': creds.client_secret, 'scopes': creds.scopes
    }
    return redirect('/')

# --- SMART GOOGLE SHEETS AUTOMATION ---
def save_to_google_sheets(record):
    try:
        if 'credentials' not in session: return
        creds = Credentials(**session['credentials'])
        service = build('sheets', 'v4', credentials=creds)
        
        # कंपनी का नाम ही शीट का नाम होगा
        sheet_name = record['company'] 
        
        # 1. चेक करें कि क्या शीट पहले से मौजूद है
        spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        existing_sheets = [s['properties']['title'] for s in spreadsheet.get('sheets', [])]
        
        # 2. अगर शीट नहीं है, तो नई बनाएँ
        if sheet_name not in existing_sheets:
            batch_update_request = {
                'requests': [{
                    'addSheet': {
                        'properties': {'title': sheet_name}
                    }
                }]
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID,
                body=batch_update_request
            ).execute()
            print(f"✨ नई शीट बनाई गई: {sheet_name}")

        # 3. डेटा तैयार करें
        values = [[
            record['date_time'], record['company'], record['item'], 
            record['qty'], record['investment'], record['revenue'], 
            record['gst_tax'], record['net_profit'], record['amount_paid'], 
            record['pending_balance']
        ]]
        
        body = {'values': values}
        
        # 4. खास कंपनी वाली शीट में डेटा जोड़ें
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{sheet_name}'!A1", 
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        print(f"✅ {sheet_name} में डेटा सेव हो गया!")
    except Exception as e:
        print(f"❌ Sheets Error: {e}")

# --- AUTOMATED SAVE & AI CALCULATIONS ---
@app.route('/save', methods=['POST'])
def save_data():
    data = request.get_json()
    try:
        qty = float(data.get('quantity', 1))
        buy_rate = float(data.get('buy', 0))
        sell_rate = float(data.get('sell', 0))
        paid_amt = float(data.get('paid', 0))
        gst_percent = float(data.get('gst', 18))

        total_investment = round(buy_rate * qty, 2)
        total_revenue = round(sell_rate * qty, 2)
        gst_tax = round((total_revenue * gst_percent) / 100, 2)
        net_profit = round(total_revenue - total_investment - gst_tax, 2)
        pending = round(total_revenue - paid_amt, 2)

        record = {
            'company': data.get('company', 'General Store'),
            'item': data.get('item', 'Item'),
            'qty': qty,
            'unit': data.get('unit', 'Pcs'),
            'investment': total_investment,
            'revenue': total_revenue,
            'gst_tax': gst_tax,
            'net_profit': net_profit,
            'amount_paid': paid_amt,
            'pending_balance': pending,
            'date_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Firebase, Sheets और Drive तीनों में सेव होगा
        db.collection('Company_Ledger').add(record)
        save_to_google_sheets(record)
        
        if 'credentials' in session:
            backup_to_drive(record)

        return jsonify({"status": "success", "profit": net_profit})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/dashboard_data')
def dashboard_data():
    try:
        docs = db.collection('Company_Ledger').stream()
        t_sales = t_invest = t_profit = t_pending = t_gst = t_stock = 0
        for doc in docs:
            d = doc.to_dict()
            t_sales += d.get('revenue', 0); t_invest += d.get('investment', 0)
            t_profit += d.get('net_profit', 0); t_pending += d.get('pending_balance', 0)
            t_gst += d.get('gst_tax', 0); t_stock += d.get('qty', 0)
        return jsonify({
            "total_sales": round(t_sales, 2), "total_invest": round(t_invest, 2),
            "total_profit": round(t_profit, 2), "total_pending": round(t_pending, 2),
            "total_gst": round(t_gst, 2), "total_stock": t_stock
        })
    except Exception as e: return jsonify({"error": str(e)})

def backup_to_drive(record_data):
    try:
        creds = Credentials(**session['credentials'])
        service = build('drive', 'v3', credentials=creds)
        file_name = f"Tally_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        content = json.dumps(record_data, ensure_ascii=False).encode('utf-8')
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype='application/json')
        service.files().create(body={'name': file_name}, media_body=media).execute()
    except: pass

@app.route('/')
def index():
    if 'credentials' not in session:
        return '''
        <div style="text-align:center; margin-top:50px; font-family: Arial;">
            <h1>Ram Bhai Tally Pro</h1>
            <p>कृपया काम शुरू करने के लिए लॉगिन करें</p>
            <a href="/login"><button style="padding:15px 30px; font-size:18px; background-color:#4285F4; color:white; border-radius:5px; cursor:pointer;">Google Login करें</button></a>
        </div>
        '''
    return f'''
    <div style="padding:10px; background:#f4f4f4; border-bottom:1px solid #ccc; display:flex; justify-content:space-between; align-items:center; font-family: Arial;">
        <b>Ram Bhai Tally Active</b>
        <a href="/logout"><button style="padding:5px 10px; background:red; color:white; border:none; border-radius:3px; cursor:pointer;">Logout करें</button></a>
    </div>
    {render_template('index.html')}
    '''

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    app.run(host='0.0.0.0', port=5000, debug=True)
