from fastapi import FastAPI;
import sqlite3;
import re;

app = FastAPI()

connection = sqlite3.connect("expense.db",check_same_thread=False);
cursor = connection.cursor();

cursor.execute("""CREATE TABLE IF NOT EXISTS transactions(\
id INTEGER PRIMARY KEY AUTOINCREMENT, \
sms_body TEXT NOT NULL, \
amount REAL, \
transaction_type TEXT, \
merchant TEXT,
transaction_date TEXT)""");

connection.commit();

@app.get("/")
def home():
    return {"message":"Server running"};

def route_sms(sms):
    sms_lower = sms.lower()

    if "upi" in sms_lower:
        return parse_upi(sms)
    elif "sip" in sms_lower:
        return parse_sip(sms)
    elif "emi" in sms_lower:
        return parse_emi(sms)
    elif "credited" in sms_lower:
        return parse_credit(sms)
    elif "debited" in sms_lower:
        return parse_debit(sms)
    return parse_unknown(sms)

def parse_upi(sms):
    amount = 0
    merchant = "UNKNOWN"

    amount_match = re.search(r'(\d+\.?\d*)',sms)

    if amount_match:
        amount = float(amount_match.group(1))

    merchant_match = re.search(r'to\s([A-Za-z0-9\s]+)',sms,re.IGNORECASE)

    if merchant_match:
        merchant = merchant_match.group(1).strip()

    return{
        "amount": amount,
        "merchant": merchant,
        "transaction_type": "UPI"
    }

def parse_sip(sms):
    amount = 0

    amount_match = re.search(r'(\d+\.?\d*)',sms)

    if amount_match:
        amount = float(amount_match.group(1))
    
    return{
        "amount": amount,
        "merchant": "Mutual Fund",
        "transaction_type": "SIP"
    }

def parse_emi(sms):
    amount = 0

    amount_match = re.search(r'(\d+\.?\d*)',sms)

    if amount_match:
        amount = float(amount_match.group(1))
    
    return{
        "amount": amount,
        "merchant": "BANK",
        "transaction_type": "EMI"
    }

def parse_credit(sms):
    amount = 0

    amount_match = re.search(r'(\d+\.?\d*)',sms)

    if amount_match:
        amount = float(amount_match.group(1))
    
    return{
        "amount": amount,
        "merchant": "BANK",
        "transaction_type": "CREDIT"
    }

def parse_debit(sms):
    amount = 0

    amount_match = re.search(r'(\d+\.?\d*)',sms)

    if amount_match:
        amount = float(amount_match.group(1))
    
    return{
        "amount": amount,
        "merchant": "BANK",
        "transaction_type": "DEBIT"
    }

def parse_unknown(sms):
    return {
        "amount": 0,
        "merchant": "UNKNOWN",
        "transaction_type": "UNKNOWN"
    }

@app.post("/sms")
def receive_sms(data: dict):

    sms = data["sms_body"]
    parsed_data = route_sms(sms)
    sms_date = data["sms_date"]

    cursor.execute("""

    INSERT INTO transactions(
        sms_body,
        amount,
        transaction_type,
        merchant,
        transaction_date
    )

    VALUES (?, ?, ?, ?,?)

    """, (

        sms,
        parsed_data["amount"],
        parsed_data["transaction_type"],
        parsed_data["merchant"],
        sms_date
    ))

    connection.commit()

    return {
        "status": "success"
    }


@app.get("/transactions")
def get_transactions():

    cursor.execute("""

    SELECT
        id,
        amount,
        transaction_type,
        merchant,
        transaction_date
    FROM transactions
    ORDER BY transaction_date DESC
    """)

    records = cursor.fetchall()

    transactions = []

    for record in records:
        transactions.append({
            "id": record[0],
            "amount": record[1],
            "transaction_type": record[2],
            "merchant": record[3],
            "transaction_date": record[4]
        })

    return {
        "transactions": transactions
    }
