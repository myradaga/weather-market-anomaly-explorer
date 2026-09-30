import hashlib
def signed_yes_exposure(side, outcome, size, price=1.0):
    sign = 1 if side.upper()=="BUY" else -1
    if outcome.upper()=="NO": sign *= -1
    return sign * float(size) * float(price)
def stable_fill_id(tx, log_index): return hashlib.sha256(f"{tx}|{log_index}".encode()).hexdigest()

