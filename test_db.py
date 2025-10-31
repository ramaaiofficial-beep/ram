from app.db import users_collection

users = list(users_collection.find())
print("Users:")
for u in users:
    print(u)
