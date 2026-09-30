def candidates(con): return con.execute("SELECT m.market_id,m.question,max(p.timestamp_utc) candidate_time FROM markets m LEFT JOIN price_observations p USING(market_id) GROUP BY ALL").fetchdf()

