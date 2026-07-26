"""Run this once (or after clearing the users/tickets tables) to populate
realistic demo data: 10 customers, 10 agents (5 per team), 2 team leads,
1 admin, plus SLA rules for all 4 priorities. Usage: python seed.py
"""
from app.database import SessionLocal, Base, engine
from app.models import User, RoleEnum, SLARule, PriorityEnum
from app.auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

created_count = 0


def add_user(name, email, password, role, team_id=None):
    global created_count
    if db.query(User).filter(User.email == email).first():
        print(f"Skipping {email}, already exists")
        return
    user = User(
        name=name,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        team_id=team_id,
    )
    db.add(user)
    created_count += 1
    print(f"Created {role.value:10s} team={team_id or '-'}: {email} / {password}")


# ---------- SLA Rules ----------
sla_targets = [
    (PriorityEnum.P1, 15, 240),     # Critical: 15 min response, 4 hr resolution
    (PriorityEnum.P2, 60, 480),     # High: 1 hr response, 8 hr resolution
    (PriorityEnum.P3, 240, 1440),   # Medium: 4 hr response, 24 hr resolution
    (PriorityEnum.P4, 1440, 2880),  # Low: 24 hr response, 48 hr resolution (tightened from 72hr)
]
for priority, response_min, resolution_min in sla_targets:
    if db.query(SLARule).filter(SLARule.priority == priority).first():
        print(f"Skipping SLA rule for {priority.value}, already exists")
        continue
    db.add(SLARule(priority=priority, response_minutes=response_min, resolution_minutes=resolution_min))
    print(f"Created SLA rule: {priority.value} -> response {response_min}min, resolution {resolution_min}min")


# ---------- Admin ----------
add_user("Ada Menon", "ada.menon@techserve.com", "adaAdmin23", RoleEnum.admin)

# ---------- Team Leads (2 teams: 1 and 2) ----------
add_user("Tara Reddy", "tara.reddy@techserve.com", "taraLead89", RoleEnum.team_lead, team_id=1)
add_user("Vikram Nair", "vikram.nair@techserve.com", "vikramLead67", RoleEnum.team_lead, team_id=2)

# ---------- Support Agents (5 on team 1, 5 on team 2) ----------
agent_names = [
    "Alex Fernandes", "Divya Iyer", "Rohan Kapoor", "Sneha Pillai", "Karan Malhotra",
    "Neha Bhatt", "Arjun Rao", "Meera Joshi", "Sameer Khan", "Ritika Desai",
]
for i, name in enumerate(agent_names):
    first = name.split()[0].lower()
    team = 1 if i < 5 else 2
    email = f"{first}.agent{i+1}@techserve.com"
    password = f"{first}Agent{10+i}"
    add_user(name, email, password, RoleEnum.agent, team_id=team)

# ---------- Customers ----------
customer_names = [
    "Priya Sharma", "Aditya Verma", "Kavya Menon", "Rahul Gupta", "Ananya Singh",
    "Nikhil Rao", "Pooja Nambiar", "Siddharth Iyer", "Lakshmi Pillai", "Varun Chawla",
]
customer_domains = ["gmail.com", "yahoo.com", "outlook.com", "gmail.com", "hotmail.com"]
for i, name in enumerate(customer_names):
    first = name.split()[0].lower()
    domain = customer_domains[i % len(customer_domains)]
    email = f"{first}{i+1}@{domain}"
    password = f"{first}{2020+i}"
    add_user(name, email, password, RoleEnum.customer)

# ---------- Extra customers with real, checkable emails (for testing forgot-password) ----------
real_email_customers = [
    ("Santa Mary", "santamarym024@gmail.com", "santa2030"),
    ("Santa M", "santamarym04@gmail.com", "santa2031"),
    ("Cathy", "b3364@rajagiri.edu", "student2032"),
    ("Jill", "20ec132@mgits.ac.in", "student2033"),
]
for name, email, password in real_email_customers:
    add_user(name, email, password, RoleEnum.customer)

db.commit()
db.close()
print(f"\nSeed complete. {created_count} users created.")