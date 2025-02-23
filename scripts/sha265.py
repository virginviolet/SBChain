import hashlib
import sys

# use parameters
if len(sys.argv) < 2:
    print("Usage: python sha256.py <string>")
    sys.exit(1)

# get the string
string: str = sys.argv[1]
hashed_string: str = hashlib.sha256(str(string).encode()).hexdigest()
print(hashed_string)