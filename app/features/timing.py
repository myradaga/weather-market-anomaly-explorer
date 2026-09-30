def signed_return(entry_price, later_price, direction="YES"):
    move=float(later_price)-float(entry_price); return move if direction=="YES" else -move
def lead_hours(entry,event): return (event-entry).total_seconds()/3600

