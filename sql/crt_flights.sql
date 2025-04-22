create table flights
	(flight_id integer PRIMARY KEY,
	 trip_id integer PRIMARY KEY,
	 flight_number integer PRIMARY KEY,
	 airline varchar(5),
	 non_stop boolean,
	 currency_code varchar(5),
	 departure_airport varchar(5),
	 arrival_airport varchar(5),
	 departure_time timestamp
	 arrival_time timestamp,
	 price float
	 votes integer,
	 booking_status varchar(30),
	 sync_status varchar(30),
	 added_by integer,
     added_at timestamp);
