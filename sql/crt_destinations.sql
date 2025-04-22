create table destinations
	(trip_id integer PRIMARY KEY,
	 destination_number integer PRIMARY KEY,
	 destination_city varchar(30),
	 destination_country varchar(30),
	 votes integer,
	 added_by integer,
     added_at timestamp);
