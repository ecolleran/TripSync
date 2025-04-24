create table expense_settlements
	(settlement_id integer PRIMARY KEY,
	 trip_id integer,
	 payer_id int,
	 receiver_id int,
	 amount_paid float,
	 settled_at timestamp);
