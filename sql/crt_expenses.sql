create table expenses
	(expense_id integer PRIMARY KEY,
	 trip_id integer PRIMARY KEY,
	 category varchar(30),
	 description varchar(100),
	 amount float,
	 paid_by int,
	 date_incurred date);
