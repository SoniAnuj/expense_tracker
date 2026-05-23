from fastapi import FastAPI;
import sqlite3;
import re;
import hashlib;
import os;

app = FastAPI()

if os.path.exists("expense.db"):
    os.remove("expense.db")

connection = sqlite3.connect("expense.db",check_same_thread=False);
cursor = connection.cursor();

cursor.execute("""CREATE TABLE IF NOT EXISTS transactions(\
id INTEGER PRIMARY KEY AUTOINCREMENT, \
sms_hash TEXT unique, \
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
cursor.close()
connection.close()

@app.get("/")
def home():
    return {"message":"Server running"};

def generate_sms_hash(sms,sms_date,sms_sender):
    raw = f"{sms}_{sms_date}_{sms_sender}"
    return hashlib.md5(raw.encode()).hexdigest()

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
        "FOOD":["zomato","swiggy","dominos","pizza","burger","restaurant","cafe","starbucks","mcdonald"],
        "GROCERY":["bigbasket","blinkit","zepto","dmart","grocery","supermarket"],
        "ENTERTAINMENT":["netflix","spotify","prime video","hotstar","movie","cinema","bookmyshow","ott"],
        "TRAVEL":["uber","ola","rapido","irctc","metro","flight","makemytrip","yatra"],
        "BILLS":["electricity","water","gas","recharge","broadband","internet","postpaid","prepaid","dth"],
        "SHOPPING":["amazon","flipkart","myntra","ajio","nykaa","shopping"],
        "HEALTH":["apollo","pharmacy","hospital","clinic","medical","1mg","netmeds"],
        "EDUCATION":["unacademy","coursera","udemy","school","college","tuition","fees"],
        "SALARY":["salary","payroll","salary credited"],
        "INVESTMENT":["mutual fund","sip","zerodha","groww","upstox","nse","bse"],
        "LOAN":["emi","loan repayment","personal loan","home loan","car loan"],
        "TRANSFER":["upi","imps","neft","rtgs"],
        "ATM":["atm withdrawal","cash withdrawal"],
        "OTHER":[]
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
    conn = sqlite3.connect("expense.db")
    cursor = conn.cursor()

    sms = data["sms_body"]
    parsed_data = parse_transaction(sms)
    sms_date = data["sms_date"]
    sms_sender = data["sms_sender"]
    sms_hash = generate_sms_hash(sms,sms_date,sms_sender)

    cursor.execute("""
        INSERT OR IGNORE INTO transactions(
            sms_body,
            sms_hash,
            amount,
            transaction_type,
            merchant,
            category,
            account_number,
            upi_id,
            sms_sender,
            transaction_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,(
            sms,
            sms_hash,
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
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "status": "success"
    }


@app.get("/transactions")
def get_transactions():
    conn = sqlite3.connect("expense.db")
    cursor = conn.cursor()

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
    LIMIT 20
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

    cursor.close()
    conn.close()

    return {
        "transactions": transactions
    }
