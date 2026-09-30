def order_imbalance(signed, notionals):
    den=sum(abs(float(x)) for x in notionals); return sum(float(x) for x in signed)/den if den else 0.0

