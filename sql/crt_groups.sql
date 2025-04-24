create table groups
	(group_id integer PRIMARY KEY,
	 group_name varchar(30),
	 group_description varchar(200), 
	group_photo blob, 
	created_by integer,
     created_at timestamp);
