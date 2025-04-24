create table destinations
	(destination_id integer PRIMARY KEY,
	trip_id integer,
	 destination_number integer,
	 destination_city varchar(30),
	 destination_country varchar(30),
	 votes integer,
	 added_by integer,
     added_at timestamp);
