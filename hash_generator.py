# hash_generator.py - Simple tool to generate hashed password for config.yaml

import bcrypt

# ← Change this to your real password (keep it secret!)
password = "Rma1234512345@"  # ← example - change it to whatever you want

# Generate the hashed password (this is exactly what streamlit-authenticator uses)
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))

print("Your hashed password (copy this full line):")
print(hashed.decode('utf-8'))