import csv
import random
from datetime import datetime, timedelta

random.seed(42)

NUM_ROWS = 5000
START_DATE = datetime(2025, 1, 1)

transaction_types = ["P2P", "P2M"]
merchant_categories = [
    "Grocery", "E-Commerce", "Food Delivery", "Travel", "Entertainment",
    "Utilities", "Healthcare", "Education", "Ride Hailing", "Recharge"
]
statuses = ["SUCCESS", "FAILED", "PENDING"]
age_groups = ["18-25", "26-35", "36-45", "46-60", "60+"]
states = [
    "Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Uttar Pradesh",
    "Gujarat", "Rajasthan", "West Bengal", "Telangana", "Haryana"
]
banks = [
    "SBI", "HDFC", "ICICI", "Axis", "Kotak", "Yes Bank",
    "Bank of Baroda", "PNB", "Canara", "Union Bank"
]
devices = ["Android", "iOS"]
networks = ["4G", "5G", "WiFi"]
days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

rows = []
for i in range(NUM_ROWS):
    txn_id = f"TXN{i+1:06d}"
    ts = START_DATE + timedelta(
        days=random.randint(0, 365),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    txn_type = random.choice(transaction_types)
    cat = random.choice(merchant_categories) if txn_type == "P2M" else ""
    amount = round(random.uniform(10, 25000), 2)
    status = random.choices(
        statuses, weights=[82, 15, 3], k=1
    )[0]
    sender_age = random.choice(age_groups)
    receiver_age = random.choice(age_groups) if txn_type == "P2P" else ""
    sender_state = random.choice(states)
    sender_bank = random.choice(banks)
    receiver_bank = random.choice(banks)
    device = random.choice(devices)
    network = random.choice(networks)
    fraud = 1 if random.random() < 0.03 else 0
    hour = ts.hour
    day = days[ts.weekday()]
    weekend = 1 if ts.weekday() >= 5 else 0

    rows.append([
        txn_id, ts.isoformat(), txn_type, cat, amount, status,
        sender_age, receiver_age, sender_state, sender_bank, receiver_bank,
        device, network, fraud, hour, day, weekend
    ])

columns = [
    "transaction_id", "timestamp", "transaction_type", "merchant_category",
    "amount (INR)", "transaction_status", "sender_age_group", "receiver_age_group",
    "sender_state", "sender_bank", "receiver_bank", "device_type",
    "network_type", "fraud_flag", "hour_of_day", "day_of_week", "is_weekend"
]

with open("insightx_transactions.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(columns)
    writer.writerows(rows)

print(f"Generated {NUM_ROWS} rows -> insightx_transactions.csv")
