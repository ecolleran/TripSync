create table trips
	(trip_id integer PRIMARY KEY,
	 group_id integer,
	 trip_name varchar(30),
	 status varchar(30),
	 start_date date,
	 end_date date,
	 created_by integer,
     created_at timestamp);
