def alert_rate(scores,threshold=.7): return sum(s>=threshold for s in scores)/len(scores) if scores else 0

