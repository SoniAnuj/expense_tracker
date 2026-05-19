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
category TEXT,
account_number TEXT,
upi_id TEXT,
sms_sender TEXT,
transaction_date TEXT)""");

connection.commit();

@app.get("/")
def home():
    return {"message":"Server running"};

def detect_transaction_type(sms):
    sms_lower = sms.lower()

    if "upi" in sms_lower:
        return "UPI"
    elif "sip" in sms_lower:
        return "SIP"
    elif "emi" in sms_lower:
        return "EMI"
    elif "credited" in sms_lower:
        return "CREDIT"
    elif "debited" in sms_lower:
        return "DEBIT"
    return "UNKNOWN"

def parse_transaction(sms):
    transaction_type = detect_transaction_type(sms)
    sensitive = identify_sensitive_fields(sms)

    return {
        "amount": amount_extraction(sms),
        "merchant": merchant_extraction(sms),
        "transaction_type": transaction_type,
        "category": identify_category(sms),
        "account_number": sensitive.get("account", "UNKNOWN"),
        "upi_id": sensitive.get("upi_id", "UNKNOWN"),
    }

def amount_extraction(sms):
    patterns = [
        r'Rs\.?\s?(\d+[,\d]*\.?\d*)',
        r'INR\s?(\d+[,\d]*\.?\d*)',
        r'(\d+[,\d]*\.?\d*)'
    ]

    for pattern in patterns:
        match = re.search(pattern,sms,re.IGNORECASE)
        if match:
            amount = match.group(1).replace(",","")
            return float(amount)
    return 0

def account_extraction(sms):
    patterns = [
        r'XX(\d{4})',
        r'X{2,}(\d{4})',
        r'ending\s?(\d{4})',
        r'Acct\s.*?(\d{4})',
        r'A/c\s.*?(\d{4})',
        r'Account\s.*?(\d{4})'
    ]

    for pattern in patterns:
        match = re.search(pattern,sms,re.IGNORECASE)
        if match:
            return match.group(1)
    return "UNKNOWN"

def upi_id_extraction(sms):
    match = re.search(r'to\s([A-Za-z0-9,_-]+@[A-Za-z0-9]+)',sms,re.IGNORECASE)

    if match:
        return match.group(1)
    return "UNKNOWN"

def merchant_extraction(sms):
    patterns = [
        r'to\s([A-Za-z0-9\s.&-]+?)(?:\s|$)',
        r'at\s([A-Za-z0-9\s.&-]+?)(?:\s|$)',
        r'paid to\s([A-Za-z0-9\s.&-]+?)(?:\s|$)'
    ]

    for pattern in patterns:
        match = re.search(pattern,sms,re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return "UNKNOWN"

def mask_sensitive_data(data):
    if data == "UNKNOWN":
        return data
    if len(data) <= 4:
        return "X" * len(data)
    return "XXXX" + data[-4:]

def identify_category(sms):
    sms_lower = sms.lower()

    category_rules = {
        "FOOD": ["restaurant", "cafe", "food", "dining", "pizza", "burger", "meal","zomato","swiggy"],
        "GROCERY": ["grocery", "supermarket", "store", "mart","bigbasket"],
        "ENTERTAINMENT": ["movie", "cinema", "theater", "concert", "entertainment","netflix","spotify"],
        "TRAVEL": ["taxi", "cab", "uber", "lyft", "transport","bus","train","irctc"],
        "BILLS": ["electricity", "water", "gas", "bill","phone","internet"],
        "SHOPPING": ["mall", "shopping", "store", "boutique","amazon","flipkart","myntra"],
        "HEALTH": ["pharmacy", "hospital", "clinic", "health","medical"],
        "EDUCATION": ["school", "college", "education", "course","unacademy","coursera"],
        "SALARY": ["salary", "payroll", "income", "credit"],
        "INVESTMENT": ["investment", "mutual fund", "stock", "sip","nse","bse"],
        "LOAN": ["loan", "emi", "bank", "debit"],
        "OTHER": []
    }

    for category, keywords in category_rules.items():
        for keyword in keywords:
            if keyword in sms_lower:
                return category
    return "OTHERS"

def identify_sensitive_fields(sms):
    sensitive_fields = {}
    
    account = account_extraction(sms)
    if account != "UNKNOWN":
        sensitive_fields["account"] = mask_sensitive_data(account)

    upi_id = upi_id_extraction(sms)
    if upi_id != "UNKNOWN":
        sensitive_fields["upi_id"] = mask_sensitive_data(upi_id)
    
    return sensitive_fields

@app.post("/sms")
def receive_sms(data: dict):

    sms = data["sms_body"]
    parsed_data = parse_transaction(sms)
    sms_date = data["sms_date"]
    sms_sender = data["sms_sender"]

    cursor.execute("""
        INSERT INTO transactions(
            sms_body,
            amount,
            transaction_type,
            merchant,
            category,
            account_number,
            upi_id,
            sms_sender,
            transaction_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,(
            sms,
            parsed_data["amount"],
            parsed_data["transaction_type"],
            parsed_data["merchant"],
            parsed_data["category"],
            parsed_data["account_number"],
            parsed_data["upi_id"],
            sms_sender,
            sms_date
        )
    )
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
        category,
        account_number,
        upi_id,
        sms_sender,
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
            "category": record[4],
            "account_number": record[5],
            "upi_id": record[6],
            "sms_sender": record[7],
            "transaction_date": record[8]
        })

    return {
        "transactions": transactions
    }
